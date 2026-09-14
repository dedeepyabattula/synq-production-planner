import React, { useState, useEffect } from 'react';
import { CheckSquare } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { RecoveryPlan } from '../types';
import api from '../api';

interface ApprovalCenterProps {
  factoryId: number;
}

const ApprovalCenter: React.FC<ApprovalCenterProps> = ({ factoryId }) => {
  const [plans, setPlans] = useState<RecoveryPlan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPlans = async () => {
      setLoading(true);
      try {
        const res = await api.get(`/factories/${factoryId}/recovery-plans`);
        setPlans(res.data);
      } catch(err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchPlans();
  }, [factoryId]);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <CheckSquare className="text-synq-primary" />
          Approval Center
        </h2>
        <p className="text-synq-muted">Ledger of generated recovery plans and approval statuses.</p>
      </div>

      <div className="bg-synq-card rounded-xl border border-synq-border shadow-xl overflow-hidden">
        {loading ? (
          <div className="p-6 animate-pulse">Loading...</div>
        ) : (
          <table className="w-full text-sm text-left">
            <thead className="bg-synq-dark text-synq-muted uppercase text-[10px] tracking-wider border-b border-synq-border">
              <tr>
                <th className="px-6 py-4 font-semibold text-white">ID</th>
                <th className="px-6 py-4 font-semibold text-white">Plan Name</th>
                <th className="px-6 py-4 font-semibold text-white">Strategy</th>
                <th className="px-6 py-4 font-semibold text-white">Metrics</th>
                <th className="px-6 py-4 font-semibold text-white">Status</th>
              </tr>
            </thead>
            <tbody>
              {plans.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center p-6 text-synq-muted">No recovery plans generated yet.</td>
                </tr>
              )}
              {plans.map(p => (
                <tr key={p.id} className="border-b border-synq-border/50 hover:bg-white/5 transition-colors">
                  <td className="px-6 py-4">#{p.id}</td>
                  <td className="px-6 py-4 font-medium">
                    {p.name}
                    {p.is_recommended && <span className="ml-2 bg-synq-accent/20 text-synq-accent text-[10px] px-1.5 py-0.5 rounded">AI REC</span>}
                  </td>
                  <td className="px-6 py-4 text-synq-muted">{p.strategy}</td>
                  <td className="px-6 py-4 text-xs whitespace-nowrap">
                    Score: {p.metrics?.weighted_score ? p.metrics.weighted_score.toFixed(1) : 'N/A'} <br/>
                    Adherence: {p.metrics?.deadline_adherence}%
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={p.approval_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default ApprovalCenter;
