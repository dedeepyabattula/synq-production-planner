import React, { useState, useEffect } from 'react';
import { factoryService, scheduleService } from '../api';
import { Factory, Schedule } from '../types';
import StatusBadge from '../components/StatusBadge';
import { Activity, Cpu, Users, Package, AlertOctagon, Target } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

interface DashboardProps {
  factoryId: number;
}

const Dashboard: React.FC<DashboardProps> = ({ factoryId }) => {
  const [factory, setFactory] = useState<Factory | null>(null);
  const [activeSchedule, setActiveSchedule] = useState<Schedule | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [fData, sData] = await Promise.all([
          factoryService.getFactory(factoryId),
          scheduleService.getActiveSchedule(factoryId).catch(() => null)
        ]);
        setFactory(fData);
        if (sData && sData.id) {
          setActiveSchedule(sData);
        } else {
          setActiveSchedule(null);
        }
      } catch (err) {
        console.error("Dashboard fetch error", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [factoryId]);

  if (loading) {
    return <div className="text-synq-muted animate-pulse">Loading Dashboard...</div>;
  }

  if (!factory) {
    return <div className="text-red-400">Failed to load factory data.</div>;
  }

  // Calculate stats
  const activeMachines = factory.machines?.filter(m => m.status === 'AVAILABLE' || m.status === 'BUSY').length || 0;
  const totalMachines = factory.machines?.length || 0;
  const availableWorkers = factory.workers?.filter(w => w.available).length || 0;
  const totalWorkers = factory.workers?.length || 0;
  
  const pendingOrders = factory.orders?.filter(o => o.status === 'PENDING' || o.status === 'IN_PROGRESS').length || 0;
  const criticalOrders = factory.orders?.filter(o => o.priority === 'CRITICAL').length || 0;

  const machineStatusColors: Record<string, string> = {
    AVAILABLE: '#22c55e', BUSY: '#3b82f6', MAINTENANCE: '#eab308', FAILED: '#ef4444'
  };

  const machineData = factory.machines?.reduce((acc: any[], m) => {
    const existing = acc.find(x => x.name === m.status);
    if (existing) existing.value += 1;
    else acc.push({ name: m.status, value: 1, color: machineStatusColors[m.status] || '#94a3b8' });
    return acc;
  }, []) || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">{factory.name} Overview</h2>
          <p className="text-synq-muted">{factory.industry}</p>
        </div>
        {activeSchedule ? (
          <div className="bg-synq-card border border-synq-primary/30 px-4 py-2 rounded flex items-center gap-3">
            <Activity className="text-synq-primary" size={20} />
            <div>
              <p className="text-xs text-synq-muted">Active Schedule</p>
              <p className="font-semibold">{activeSchedule.name}</p>
            </div>
          </div>
        ) : (
          <div className="bg-synq-card/50 border border-yellow-500/30 px-4 py-2 rounded flex items-center gap-3">
            <AlertOctagon className="text-yellow-500" size={20} />
            <div>
              <p className="text-xs text-synq-muted">Schedule Status</p>
              <p className="font-semibold text-yellow-500">No Active Schedule</p>
            </div>
          </div>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard 
          title="Machine Status" 
          value={`${activeMachines} / ${totalMachines}`} 
          subtext="Healthy / Total" 
          icon={<Cpu />} 
          color="text-blue-400"
        />
        <KPICard 
          title="Worker Availability" 
          value={`${availableWorkers} / ${totalWorkers}`} 
          subtext="Available / Total" 
          icon={<Users />} 
          color="text-green-400"
        />
        <KPICard 
          title="Active Orders" 
          value={pendingOrders.toString()} 
          subtext={`${criticalOrders} Critical`} 
          icon={<Package />} 
          color="text-orange-400"
        />
        <KPICard 
          title="Deadline Adherence" 
          value={activeSchedule?.metrics.deadline_adherence != null ? `${activeSchedule.metrics.deadline_adherence}%` : 'N/A'} 
          subtext="Current Schedule" 
          icon={<Target />} 
          color="text-purple-400"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Machine Status Chart */}
        <div className="bg-synq-card rounded-xl border border-synq-border p-4 shadow-lg lg:col-span-1 border-t-4 border-t-synq-primary h-80 flex flex-col">
          <h3 className="font-bold text-lg mb-4">Machine Fleet</h3>
          <div className="flex-1 relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={machineData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {machineData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} stroke="rgba(0,0,0,0.2)" />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }}
                  itemStyle={{ color: '#fff' }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <span className="text-2xl font-bold">{totalMachines}</span>
            </div>
          </div>
          <div className="flex justify-center gap-3 mt-4 text-xs">
             {machineData.map(d => (
               <div key={d.name} className="flex items-center gap-1">
                 <div className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }}></div>
                 <span>{d.name.toLowerCase()}</span>
               </div>
             ))}
          </div>
        </div>

        {/* Priority Orders */}
        <div className="bg-synq-card rounded-xl border border-synq-border p-4 shadow-lg lg:col-span-2 overflow-hidden flex flex-col h-80">
          <h3 className="font-bold text-lg mb-4">Priority Orders</h3>
          <div className="overflow-y-auto pr-2 custom-scrollbar">
            <table className="w-full text-sm text-left">
              <thead className="text-synq-muted border-b border-synq-border uppercase text-[10px]">
                <tr>
                  <th className="pb-2">Order</th>
                  <th className="pb-2">Product</th>
                  <th className="pb-2">Priority</th>
                  <th className="pb-2">Deadline</th>
                  <th className="pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {factory.orders?.slice(0, 10).map(order => (
                  <tr key={order.id} className="border-b border-synq-border/50 hover:bg-white/5 transition-colors">
                    <td className="py-3 font-medium">{order.order_code}</td>
                    <td className="py-3 text-synq-muted">{order.product_name}</td>
                    <td className="py-3"><StatusBadge status={order.priority} /></td>
                    <td className="py-3 text-synq-muted">{new Date(order.deadline).toLocaleDateString()}</td>
                    <td className="py-3"><StatusBadge status={order.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

const KPICard = ({ title, value, subtext, icon, color }: any) => (
  <div className="bg-synq-card rounded-xl border border-synq-border p-5 shadow-lg relative overflow-hidden group hover:border-synq-primary/50 transition-colors">
    <div className={`absolute -right-4 -top-4 w-24 h-24 rounded-full opacity-5 blur-2xl ${color.replace('text', 'bg')}`}></div>
    <div className="flex justify-between items-start">
      <div>
        <p className="text-synq-muted text-sm font-medium mb-1">{title}</p>
        <h4 className="text-3xl font-bold tracking-tight mb-2">{value}</h4>
        <p className="text-xs text-synq-muted flex items-center gap-1">
          {subtext}
        </p>
      </div>
      <div className={`p-3 rounded-lg bg-synq-dark border border-synq-border ${color}`}>
        {icon}
      </div>
    </div>
  </div>
);

export default Dashboard;
