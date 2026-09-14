import React, { useMemo } from 'react';
import { ScheduleTask } from '../types';

interface GanttChartProps {
  tasks: ScheduleTask[];
}

const MACHINE_COLORS = [
  'bg-blue-500', 'bg-emerald-500', 'bg-violet-500', 'bg-amber-500', 
  'bg-pink-500', 'bg-cyan-500', 'bg-rose-500', 'bg-indigo-500'
];

const GanttChart: React.FC<GanttChartProps> = ({ tasks }) => {
  const { machines, maxTime } = useMemo(() => {
    if (!tasks || tasks.length === 0) {
      return { machines: [], maxTime: 100 };
    }

    // Group tasks by machine
    const machineGroups = new Map<number, { id: number, name: string, tasks: ScheduleTask[] }>();
    let max = 0;

    tasks.forEach(t => {
      if (!machineGroups.has(t.machine_id)) {
        machineGroups.set(t.machine_id, {
          id: t.machine_id,
          name: t.machine_name || `Machine ${t.machine_id}`,
          tasks: []
        });
      }
      machineGroups.get(t.machine_id)!.tasks.push(t);
      if (t.end_time > max) max = t.end_time;
    });

    const mList = Array.from(machineGroups.values()).sort((a, b) => a.name.localeCompare(b.name));
    
    // Scale max time for some padding
    const maxTime = max > 0 ? Math.ceil(max * 1.1) : 100;

    return { machines: mList, maxTime };
  }, [tasks]);

  if (!tasks || tasks.length === 0) {
    return (
      <div className="flex bg-[#111827] items-center justify-center h-full text-synq-muted">
        No tasks to display in Gantt Chart
      </div>
    );
  }

  // Create time markers
  const markers: number[] = [];
  const step = maxTime > 300 ? 60 : maxTime > 100 ? 30 : 10;
  for (let i = 0; i <= maxTime; i += step) {
    markers.push(i);
  }

  return (
    <div className="flex flex-col h-full w-full bg-[#111827] text-sm overflow-hidden custom-scrollbar pb-1">
      {/* Header / Timeline */}
      <div className="flex border-b border-synq-border bg-synq-dark sticky top-0 z-20">
        <div className="w-48 flex-shrink-0 border-r border-synq-border p-3 font-semibold text-synq-muted flex items-center bg-synq-dark">
          Resource
        </div>
        <div className="flex-1 relative min-w-[600px] h-12 bg-synq-dark">
          {markers.map(m => (
            <div 
              key={m} 
              className="absolute top-0 bottom-0 border-l border-synq-border/30"
              style={{ left: `${(m / maxTime) * 100}%` }}
            >
              <span className="text-[10px] text-synq-muted -ml-3 mt-8 bg-synq-dark px-1">
                {m}m
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto overflow-x-auto">
        <div className="min-w-[750px]">
          {machines.map((m, idx) => {
            const colorClass = MACHINE_COLORS[idx % MACHINE_COLORS.length];
            return (
              <div key={m.id} className="flex border-b border-synq-border/50 hover:bg-white/5 transition-colors group">
                <div className="w-48 flex-shrink-0 border-r border-synq-border p-3 flex flex-col justify-center bg-synq-dark sticky left-0 z-10 group-hover:bg-[#1f2937]">
                  <span className="font-medium truncate" title={m.name}>{m.name}</span>
                </div>
                <div className="flex-1 relative h-16 bg-[#111827]/50 py-2">
                  {/* Grid lines */}
                  {markers.map(marker => (
                    <div 
                      key={marker} 
                      className="absolute top-0 bottom-0 border-l border-synq-border/20 pointer-events-none"
                      style={{ left: `${(marker / maxTime) * 100}%` }}
                    />
                  ))}
                  
                  {/* Tasks */}
                  {m.tasks.map(t => {
                    const left = (t.start_time / maxTime) * 100;
                    const width = ((t.end_time - t.start_time) / maxTime) * 100;
                    
                    return (
                      <div
                        key={t.id}
                        className={`absolute top-2 bottom-2 rounded cursor-pointer shadow-sm shadow-black/20 overflow-hidden ${colorClass} bg-opacity-80 hover:bg-opacity-100 hover:ring-2 ring-white/30 transition-all group/task group-hover/row:opacity-100`}
                        style={{ left: `${left}%`, width: `${width}%` }}
                        title={`Order: ${t.order_code}\nStep: ${t.step_name}\nTime: ${t.start_time.toFixed(1)} - ${t.end_time.toFixed(1)}m\nStatus: ${t.status}`}
                      >
                        <div className="px-2 py-1 h-full flex flex-col justify-center">
                          <span className="text-[10px] font-bold text-white leading-tight truncate drop-shadow-md">
                            {t.order_code}
                          </span>
                          <span className="text-[10px] text-white/80 leading-tight truncate drop-shadow-md">
                            {t.step_name}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default GanttChart;
