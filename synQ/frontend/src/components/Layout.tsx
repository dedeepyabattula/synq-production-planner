import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, Factory as FactoryIcon, CalendarDays, 
  AlertTriangle, ShieldCheck, CheckSquare, History,
  Settings, User, ChevronDown, Plus
} from 'lucide-react';
import { Factory } from '../types';
import { factoryService } from '../api';
import AIChat from './AIChat';

interface LayoutProps {
  children: React.ReactNode;
  factory: Factory | null;
  onFactoryChange: (f: Factory) => void;
}

const Layout: React.FC<LayoutProps> = ({ children, factory, onFactoryChange }) => {
  const [factories, setFactories] = useState<Factory[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    factoryService.getFactories().then(setFactories).catch(console.error);
  }, [factory]);

  const navItems = [
    { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
    { to: "/factory-builder", icon: FactoryIcon, label: "Factory Builder" },
    { to: "/schedule", icon: CalendarDays, label: "Production Schedule" },
    { to: "/disruption", icon: AlertTriangle, label: "Disruption Simulator" },
    { to: "/recovery", icon: ShieldCheck, label: "Recovery Center" },
    { to: "/approval", icon: CheckSquare, label: "Approval Center" },
    { to: "/history", icon: History, label: "History" },
  ];

  return (
    <div className="flex h-screen bg-synq-dark text-synq-text overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-synq-card border-r border-synq-border flex flex-col z-20">
        <div className="p-4 border-b border-synq-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded bg-synq-primary flex items-center justify-center font-bold text-lg">
              S
            </div>
            <div>
              <h1 className="font-bold text-xl tracking-wide">SynQ</h1>
              <p className="text-[10px] text-synq-muted uppercase tracking-widest">Ops Platform</p>
            </div>
          </div>
        </div>

        {/* Factory Selector */}
        <div className="p-4 border-b border-synq-border relative">
          <button 
            className="w-full flex items-center justify-between bg-synq-dark p-2 rounded border border-synq-border hover:border-synq-primary transition-colors text-sm"
            onClick={() => setDropdownOpen(!dropdownOpen)}
          >
            <span className="truncate pr-2 font-medium">
              {factory ? factory.name : "Select Factory"}
            </span>
            <ChevronDown size={14} className="text-synq-muted flex-shrink-0" />
          </button>
          
          {dropdownOpen && (
            <div className="absolute top-full left-4 right-4 mt-1 bg-synq-dark border border-synq-border rounded shadow-lg z-50">
              {factories.map(f => (
                <button
                  key={f.id}
                  className="w-full text-left p-2 text-sm hover:bg-synq-card transition-colors first:rounded-t last:rounded-b"
                  onClick={() => {
                    onFactoryChange(f);
                    setDropdownOpen(false);
                  }}
                >
                  {f.name}
                  {f.is_demo && <span className="ml-2 text-[10px] bg-synq-accent/20 text-synq-accent px-1.5 py-0.5 rounded">DEMO</span>}
                </button>
              ))}
              <button
                className="w-full text-left p-2 text-sm hover:bg-synq-card transition-colors border-t border-synq-border text-synq-primary flex items-center gap-1.5 first:rounded-t last:rounded-b"
                onClick={() => {
                  setDropdownOpen(false);
                  navigate('/factory-builder/new');
                }}
              >
                <Plus size={14} /> New Factory
              </button>
            </div>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => 
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive 
                    ? 'bg-synq-primary/10 text-synq-primary font-medium' 
                    : 'text-synq-muted hover:bg-synq-border hover:text-synq-text'
                }`
              }
            >
              <item.icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-synq-border flex items-center justify-between text-sm text-synq-muted">
          <div className="flex items-center gap-2 cursor-pointer hover:text-synq-text">
            <User size={16} />
            <span>Admin User</span>
          </div>
          <Settings size={16} className="cursor-pointer hover:text-synq-text" />
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <header className="h-14 border-b border-synq-border bg-synq-dark/80 backdrop-blur flex items-center px-6 z-10">
          <p className="text-sm text-synq-muted italic">"The factory changes. The plan adapts."</p>
        </header>
        <div className="flex-1 overflow-y-auto p-6 scroll-smooth relative">
          {children}
        </div>
      </main>

      {/* AI Assistant Overlay */}
      {factory && <AIChat factoryId={factory.id} />}
    </div>
  );
};

export default Layout;
