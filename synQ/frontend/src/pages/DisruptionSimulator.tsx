import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { factoryService, disruptionService } from '../api';
import { Factory } from '../types';
import { AlertOctagon, Settings2, ArrowRight } from 'lucide-react';

interface DisruptionProps {
  factoryId: number;
}

const DisruptionSimulator: React.FC<DisruptionProps> = ({ factoryId }) => {
  const navigate = useNavigate();
  const [factory, setFactory] = useState<Factory | null>(null);
  const [loading, setLoading] = useState(false);

  // Form State
  const [disruptionType, setDisruptionType] = useState('MACHINE_BREAKDOWN');
  const [resourceId, setResourceId] = useState('');
  const [duration, setDuration] = useState('2');
  const [isWhatIf, setIsWhatIf] = useState(false);

  useEffect(() => {
    factoryService.getFactory(factoryId).then(setFactory).catch(console.error);
  }, [factoryId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    let resourceType = null;
    if (disruptionType.includes('MACHINE')) resourceType = 'machine';
    if (disruptionType.includes('WORKER')) resourceType = 'worker';

    const payload = {
      disruption_type: disruptionType,
      description: `Simulated ${disruptionType}`,
      affected_resource_id: resourceId ? parseInt(resourceId) : null,
      affected_resource_type: resourceType,
      parameters: { duration_hours: parseFloat(duration) },
      is_whatif: isWhatIf
    };

    try {
      const res = await disruptionService.createDisruption(factoryId, payload);
      // Navigate to recovery center with disruption ID
      navigate(`/recovery?d=${res.disruption.id}`);
    } catch (err) {
      console.error(err);
      alert('Failed to simulate disruption. Do you have an active schedule?');
    } finally {
      setLoading(false);
    }
  };

  if (!factory) return <div className="text-synq-muted p-6">Loading factory resources...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <AlertOctagon className="text-red-500" />
          Disruption Simulator
        </h2>
        <p className="text-synq-muted">Test your factory's resilience by simulating operational failures.</p>
      </div>

      <div className="bg-synq-card rounded-xl border border-synq-border p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-red-500/5 rounded-full blur-3xl pointer-events-none"></div>

        <form onSubmit={handleSubmit} className="relative z-10 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Left Column */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-synq-muted mb-1">Disruption Type</label>
                <div className="relative">
                  <select 
                    value={disruptionType}
                    onChange={e => { setDisruptionType(e.target.value); setResourceId(''); }}
                    className="w-full bg-synq-dark border border-synq-border rounded-lg px-4 py-2.5 text-synq-text focus:border-synq-primary focus:ring-1 focus:ring-synq-primary appearance-none outline-none"
                  >
                    <option value="MACHINE_BREAKDOWN">Machine Breakdown</option>
                    <option value="MACHINE_CAPACITY_REDUCTION">Machine Capacity Reduction</option>
                    <option value="WORKER_ABSENCE">Worker Absence</option>
                    <option value="MATERIAL_SHORTAGE">Material Shortage</option>
                  </select>
                  <Settings2 size={16} className="absolute right-3 top-3 text-synq-muted pointer-events-none" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-synq-muted mb-1">Target Resource</label>
                <select 
                  value={resourceId}
                  onChange={e => setResourceId(e.target.value)}
                  required
                  className="w-full bg-synq-dark border border-synq-border rounded-lg px-4 py-2.5 text-synq-text focus:border-synq-primary outline-none"
                >
                  <option value="" disabled>Select a {disruptionType.includes('MACHINE') ? 'machine' : 'worker'}...</option>
                  {disruptionType.includes('MACHINE') 
                    ? factory.machines?.map(m => (
                        <option key={m.id} value={m.id}>{m.name} ({m.status})</option>
                      ))
                    : factory.workers?.map(w => (
                        <option key={w.id} value={w.id}>{w.name} ({w.shift})</option>
                      ))
                  }
                </select>
              </div>
            </div>

            {/* Right Column */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-synq-muted mb-1">Duration (Hours)</label>
                <input 
                  type="number"
                  min="0.5"
                  step="0.5"
                  value={duration}
                  onChange={e => setDuration(e.target.value)}
                  className="w-full bg-synq-dark border border-synq-border rounded-lg px-4 py-2.5 text-synq-text focus:border-synq-primary outline-none"
                />
              </div>

              <div className="flex items-center pt-8">
                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className="relative">
                    <input 
                      type="checkbox" 
                      className="sr-only" 
                      checked={isWhatIf}
                      onChange={e => setIsWhatIf(e.target.checked)}
                    />
                    <div className={`w-10 h-6 outline-none rounded-full transition-colors ${isWhatIf ? 'bg-synq-primary' : 'bg-synq-dark border border-synq-border'}`}></div>
                    <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${isWhatIf ? 'translate-x-4' : ''}`}></div>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-synq-text group-hover:text-white transition-colors">What-If Mode</span>
                    <p className="text-[10px] text-synq-muted">Simulate without recording officially</p>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-synq-border/50 flex justify-end">
            <button 
              type="submit"
              disabled={loading || !resourceId}
              className="bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/50 px-6 py-2.5 rounded-lg font-medium transition-all flex items-center gap-2 disabled:opacity-50"
            >
              {loading ? 'Analyzing Impact...' : 'Simulate Disruption'}
              <ArrowRight size={18} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DisruptionSimulator;
