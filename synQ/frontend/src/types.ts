// Frontend Types (synced with backend schemas)

export interface Factory {
  id: number;
  name: string;
  industry: string;
  description: string;
  is_demo: boolean;
  products?: Product[];
  machines?: Machine[];
  workers?: Worker[];
  materials?: Material[];
  orders?: Order[];
}

export interface Product {
  id: number;
  factory_id: number;
  name: string;
  description: string;
}

export interface Machine {
  id: number;
  name: string;
  status: 'AVAILABLE' | 'BUSY' | 'MAINTENANCE' | 'FAILED';
  capacity: number;
  processing_speed: number;
  setup_time: number;
  energy_consumption: number;
  operating_cost: number;
  capabilities: string[];
}

export interface Worker {
  id: number;
  name: string;
  shift: string;
  available: boolean;
  max_overtime_hours: number;
  skills: string[];
}

export interface Material {
  id: number;
  name: string;
  total_quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  reorder_level: number;
  unit_cost: number;
}

export interface Order {
  id: number;
  order_code: string;
  quantity: number;
  priority: 'LOW' | 'NORMAL' | 'HIGH' | 'CRITICAL';
  deadline: string;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'DELAYED' | 'CANCELLED';
  product_name?: string;
  product_id?: number;
}

export interface ScheduleTask {
  id: number;
  schedule_id: number;
  order_id: number;
  order_code: string;
  step_id: number;
  step_name: string;
  machine_id: number;
  machine_name: string;
  worker_id: number | null;
  worker_name: string;
  start_time: number; // minutes from schedule start
  end_time: number; // minutes from schedule start
  status: string;
}

export interface ScheduleMetrics {
  deadline_adherence?: number;
  total_delay?: number;
  delayed_orders?: number;
  estimated_cost?: number;
  machine_utilization?: number;
  worker_utilization?: number;
  energy_impact?: number;
  makespan?: number;
  total_tasks?: number;
  total_orders?: number;
  on_time_orders?: number;
  weighted_score?: number;
}

export interface Schedule {
  id: number;
  factory_id: number;
  name: string;
  status: 'DRAFT' | 'ACTIVE' | 'SUPERSEDED';
  created_at: string;
  is_recovery: boolean;
  metrics: ScheduleMetrics;
  tasks?: ScheduleTask[];
}

export interface Disruption {
  id: number;
  factory_id: number;
  disruption_type: string;
  description: string;
  affected_resource_id: number | null;
  affected_resource_type: string | null;
  parameters: Record<string, any>;
  created_at: string;
  resolved: boolean;
  is_whatif: boolean;
}

export interface RecoveryPlan {
  id: number;
  disruption_id: number;
  name: string;
  strategy: string;
  description: string;
  metrics: ScheduleMetrics;
  is_recommended: boolean;
  is_feasible: boolean;
  infeasibility_reason: string;
  approval_status: 'PENDING' | 'APPROVED' | 'MODIFIED' | 'REJECTED';
  schedule_data: any[];
}

export interface ImpactAnalysis {
  disruption_id: number;
  disruption_type: string;
  affected_resource: any;
  affected_tasks: any[];
  downstream_tasks: any[];
  affected_orders: any[];
  deadlines_at_risk: any[];
  expected_delay_minutes: number;
  alternative_machines: any[];
  alternative_workers: any[];
  summary: string;
  is_whatif?: boolean;
}

export interface AIChatMessage {
  role: 'user' | 'assistant';
  content: string;
  actions?: any[];
}
