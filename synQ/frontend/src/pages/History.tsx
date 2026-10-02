import React, { useState, useEffect } from 'react';
import { History as HistoryIcon } from 'lucide-react';
import api from '../api';

interface HistoryProps {
  factoryId: number;
}

const History: React.FC<HistoryProps> = ({ factoryId }) => {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAudit = async () => {
      setLoading(true);
      try {
        const res = await api.get(`/factories/${factoryId}/audit`);
        setLogs(res.data);
      } catch(err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchAudit();
  }, [factoryId]);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <HistoryIcon className="text-synq-primary" />
          Audit History
        </h2>
        <p className="text-synq-muted">Traceability of all system events, disruptions, and plan changes.</p>
      </div>

      <div className="bg-synq-card rounded-xl border border-synq-border p-6 shadow-xl relative overflow-hidden">
        {loading ? (
          <div className="animate-pulse">Loading logs...</div>
        ) : logs.length === 0 ? (
          <div className="text-synq-muted py-8 text-center">No history recorded yet.</div>
        ) : (
          <div className="relative">
            <div className="absolute top-0 bottom-0 left-6 w-px bg-synq-border"></div>
            <div className="space-y-6">
              {logs.map((log) => (
                <div key={log.id} className="relative pl-14 flex items-start group">
                  {/* Timeline dot */}
                  <div className="absolute left-[22px] w-3 h-3 rounded-full bg-synq-primary ring-4 ring-synq-card mt-1.5 group-hover:bg-synq-accent transition-colors"></div>
                  
                  <div className="bg-synq-dark border border-synq-border rounded-lg p-4 w-full group-hover:border-synq-primary/30 transition-colors">
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-bold text-[15px]">{log.title}</h4>
                      <span className="text-xs text-synq-muted">
                        {new Date(log.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="text-xs text-synq-muted bg-synq-card p-3 rounded font-mono overflow-auto custom-scrollbar">
                      {JSON.stringify(log.details, null, 2)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default History;
