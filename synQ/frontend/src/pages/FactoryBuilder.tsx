import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { factoryService, aiService, factoryBuilderService } from '../api';
import { Factory } from '../types';
import { Factory as FactoryIcon, Cpu, Users, Box, GitMerge, Sparkles, PenLine, Plus, Trash2, CheckCircle2 } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';

interface FactoryBuilderProps {
  factoryId: number;
  createMode?: boolean;
  onFactoryCreated?: (f: Factory) => void;
}

// ─────────────────────────────────────────────────────────────────────────
// Draft shape used by both the manual and AI-assisted creation flows. It
// mirrors exactly what POST /factories/bulk expects, so both paths funnel
// into the same review screen and the same save call.
// ─────────────────────────────────────────────────────────────────────────
interface DraftMachine { name: string; capabilities: string[]; capacity: number; }
interface DraftWorker { name: string; skills: string[]; hourly_cost: number; }
interface DraftProduct { name: string; description: string; }
interface DraftStep { name: string; required_capability: string; required_skill: string; processing_duration: number; setup_duration: number; preceding_step_indices: number[]; material_requirements: any[]; }
interface DraftWorkflow { product_name: string; name: string; steps: DraftStep[]; }
interface Draft {
  factory: { name: string; industry: string; description: string };
  products: DraftProduct[];
  machines: DraftMachine[];
  workers: DraftWorker[];
  materials: any[];
  workflows: DraftWorkflow[];
  orders: any[];
}

const emptyDraft = (): Draft => ({
  factory: { name: '', industry: '', description: '' },
  products: [],
  machines: [],
  workers: [],
  materials: [],
  workflows: [],
  orders: [],
});

