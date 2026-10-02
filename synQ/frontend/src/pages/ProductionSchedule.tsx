import React, { useState, useEffect } from 'react';
import { scheduleService } from '../api';
import { Schedule } from '../types';
import StatusBadge from '../components/StatusBadge';
import { Calendar as CalendarIcon, Play, AlertCircle } from 'lucide-react';
import GanttChart from '../components/GanttChart';

interface ScheduleProps {
  factoryId: number;
}

const ProductionSchedule: React.FC<ScheduleProps> = ({ factoryId }) => {
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchSchedule = async () => {
    setLoading(true);
    try {
      const data = await scheduleService.getActiveSchedule(factoryId);
      if (data && data.id) {
        setSchedule(data);
      } else {
        setSchedule(null);
      }
    } catch (err) {
      console.error(err);
      setError('Failed to fetch schedule');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSchedule();
  }, [factoryId]);

  const handleGenerate = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await scheduleService.generateSchedule(factoryId);
      setSchedule(data);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail?.message || 'Failed to generate schedule');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 h-full flex flex-col">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <CalendarIcon className="text-synq-primary" />
            Production Schedule
          </h2>
          <p className="text-synq-muted">Interactive task sequencing and resource allocation</p>
        </div>
        
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="bg-synq-primary hover:bg-blue-600 text-white px-4 py-2 rounded-lg font-medium shadow-lg shadow-blue-500/20 transition-all flex items-center gap-2 disabled:opacity-50"
        >
          <Play size={18} />
          {loading ? 'Processing...' : 'Run Auto-Scheduler'}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded-lg flex items-start gap-3 flex-shrink-0">
          <AlertCircle className="flex-shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {schedule ? (
        <div className="flex-1 flex flex-col space-y-4 min-h-0 bg-synq-card rounded-xl border border-synq-border p-6 shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-synq-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none"></div>
          
          <div className="flex justify-between items-start z-10">
            <div>
              <h3 className="text-xl font-bold">{schedule.name}</h3>
              <p className="text-sm text-synq-muted flex items-center gap-2 mt-1">
                Generated: {new Date(schedule.created_at).toLocaleString()}
                <span className="text-synq-border">•</span>
                Status: <StatusBadge status={schedule.status} />
              </p>
            </div>
            
            <div className="flex items-center gap-6 bg-synq-dark p-3 rounded-lg border border-synq-border text-sm">
              <div className="text-center">
                <p className="text-synq-muted uppercase text-[10px] tracking-wider mb-1">Makespan</p>
                <p className="font-bold text-lg text-synq-text">{schedule.metrics?.makespan?.toFixed(1) || 0}m</p>
              </div>
              <div className="w-px h-8 bg-synq-border"></div>
              <div className="text-center">
                <p className="text-synq-muted uppercase text-[10px] tracking-wider mb-1">Deadline Adh.</p>
                <p className="font-bold text-lg text-green-400">{schedule.metrics?.deadline_adherence || 0}%</p>
              </div>
              <div className="w-px h-8 bg-synq-border"></div>
              <div className="text-center">
                <p className="text-synq-muted uppercase text-[10px] tracking-wider mb-1">Utilization</p>
                <p className="font-bold text-lg text-blue-400">{schedule.metrics?.machine_utilization || 0}%</p>
              </div>
            </div>
          </div>

          <div className="flex-1 border border-synq-border rounded-lg bg-[#111827] overflow-hidden flex flex-col z-10 z-0">
             <GanttChart tasks={schedule.tasks || []} />
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center border-2 border-dashed border-synq-border rounded-xl bg-synq-card/30">
          <div className="text-center max-w-md p-8">
            <div className="w-16 h-16 bg-synq-dark rounded-full flex items-center justify-center mx-auto mb-4 border border-synq-border">
              <CalendarIcon size={32} className="text-synq-muted" />
            </div>
            <h3 className="text-xl font-bold mb-2">No Active Schedule</h3>
            <p className="text-synq-muted mb-6">
              There is currently no active production schedule for this factory. 
              Run the deterministic scheduling engine to generate one based on current orders, machine availability, and dependencies.
            </p>
            <button 
              onClick={handleGenerate}
              className="bg-synq-dark hover:bg-synq-border border border-synq-border text-synq-text px-6 py-2.5 rounded-lg transition-colors"
            >
              Generate Initial Schedule
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProductionSchedule;
