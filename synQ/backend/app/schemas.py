from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class MachineStatusEnum(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"

class OrderPriorityEnum(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class OrderStatusEnum(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"

class DisruptionTypeEnum(str, Enum):
    MACHINE_BREAKDOWN = "MACHINE_BREAKDOWN"
    WORKER_ABSENCE = "WORKER_ABSENCE"
    MATERIAL_SHORTAGE = "MATERIAL_SHORTAGE"
    URGENT_ORDER = "URGENT_ORDER"
    PRIORITY_CHANGE = "PRIORITY_CHANGE"
    MACHINE_CAPACITY_REDUCTION = "MACHINE_CAPACITY_REDUCTION"
    WORKER_AVAILABILITY_CHANGE = "WORKER_AVAILABILITY_CHANGE"


# ─── Factory ─────────────────────────────────────────────────────────────────

class FactoryCreate(BaseModel):
    name: str
    industry: str
    description: str = ""

class FactoryResponse(BaseModel):
    id: int
    name: str
    industry: str
    description: str
    created_at: datetime
    is_demo: bool
    class Config:
        from_attributes = True

class FactoryDetail(FactoryResponse):
    products: List["ProductResponse"] = []
    machines: List["MachineResponse"] = []
    workers: List["WorkerResponse"] = []
    materials: List["MaterialResponse"] = []
    orders: List["OrderResponse"] = []


# ─── Product ──────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str
    description: str = ""

class ProductResponse(BaseModel):
    id: int
    factory_id: int
    name: str
    description: str
    class Config:
        from_attributes = True


# ─── Workflow ─────────────────────────────────────────────────────────────────

class ProductionStepCreate(BaseModel):
    name: str
    required_capability: str
    required_skill: str = ""
    processing_duration: float
    setup_duration: float = 0
    priority: int = 0
    material_requirements: List[Dict[str, Any]] = []
    preceding_steps: List[int] = []

class ProductionStepResponse(BaseModel):
    id: int
    workflow_id: int
    name: str
    required_capability: str
    required_skill: str
    processing_duration: float
    setup_duration: float
    priority: int
    material_requirements: List[Dict[str, Any]]
    preceding_steps: List[int]
    class Config:
        from_attributes = True

class WorkflowCreate(BaseModel):
    product_id: int
    name: str
    description: str = ""
    steps: List[ProductionStepCreate] = []

class WorkflowResponse(BaseModel):
    id: int
    product_id: int
    name: str
    description: str
    steps: List[ProductionStepResponse] = []
    class Config:
        from_attributes = True


# ─── Machine ──────────────────────────────────────────────────────────────────

class MachineCreate(BaseModel):
    name: str
    status: MachineStatusEnum = MachineStatusEnum.AVAILABLE
    capacity: int = 1
    processing_speed: float = 1.0
    setup_time: float = 0
    energy_consumption: float = 0
    operating_cost: float = 0
    capabilities: List[str] = []

class MachineResponse(BaseModel):
    id: int
    factory_id: int
    name: str
    status: str
    capacity: int
    processing_speed: float
    setup_time: float
    energy_consumption: float
    operating_cost: float
    capabilities: List[str] = []
    class Config:
        from_attributes = True


# ─── Worker ───────────────────────────────────────────────────────────────────

class WorkerCreate(BaseModel):
    name: str
    shift: str = "DAY"
    available: bool = True
    max_overtime_hours: float = 0
    skills: List[str] = []

class WorkerResponse(BaseModel):
    id: int
    factory_id: int
    name: str
    shift: str
    available: bool
    max_overtime_hours: float
    skills: List[str] = []
    class Config:
        from_attributes = True


# ─── Material ─────────────────────────────────────────────────────────────────

class MaterialCreate(BaseModel):
    name: str
    total_quantity: float = 0
    reserved_quantity: float = 0
    reorder_level: float = 0
    unit_cost: float = 0

class MaterialResponse(BaseModel):
    id: int
    factory_id: int
    name: str
    total_quantity: float
    reserved_quantity: float
    available_quantity: float = 0
    reorder_level: float
    unit_cost: float
    class Config:
        from_attributes = True


# ─── Order ────────────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    product_id: int
    order_code: str
    quantity: int
    priority: OrderPriorityEnum = OrderPriorityEnum.NORMAL
    deadline: datetime
    status: OrderStatusEnum = OrderStatusEnum.PENDING

class OrderResponse(BaseModel):
    id: int
    factory_id: int
    product_id: int
    order_code: str
    quantity: int
    priority: str
    deadline: datetime
    status: str
    product_name: str = ""
    class Config:
        from_attributes = True


# ─── Schedule ─────────────────────────────────────────────────────────────────

class ScheduleTaskResponse(BaseModel):
    id: int
    schedule_id: int
    order_id: int
    step_id: int
    machine_id: int
    worker_id: Optional[int] = None
    start_time: float
    end_time: float
    status: str
    order_code: str = ""
    step_name: str = ""
    machine_name: str = ""
    worker_name: str = ""
    class Config:
        from_attributes = True

class ScheduleResponse(BaseModel):
    id: int
    factory_id: int
    name: str
    status: str
    created_at: datetime
    is_recovery: bool
    metrics: Dict[str, Any] = {}
    tasks: List[ScheduleTaskResponse] = []
    class Config:
        from_attributes = True


# ─── Disruption ───────────────────────────────────────────────────────────────

class DisruptionCreate(BaseModel):
    disruption_type: DisruptionTypeEnum
    description: str = ""
    affected_resource_id: Optional[int] = None
    affected_resource_type: Optional[str] = None
    parameters: Dict[str, Any] = {}
    is_whatif: bool = False

class DisruptionResponse(BaseModel):
    id: int
    factory_id: int
    disruption_type: str
    description: str
    affected_resource_id: Optional[int]
    affected_resource_type: Optional[str]
    parameters: Dict[str, Any]
    created_at: datetime
    resolved: bool
    is_whatif: bool
    class Config:
        from_attributes = True


# ─── Impact Analysis ─────────────────────────────────────────────────────────

class ImpactAnalysis(BaseModel):
    disruption_id: int
    affected_resource: Dict[str, Any] = {}
    affected_tasks: List[Dict[str, Any]] = []
    downstream_tasks: List[Dict[str, Any]] = []
    affected_orders: List[Dict[str, Any]] = []
    deadlines_at_risk: List[Dict[str, Any]] = []
    expected_delay_minutes: float = 0
    alternative_machines: List[Dict[str, Any]] = []
    alternative_workers: List[Dict[str, Any]] = []
    material_impact: List[Dict[str, Any]] = []
    summary: str = ""


# ─── Recovery Plan ────────────────────────────────────────────────────────────

class RecoveryPlanResponse(BaseModel):
    id: int
    disruption_id: int
    name: str
    strategy: str
    description: str
    metrics: Dict[str, Any] = {}
    is_recommended: bool
    is_feasible: bool
    infeasibility_reason: str = ""
    approval_status: str
    schedule_data: List[Dict[str, Any]] = []
    class Config:
        from_attributes = True

class PriorityWeights(BaseModel):
    deadline: float = 80
    cost: float = 60
    delay: float = 70
    utilization: float = 50
    energy: float = 40


class RecoveryPlanModify(BaseModel):
    """
    Manager modification of a recovery plan before approval. Any additional
    machines/workers to exclude beyond what the disruption itself excluded, and
    any order priority overrides, are merged with the plan's original strategy
    and the plan is regenerated + re-validated. Nothing is approved/applied by
    this call — it only updates the draft plan so it can then be approved.
    """
    additional_excluded_machine_ids: List[int] = []
    additional_excluded_worker_ids: List[int] = []
    order_priority_overrides: Dict[int, OrderPriorityEnum] = {}


# ─── Audit ────────────────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: int
    factory_id: int
    event_type: str
    title: str
    details: Dict[str, Any]
    created_at: datetime
    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    id: int
    factory_id: int
    title: str
    message: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    read: bool
    created_at: datetime
    class Config:
        from_attributes = True


# ─── AI ───────────────────────────────────────────────────────────────────────

class AIMessage(BaseModel):
    message: str
    factory_id: int

class AIResponse(BaseModel):
    response: str
    actions: List[Dict[str, Any]] = []
    structured_data: Dict[str, Any] = {}


# ─── Bulk Factory Creation ───────────────────────────────────────────────────

class BulkFactoryCreate(BaseModel):
    factory: FactoryCreate
    products: List[ProductCreate] = []
    machines: List[MachineCreate] = []
    workers: List[WorkerCreate] = []
    materials: List[MaterialCreate] = []
    workflows: List[Dict[str, Any]] = []
    orders: List[Dict[str, Any]] = []