const FactoryBuilder: React.FC<FactoryBuilderProps> = ({ factoryId, createMode, onFactoryCreated }) => {
  const navigate = useNavigate();
  const [factory, setFactory] = useState<Factory | null>(null);
  const [activeTab, setActiveTab] = useState<'machines' | 'workers' | 'products'>('machines');

  useEffect(() => {
    if (!createMode) {
      factoryService.getFactory(factoryId).then(setFactory).catch(console.error);
    }
  }, [factoryId, createMode]);

  if (createMode) {
    return (
      <FactoryCreationFlow
        onCreated={(f) => {
          onFactoryCreated?.(f);
          navigate('/dashboard');
        }}
        onCancel={() => navigate('/dashboard')}
      />
    );
  }

  if (!factory) return <div className="animate-pulse p-6">Loading Configuration...</div>;

  return (
    <div className="max-w-6xl mx-auto space-y-6 h-full flex flex-col">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <FactoryIcon className="text-synq-primary" />
            Factory Configuration
          </h2>
          <p className="text-synq-muted">View factory resources, capabilities, and workflows.</p>
        </div>
        <button
          onClick={() => navigate('/factory-builder/new')}
          className="flex items-center gap-2 bg-synq-primary hover:bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium transition-colors"
        >
          <Plus size={16} /> New Factory
        </button>
      </div>

      <div className="flex gap-4 border-b border-synq-border px-2">
        <TabButton active={activeTab === 'machines'} onClick={() => setActiveTab('machines')} icon={<Cpu size={16}/>} label={`Machines (${factory.machines?.length || 0})`} />
        <TabButton active={activeTab === 'workers'} onClick={() => setActiveTab('workers')} icon={<Users size={16}/>} label={`Workers (${factory.workers?.length || 0})`} />
        <TabButton active={activeTab === 'products'} onClick={() => setActiveTab('products')} icon={<Box size={16}/>} label={`Products (${factory.products?.length || 0})`} />
      </div>

      <div className="flex-1 overflow-y-auto bg-synq-card rounded-xl border border-synq-border p-6 custom-scrollbar">
        {activeTab === 'machines' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {factory.machines?.map(m => (
              <div key={m.id} className="bg-synq-dark border border-synq-border rounded-lg p-4 hover:border-synq-primary/50 transition-colors">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-bold">{m.name}</h4>
                  <StatusBadge status={m.status} />
                </div>
                <div className="text-xs text-synq-muted space-y-1 mb-3">
                  <p>Processing Speed: {m.processing_speed.toFixed(1)}x</p>
                  <p>Setup Time: {m.setup_time} min</p>
                  <p>Operating Cost: ${m.operating_cost}/hr</p>
                  <p>Energy: {m.energy_consumption} kWh</p>
                </div>
                <div className="flex flex-wrap gap-1">
                  {m.capabilities?.map(c => (
                    <span key={c} className="text-[10px] bg-white/5 border border-white/10 px-1.5 py-0.5 rounded">{c}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'workers' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {factory.workers?.map(w => (
              <div key={w.id} className="bg-synq-dark border border-synq-border rounded-lg p-4 hover:border-synq-primary/50 transition-colors">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-bold">{w.name}</h4>
                  <span className={`text-xs px-2 py-0.5 rounded ${w.available ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                    {w.available ? 'Available' : 'Unavailable'}
                  </span>
                </div>
                <div className="text-xs text-synq-muted space-y-1 mb-3">
                  <p>Shift: {w.shift}</p>
                  <p>Max Overtime: {w.max_overtime_hours} hrs</p>
                </div>
                <div className="flex flex-wrap gap-1">
                  {w.skills?.map(s => (
                    <span key={s} className="text-[10px] bg-white/5 border border-white/10 px-1.5 py-0.5 rounded">{s}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'products' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {factory.products?.map(p => (
              <div key={p.id} className="bg-synq-dark border border-synq-border rounded-lg p-5">
                <h4 className="font-bold text-lg text-synq-text">{p.name}</h4>
                <p className="text-sm text-synq-muted mb-4">{p.description}</p>
                
                {/* Normally we'd fetch workflows for product here, simplified for demo */}
                <div className="flex items-center gap-2 text-synq-muted text-sm bg-white/5 p-2 rounded">
                  <GitMerge size={16} />
                  <span>Configured via API</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────
// Creation flow: choose Manual or AI-Assisted, build a Draft, review it,
// then explicitly confirm before it's ever saved. Nothing is written to the
// factory until "Create Factory" is clicked on the review screen.
// ─────────────────────────────────────────────────────────────────────────
const FactoryCreationFlow: React.FC<{ onCreated: (f: Factory) => void; onCancel: () => void }> = ({ onCreated, onCancel }) => {
  const [mode, setMode] = useState<'choose' | 'manual' | 'ai' | 'review'>('choose');
  const [draft, setDraft] = useState<Draft>(emptyDraft());
  const [aiText, setAiText] = useState('');
  const [aiSource, setAiSource] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAiParse = async () => {
    if (!aiText.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await aiService.parseFactorySetup(aiText);
      const { _source, ...rest } = result;
      setAiSource(_source || null);
      setDraft({ ...emptyDraft(), ...rest });
      setMode('review');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleManualStart = () => {
    setDraft(emptyDraft());
    setMode('manual');
  };

  const handleSave = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await factoryBuilderService.createFactoryBulk(draft);
      // Backend returns { id, name, message } — fetch the full factory record
      const created = await factoryService.getFactory(result.id);
      onCreated(created);
    } catch (err: any) {
      setError(err.response?.data?.detail?.message || err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <FactoryIcon className="text-synq-primary" />
            New Factory
          </h2>
          <p className="text-synq-muted">Configure any factory — industry, products, workflows, machines, and workers are all yours to define.</p>
        </div>
        <button onClick={onCancel} className="text-sm text-synq-muted hover:text-synq-text">Cancel</button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-300 text-sm rounded-lg px-4 py-3">{error}</div>
      )}

      {mode === 'choose' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button
            onClick={() => setMode('ai')}
            className="bg-synq-card border border-synq-border hover:border-synq-primary rounded-xl p-6 text-left transition-colors"
          >
            <Sparkles className="text-synq-accent mb-3" size={24} />
            <h3 className="font-bold text-lg mb-1">AI-Assisted Setup</h3>
            <p className="text-sm text-synq-muted">Describe your factory in plain language. AI converts it into structured, editable data — you review everything before it's saved.</p>
          </button>
          <button
            onClick={handleManualStart}
            className="bg-synq-card border border-synq-border hover:border-synq-primary rounded-xl p-6 text-left transition-colors"
          >
            <PenLine className="text-synq-primary mb-3" size={24} />
            <h3 className="font-bold text-lg mb-1">Manual Setup</h3>
            <p className="text-sm text-synq-muted">Build the factory yourself: name, products, machines, and workers.</p>
          </button>
        </div>
      )}

      {mode === 'ai' && (
        <div className="bg-synq-card border border-synq-border rounded-xl p-6 space-y-4">
          <label className="text-sm font-medium text-synq-text">Describe your factory</label>
          <textarea
            value={aiText}
            onChange={(e) => setAiText(e.target.value)}
            rows={5}
            placeholder='e.g. "I run a furniture factory producing tables and chairs. We have 3 cutting machines and 2 assembly machines."'
            className="w-full bg-synq-dark border border-synq-border rounded-lg p-3 text-sm focus:outline-none focus:border-synq-primary"
          />
          <div className="flex gap-2">
            <button
              onClick={handleAiParse}
              disabled={loading || !aiText.trim()}
              className="bg-synq-primary hover:bg-blue-600 disabled:opacity-40 text-white px-4 py-2 rounded text-sm font-medium transition-colors"
            >
              {loading ? 'Parsing...' : 'Parse with AI'}
            </button>
            <button onClick={() => setMode('choose')} className="text-sm text-synq-muted hover:text-synq-text px-4 py-2">Back</button>
          </div>
        </div>
      )}

      {mode === 'manual' && (
        <ManualDraftEditor draft={draft} setDraft={setDraft} onNext={() => setMode('review')} onBack={() => setMode('choose')} />
      )}

      {mode === 'review' && (
        <DraftReview
          draft={draft}
          setDraft={setDraft}
          aiSource={aiSource}
          loading={loading}
          onBack={() => setMode('choose')}
          onSave={handleSave}
        />
      )}
    </div>
  );
};

// Minimal manual builder: factory info + add machines/workers/products inline.
// This produces the same Draft shape the AI path does, and both land on the
// same review screen before saving.
const ManualDraftEditor: React.FC<{ draft: Draft; setDraft: (d: Draft) => void; onNext: () => void; onBack: () => void }> = ({ draft, setDraft, onNext, onBack }) => {
  const [newMachine, setNewMachine] = useState({ name: '', capability: '', capacity: 1 });
  const [newWorker, setNewWorker] = useState({ name: '', skill: '', hourly_cost: 20 });
  const [newProduct, setNewProduct] = useState('');

  const addMachine = () => {
    if (!newMachine.name || !newMachine.capability) return;
    setDraft({
      ...draft,
      machines: [...draft.machines, { name: newMachine.name, capabilities: [newMachine.capability], capacity: newMachine.capacity }],
    });
    setNewMachine({ name: '', capability: '', capacity: 1 });
  };

  const addWorker = () => {
    if (!newWorker.name || !newWorker.skill) return;
    setDraft({
      ...draft,
      workers: [...draft.workers, { name: newWorker.name, skills: [newWorker.skill], hourly_cost: newWorker.hourly_cost }],
    });
    setNewWorker({ name: '', skill: '', hourly_cost: 20 });
  };

  const addProduct = () => {
    if (!newProduct.trim()) return;
    setDraft({ ...draft, products: [...draft.products, { name: newProduct.trim(), description: '' }] });
    setNewProduct('');
  };

  const canProceed = draft.factory.name.trim() && draft.machines.length > 0 && draft.products.length > 0;

  return (
    <div className="bg-synq-card border border-synq-border rounded-xl p-6 space-y-6">
      <div>
        <label className="text-sm font-medium text-synq-text">Factory Name</label>
        <input
          value={draft.factory.name}
          onChange={(e) => setDraft({ ...draft, factory: { ...draft.factory, name: e.target.value } })}
          className="w-full mt-1 bg-synq-dark border border-synq-border rounded-lg p-2 text-sm focus:outline-none focus:border-synq-primary"
          placeholder="e.g. Riverside Metal Works"
        />
      </div>
      <div>
        <label className="text-sm font-medium text-synq-text">Industry</label>
        <input
          value={draft.factory.industry}
          onChange={(e) => setDraft({ ...draft, factory: { ...draft.factory, industry: e.target.value } })}
          className="w-full mt-1 bg-synq-dark border border-synq-border rounded-lg p-2 text-sm focus:outline-none focus:border-synq-primary"
          placeholder="e.g. Metal Fabrication"
        />
      </div>

      {/* Products */}
      <div>
        <label className="text-sm font-medium text-synq-text">Products</label>
        <div className="flex flex-wrap gap-2 mt-2 mb-2">
          {draft.products.map((p, i) => (
            <span key={i} className="text-xs bg-synq-dark border border-synq-border px-2 py-1 rounded flex items-center gap-1">
              {p.name}
              <Trash2 size={12} className="cursor-pointer text-red-400" onClick={() => setDraft({ ...draft, products: draft.products.filter((_, idx) => idx !== i) })} />
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input value={newProduct} onChange={(e) => setNewProduct(e.target.value)} placeholder="Product name" className="flex-1 bg-synq-dark border border-synq-border rounded-lg p-2 text-sm focus:outline-none focus:border-synq-primary" />
          <button onClick={addProduct} className="bg-synq-dark border border-synq-border hover:border-synq-primary px-3 rounded text-sm">Add</button>
        </div>
      </div>

      {/* Machines */}
      <div>
        <label className="text-sm font-medium text-synq-text">Machines</label>
        <div className="space-y-1 mt-2 mb-2">
          {draft.machines.map((m, i) => (
            <div key={i} className="text-xs bg-synq-dark border border-synq-border px-2 py-1.5 rounded flex justify-between items-center">
              <span>{m.name} — capability: {m.capabilities.join(', ')}</span>
              <Trash2 size={12} className="cursor-pointer text-red-400" onClick={() => setDraft({ ...draft, machines: draft.machines.filter((_, idx) => idx !== i) })} />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2">
          <input value={newMachine.name} onChange={(e) => setNewMachine({ ...newMachine, name: e.target.value })} placeholder="Machine name" className="bg-synq-dark border border-synq-border rounded-lg p-2 text-sm focus:outline-none focus:border-synq-primary" />
          <input value={newMachine.capability} onChange={(e) => setNewMachine({ ...newMachine, capability: e.target.value })} placeholder="Capability (e.g. cutting)" className="bg-synq-dark border border-synq-border rounded-lg p-2 text-sm focus:outline-none focus:border-synq-primary" />
          <button onClick={addMachine} className="bg-synq-dark border border-synq-border hover:border-synq-primary rounded text-sm">Add Machine</button>
        </div>
      </div>

      {/* Workers */}
      <div>
        <label className="text-sm font-medium text-synq-text">Workers</label>
        <div className="space-y-1 mt-2 mb-2">
          {draft.workers.map((w, i) => (
            <div key={i} className="text-xs bg-synq-dark border border-synq-border px-2 py-1.5 rounded flex justify-between items-center">
              <span>{w.name} — skill: {w.skills.join(', ')}</span>
              <Trash2 size={12} className="cursor-pointer text-red-400" onClick={() => setDraft({ ...draft, workers: draft.workers.filter((_, idx) => idx !== i) })} />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2">
          <input value={newWorker.name} onChange={(e) => setNewWorker({ ...newWorker, name: e.target.value })} placeholder="Worker name" className="bg-synq-dark border border-synq-border rounded-lg p-2 text-sm focus:outline-none focus:border-synq-primary" />
          <input value={newWorker.skill} onChange={(e) => setNewWorker({ ...newWorker, skill: e.target.value })} placeholder="Skill (matches a capability)" className="bg-synq-dark border border-synq-border rounded-lg p-2 text-sm focus:outline-none focus:border-synq-primary" />
          <button onClick={addWorker} className="bg-synq-dark border border-synq-border hover:border-synq-primary rounded text-sm">Add Worker</button>
        </div>
      </div>

      <p className="text-xs text-synq-muted">
        Production workflows will be generated as one linear step per distinct machine capability, in the order you added machines — you can review (and later refine) this on the next screen.
      </p>

      <div className="flex gap-2 pt-2">
        <button
          onClick={() => {
            // Build a simple linear workflow per product from the capabilities entered,
            // mirroring what the AI-assisted path produces, so both flows are consistent.
            const caps = Array.from(new Set(draft.machines.map(m => m.capabilities[0]).filter(Boolean)));
            const workflows: DraftWorkflow[] = draft.products.map(p => ({
              product_name: p.name,
              name: `${p.name} Production`,
              steps: caps.map((cap, i) => ({
                name: `${cap} Step`,
                required_capability: cap,
                required_skill: cap,
                processing_duration: 30,
                setup_duration: 10,
                material_requirements: [],
                preceding_step_indices: i > 0 ? [i - 1] : [],
              })),
            }));
            setDraft({ ...draft, workflows });
            onNext();
          }}
          disabled={!canProceed}
          className="bg-synq-primary hover:bg-blue-600 disabled:opacity-40 text-white px-4 py-2 rounded text-sm font-medium transition-colors"
        >
          Review Draft
        </button>
        <button onClick={onBack} className="text-sm text-synq-muted hover:text-synq-text px-4 py-2">Back</button>
      </div>
      {!canProceed && <p className="text-xs text-synq-muted">Add a factory name, at least one product, and at least one machine to continue.</p>}
    </div>
  );
};

// Review screen shared by both creation paths. Nothing is saved until
// "Create Factory" is explicitly clicked here — this is the mandatory
// human-review step for AI-generated data.
const DraftReview: React.FC<{
  draft: Draft; setDraft: (d: Draft) => void; aiSource: string | null; loading: boolean;
  onBack: () => void; onSave: () => void;
}> = ({ draft, setDraft, aiSource, loading, onBack, onSave }) => {
  return (
    <div className="bg-synq-card border border-synq-border rounded-xl p-6 space-y-5">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="text-synq-accent" size={20} />
        <h3 className="font-bold text-lg">Review before saving</h3>
      </div>
      {aiSource && (
        <p className="text-xs text-synq-muted">
          Generated {aiSource === 'ai' ? 'by AI' : 'by the deterministic parser (no AI key configured)'} from your description — check it over, nothing is saved yet.
        </p>
      )}

      <div>
        <label className="text-xs uppercase tracking-wider text-synq-muted">Factory Name</label>
        <input
          value={draft.factory.name}
          onChange={(e) => setDraft({ ...draft, factory: { ...draft.factory, name: e.target.value } })}
          className="w-full mt-1 bg-synq-dark border border-synq-border rounded-lg p-2 text-sm"
        />
      </div>
      <div>
        <label className="text-xs uppercase tracking-wider text-synq-muted">Industry</label>
        <input
          value={draft.factory.industry}
          onChange={(e) => setDraft({ ...draft, factory: { ...draft.factory, industry: e.target.value } })}
          className="w-full mt-1 bg-synq-dark border border-synq-border rounded-lg p-2 text-sm"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <h4 className="text-xs uppercase tracking-wider text-synq-muted mb-2">Products ({draft.products.length})</h4>
          <ul className="text-sm space-y-1">
            {draft.products.map((p, i) => <li key={i} className="bg-synq-dark border border-synq-border rounded px-2 py-1">{p.name}</li>)}
          </ul>
        </div>
        <div>
          <h4 className="text-xs uppercase tracking-wider text-synq-muted mb-2">Machines ({draft.machines.length})</h4>
          <ul className="text-sm space-y-1">
            {draft.machines.map((m, i) => <li key={i} className="bg-synq-dark border border-synq-border rounded px-2 py-1">{m.name} <span className="text-synq-muted">({m.capabilities.join(', ')})</span></li>)}
          </ul>
        </div>
        <div>
          <h4 className="text-xs uppercase tracking-wider text-synq-muted mb-2">Workers ({draft.workers.length})</h4>
          <ul className="text-sm space-y-1">
            {draft.workers.map((w, i) => <li key={i} className="bg-synq-dark border border-synq-border rounded px-2 py-1">{w.name} <span className="text-synq-muted">({w.skills.join(', ')})</span></li>)}
          </ul>
        </div>
      </div>

      <div>
        <h4 className="text-xs uppercase tracking-wider text-synq-muted mb-2">Workflows ({draft.workflows.length})</h4>
        <div className="space-y-2">
          {draft.workflows.map((wf, i) => (
            <div key={i} className="bg-synq-dark border border-synq-border rounded p-2 text-sm">
              <span className="font-medium">{wf.name}</span>
              <span className="text-synq-muted"> — {wf.steps.map(s => s.name).join(' → ')}</span>
            </div>
          ))}
          {draft.workflows.length === 0 && <p className="text-xs text-synq-muted">No workflows yet — add machines/products with matching capabilities first.</p>}
        </div>
      </div>

      {draft.workers.length === 0 && (
        <p className="text-xs text-yellow-400">No workers added — steps requiring a worker skill won't be schedulable until you add one from Factory Configuration after creating.</p>
      )}

      <div className="flex gap-2 pt-2 border-t border-synq-border">
        <button
          onClick={onSave}
          disabled={loading || !draft.factory.name.trim()}
          className="bg-synq-primary hover:bg-blue-600 disabled:opacity-40 text-white px-5 py-2 rounded text-sm font-medium transition-colors"
        >
          {loading ? 'Creating...' : 'Create Factory'}
        </button>
        <button onClick={onBack} className="text-sm text-synq-muted hover:text-synq-text px-4 py-2">Start Over</button>
      </div>
    </div>
  );
};

const TabButton = ({ active, onClick, icon, label }: any) => (
  <button 
    onClick={onClick}
    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
      active ? 'border-synq-primary text-synq-text' : 'border-transparent text-synq-muted hover:text-synq-text hover:border-synq-border'
    }`}
  >
    {icon} 
    {label}
  </button>
);

export default FactoryBuilder;
