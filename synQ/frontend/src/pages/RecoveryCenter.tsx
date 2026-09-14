import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { disruptionService } from '../api';
import { ImpactAnalysis, RecoveryPlan } from '../types';
import StatusBadge from '../components/StatusBadge';
import { ShieldCheck, Activity, Brain, Clock, Zap, Target, DollarSign } from 'lucide-react';
import GanttChart from '../components/GanttChart';

interface RecoveryCenterProps {
  factoryId: number;
}

const RecoveryCenter: React.FC<RecoveryCenterProps> = ({ factoryId }) => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const disruptionId = searchParams.get('d');
  
  const [impact, setImpact] = useState<ImpactAnalysis | null>(null);
  const [plans, setPlans] = useState<RecoveryPlan[]>([]);
  const [loading, setLoading] = useState(false);
  const [weights, setWeights] = useState({
    deadline: 80, cost: 60, delay: 70, utilization: 50, energy: 40
  });

  const loadData = async (dId: number, currentWeights: any) => {
    setLoading(true);
    try {
      const dbImpact = await disruptionService.getImpact(factoryId, dId);
      setImpact(dbImpact);
      
      const res = await disruptionService.generateRecoveryPlans(factoryId, dId, currentWeights);
      setPlans(res.plans || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (disruptionId) {
      loadData(parseInt(disruptionId), weights);
    }
  }, [factoryId, disruptionId]);

  const handleReweight = async () => {
    if (!disruptionId) return;
    setLoading(true);
    try {
      // Uses the dedicated reweight endpoint: re-scores the plans already on
      // screen (including any manager modifications) against the new
      // weights, instead of throwing them away and regenerating from
      // scratch. This is what lets "changing weights can change the
      // recommended plan" work without discarding manager edits.
      const res = await disruptionService.reweightPlans(factoryId, parseInt(disruptionId), weights);
      setPlans(res.plans || []);
    } catch (err: any) {
      alert('Failed to recalculate: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (planId: number) => {
    if (!confirm('Are you sure you want to approve and APPLY this recovery plan? This will change the active schedule.')) return;
    try {
      await disruptionService.approvePlan(planId);
      navigate('/schedule');
    } catch (err: any) {
      alert('Failed to approve: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleReject = async (planId: number) => {
    try {
      await disruptionService.rejectPlan(planId);
      setPlans(plans.map(p => p.id === planId ? { ...p, approval_status: 'REJECTED' } : p));
    } catch (err: any) {
      alert('Failed to reject: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleModify = async (planId: number) => {
    const machineInput = prompt(
      'Modify plan: enter additional machine ID(s) to exclude (comma-separated), or leave blank.'
    );
    if (machineInput === null) return; // cancelled
    const additional_excluded_machine_ids = machineInput
      .split(',')
      .map(s => parseInt(s.trim()))
      .filter(n => !isNaN(n));
    setLoading(true);
    try {
      const updated = await disruptionService.modifyPlan(planId, { additional_excluded_machine_ids });
      setPlans(plans.map(p => p.id === planId ? { ...p, ...updated } : p));
    } catch (err: any) {
      alert('Failed to modify: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  if (!disruptionId) {
    return (
      <div className="flex bg-synq-card h-full rounded-xl border border-synq-border items-center justify-center text-synq-muted">
        No active disruption selected. Go to Simulator first.
      </div>
    );
  }

  if (loading && !impact) return <div className="animate-pulse">Analyzing alternatives...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <ShieldCheck className="text-green-500" />
            Recovery Center
          </h2>
          <p className="text-synq-muted">Impact analysis and AI recommended strategies</p>
        </div>
      </div>

      {impact?.is_whatif && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 text-yellow-300 text-sm rounded-lg px-4 py-3">
          <strong>What-If Simulation</strong> — these plans are for exploration only and cannot be applied to the active schedule.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Impact Summary & Weights */}
        <div className="space-y-6">
          {impact && (
            <div className="bg-synq-card rounded-xl border border-red-500/30 p-5 shadow-lg">
              <h3 className="font-bold text-lg mb-3 flex items-center gap-2 text-white">
                <Activity size={18} className="text-red-400" />
                Impact Summary
              </h3>
              <p className="text-sm text-synq-muted mb-4">{impact.summary}</p>
              
              <div className="space-y-3">
                <div className="bg-synq-dark p-3 rounded-lg border border-synq-border flex justify-between">
                  <span className="text-sm text-synq-muted">Directly Affected Tasks</span>
                  <span className="font-bold">{impact.affected_tasks.length}</span>
                </div>
                <div className="bg-synq-dark p-3 rounded-lg border border-synq-border flex justify-between">
                  <span className="text-sm text-synq-muted">Deadlines at Risk</span>
                  <span className="font-bold text-red-400">{impact.deadlines_at_risk.length}</span>
                </div>
                <div className="bg-synq-dark p-3 rounded-lg border border-synq-border flex justify-between">
                  <span className="text-sm text-synq-muted">Expected Delay</span>
                  <span className="font-bold text-orange-400">{impact.expected_delay_minutes} min</span>
                </div>
              </div>
            </div>
          )}

          <div className="bg-synq-card rounded-xl border border-synq-border p-5 shadow-lg">
            <h3 className="font-bold text-lg mb-4 flex items-center gap-2 text-white">
              <Brain size={18} className="text-synq-accent" />
              Strategic Priorities
            </h3>
            
            <div className="space-y-4">
              {Object.entries(weights).map(([key, value]) => (
                <div key={key}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-synq-muted capitalize">{key}</span>
                    <span className="font-medium">{value}</span>
                  </div>
                  <input 
                    type="range" min="0" max="100" 
                    value={value}
                    onChange={(e) => setWeights({...weights, [key]: parseInt(e.target.value)})}
                    className="w-full accent-synq-accent bg-synq-dark h-1 sm:h-2"
                  />
                </div>
              ))}
              
              <button 
                onClick={handleReweight}
                disabled={loading}
                className="w-full mt-2 bg-synq-dark hover:bg-synq-border border border-synq-border text-synq-text text-sm py-2 rounded transition-colors"
              >
                {loading ? 'Recalculating...' : 'Recalculate Recommendation'}
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Plans */}
        <div className="lg:col-span-2 space-y-4">
          <h3 className="font-bold text-lg">Alternative Scenarios</h3>
          
          {plans.map(plan => (
            <div 
              key={plan.id} 
              className={`bg-synq-card rounded-xl border p-5 transition-all ${
                plan.is_recommended 
                  ? 'border-synq-accent shadow-[0_0_15px_rgba(6,182,212,0.15)]' 
                  : 'border-synq-border hover:border-synq-primary/50'
              }`}
            >
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h4 className="text-lg font-bold flex items-center gap-2">
                    {plan.name}
                    {plan.is_recommended && (
                      <span className="bg-synq-accent/20 text-synq-accent text-[10px] px-2 py-0.5 rounded uppercase tracking-wider font-bold">
                        AI Recommended
                      </span>
                    )}
                    {!plan.is_feasible && (
                      <span className="bg-red-500/20 text-red-400 text-[10px] px-2 py-0.5 rounded uppercase tracking-wider font-bold">
                        Infeasible
                      </span>
                    )}
                  </h4>
                  <p className="text-sm text-synq-muted mt-1">{plan.description}</p>
                  {plan.infeasibility_reason && (
                    <p className="text-xs text-red-400 mt-2">Error: {plan.infeasibility_reason}</p>
                  )}
                </div>
                
                {plan.is_feasible && (
                  <div className="flex flex-col gap-2 items-end">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApprove(plan.id)}
                        disabled={plan.approval_status === 'REJECTED' || impact?.is_whatif}
                        title={impact?.is_whatif ? 'What-If plans cannot be applied to the active schedule' : ''}
                        className="bg-synq-primary hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-2 rounded text-sm font-medium transition-colors whitespace-nowrap"
                      >
                        Approve & Apply
                      </button>
                      <button
                        onClick={() => handleModify(plan.id)}
                        className="border border-synq-border hover:border-synq-primary/50 text-synq-text px-3 py-2 rounded text-sm font-medium transition-colors whitespace-nowrap"
                      >
                        Modify
                      </button>
                      <button
                        onClick={() => handleReject(plan.id)}
                        disabled={plan.approval_status === 'REJECTED'}
                        className="border border-red-500/30 hover:bg-red-500/10 disabled:opacity-40 disabled:cursor-not-allowed text-red-400 px-3 py-2 rounded text-sm font-medium transition-colors whitespace-nowrap"
                      >
                        Reject
                      </button>
                    </div>
                    {plan.approval_status && plan.approval_status !== 'PENDING' && (
                      <StatusBadge status={plan.approval_status} />
                    )}
                  </div>
                )}
              </div>

              {plan.is_feasible && plan.metrics && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <MetricBox 
                    icon={<Target size={14} />} 
                    label="Deadline Adh." 
                    value={`${plan.metrics.deadline_adherence}%`} 
                    color="text-green-400"
                  />
                  <MetricBox 
                    icon={<Clock size={14} />} 
                    label="Total Delay" 
                    value={`${plan.metrics.total_delay}m`} 
                    color="text-orange-400"
                  />
                  <MetricBox 
                    icon={<DollarSign size={14} />} 
                    label="Est. Cost" 
                    value={`$${plan.metrics.estimated_cost}`} 
                    color="text-red-400"
                  />
                  <MetricBox 
                    icon={<Zap size={14} />} 
                    label="Machine Util." 
                    value={`${plan.metrics.machine_utilization}%`} 
                    color="text-blue-400"
                  />
                </div>
              )}
              
              {plan.is_feasible && (
                <div className="mt-4 pt-4 border-t border-synq-border/30 h-48 rounded bg-synq-dark p-2">
                  <GanttChart tasks={plan.schedule_data} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const MetricBox = ({ icon, label, value, color }: any) => (
  <div className="bg-synq-dark border border-synq-border rounded p-2 flex flex-col justify-center items-center text-center">
    <div className={`p-1 mb-1 rounded bg-black/20 ${color}`}>{icon}</div>
    <span className="text-[10px] text-synq-muted uppercase tracking-wider">{label}</span>
    <span className={`font-bold ${color}`}>{value}</span>
  </div>
);

export default RecoveryCenter;
