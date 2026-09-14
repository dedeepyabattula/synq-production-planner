import axios from 'axios';
import { Factory, Schedule, ImpactAnalysis } from './types';

// In production, set VITE_API_URL to the deployed backend's URL
// (e.g. https://your-backend.onrender.com/api). Falls back to localhost for
// local development.
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
});

export const factoryService = {
  getFactories: async () => {
    const res = await api.get<Factory[]>('/factories');
    return res.data;
  },
  getFactory: async (id: number) => {
    const res = await api.get<Factory>(`/factories/${id}`);
    return res.data;
  },
  // We'll primarily rely on backend seed data for the demo
};

export const scheduleService = {
  getActiveSchedule: async (factoryId: number) => {
    const res = await api.get<Schedule>(`/factories/${factoryId}/schedules/active`);
    return res.data;
  },
  generateSchedule: async (factoryId: number) => {
    const res = await api.post<Schedule>(`/factories/${factoryId}/schedules/generate`);
    return res.data;
  }
};

export const disruptionService = {
  createDisruption: async (factoryId: number, disruptionData: any) => {
    const res = await api.post(`/factories/${factoryId}/disruptions`, disruptionData);
    return res.data; // { disruption, impact }
  },
  getImpact: async (factoryId: number, disruptionId: number) => {
    const res = await api.get<ImpactAnalysis>(`/factories/${factoryId}/disruptions/${disruptionId}/impact`);
    return res.data;
  },
  generateRecoveryPlans: async (factoryId: number, disruptionId: number, weights: any) => {
    const res = await api.post(`/factories/${factoryId}/disruptions/${disruptionId}/recover`, weights);
    return res.data;
  },
  reweightPlans: async (factoryId: number, disruptionId: number, weights: any) => {
    // Re-scores already-generated plans against new weights without
    // regenerating candidate schedules (cheap, and doesn't disturb any
    // manager modifications already made to a draft plan).
    const res = await api.post(`/factories/${factoryId}/disruptions/${disruptionId}/reweight`, weights);
    return res.data;
  },
  approvePlan: async (planId: number) => {
    const res = await api.post(`/recovery-plans/${planId}/approve`);
    return res.data;
  },
  rejectPlan: async (planId: number) => {
    const res = await api.post(`/recovery-plans/${planId}/reject`);
    return res.data;
  },
  modifyPlan: async (planId: number, modifications: {
    additional_excluded_machine_ids?: number[];
    additional_excluded_worker_ids?: number[];
    order_priority_overrides?: Record<number, string>;
  }) => {
    const res = await api.post(`/recovery-plans/${planId}/modify`, modifications);
    return res.data;
  },
};

export const aiService = {
  chat: async (factoryId: number, message: string) => {
    const res = await api.post(`/factories/${factoryId}/ai/chat`, { message, factory_id: factoryId });
    return res.data;
  },
  parseFactorySetup: async (description: string) => {
    const res = await api.post(`/ai/parse-factory`, { description });
    return res.data;
  },
};

export const factoryBuilderService = {
  createFactoryBulk: async (draft: any) => {
    const res = await api.post(`/factories/bulk`, draft);
    return res.data;
  },
  addMachine: async (factoryId: number, machine: any) => {
    const res = await api.post(`/factories/${factoryId}/machines`, machine);
    return res.data;
  },
  addWorker: async (factoryId: number, worker: any) => {
    const res = await api.post(`/factories/${factoryId}/workers`, worker);
    return res.data;
  },
  addMaterial: async (factoryId: number, material: any) => {
    const res = await api.post(`/factories/${factoryId}/materials`, material);
    return res.data;
  },
  addOrder: async (factoryId: number, order: any) => {
    const res = await api.post(`/factories/${factoryId}/orders`, order);
    return res.data;
  },
};

export default api;
