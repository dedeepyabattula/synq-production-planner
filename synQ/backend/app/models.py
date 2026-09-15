 # per hour
    # Configured repair time for this machine, used by the "repair" recovery
    # strategy when a breakdown disruption has Models.py
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, Boolean, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base


# ─── Enums ────────────────────────────────────────────────────────────────────

class MachineStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"


class OrderPriority(str, enum.Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"


class ScheduleStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DISRUPTED = "DISRUPTED"
    RESCHEDULED = "RESCHEDULED"


class DisruptionType(str, enum.Enum):
    MACHINE_BREAKDOWN = "MACHINE_BREAKDOWN"
    WORKER_ABSENCE = "WORKER_ABSENCE"
    MATERIAL_SHORTAGE = "MATERIAL_SHORTAGE"
    URGENT_ORDER = "URGENT_ORDER"
    PRIORITY_CHANGE = "PRIORITY_CHANGE"
    MACHINE_CAPACITY_REDUCTION = "MACHINE_CAPACITY_REDUCTION"
    WORKER_AVAILABILITY_CHANGE = "WORKER_AVAILABILITY_CHANGE"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    MODIFIED = "MODIFIED"
    REJECTED = "REJECTED"


# ─── Factory ─────────────────────────────────────────────────────────────────

class Factory(Base):
    __tablename__ = "factories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    industry = Column(String, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_demo = Column(Boolean, default=False)

    products = relationship("Product", back_populates="factory", cascade="all, delete-orphan")
    machines = relationship("Machine", back_populates="factory", cascade="all, delete-orphan")
    workers = relationship("Worker", back_populates="factory", cascade="all, delete-orphan")
    materials = relationship("Material", back_populates="factory", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="factory", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="factory", cascade="all, delete-orphan")
    disruptions = relationship("Disruption", back_populates="factory", cascade="all, delete-orphan")


# ─── Products & Workflows ────────────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, default="")

    factory = relationship("Factory", back_populates="products")
    workflows = relationship("ProductionWorkflow", back_populates="product", cascade="all, delete-orphan")


class ProductionWorkflow(Base):
    __tablename__ = "production_workflows"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, default="")

    product = relationship("Product", back_populates="workflows")
    steps = relationship("ProductionStep", back_populates="workflow", cascade="all, delete-orphan")


class ProductionStep(Base):
    __tablename__ = "production_steps"
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("production_workflows.id"), nullable=False)
    name = Column(String, nullable=False)
    required_capability = Column(String, nullable=False)
    required_skill = Column(String, default="")
    processing_duration = Column(Float, nullable=False)  # minutes
    setup_duration = Column(Float, default=0)  # minutes
    priority = Column(Integer, default=0)
    material_requirements = Column(JSON, default=list)  # [{"material_id": X, "quantity": Y}]
    preceding_steps = Column(JSON, default=list)  # [step_id, ...]

    workflow = relationship("ProductionWorkflow", back_populates="steps")


# ─── Machines ─────────────────────────────────────────────────────────────────

class Machine(Base):
    __tablename__ = "machines"
    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(Enum(MachineStatus), default=MachineStatus.AVAILABLE)
    capacity = Column(Integer, default=1)
    processing_speed = Column(Float, default=1.0)  # multiplier
    setup_time = Column(Float, default=0)  # minutes
    energy_consumption = Column(Float, default=0)  # kWh
        operating_cost = Column(Float, default=0)  # per hour
    # Configured repair time for this machine, used by the "repair" recovery
    # strategy when a breakdown disruption has no alternative capable machine.
    # Nullable: when unset, the repair strategy falls back to the disruption's
    # own duration_hours parameter, and only as a last resort to a documented
    # default (see simulation.py generate_repair_plan).
    repair_duration_minutes = Column(Float, nullable=True)

    factory = relationship("Factory", back_populates="machines")
    capabilities = relationship("MachineCapability", back_populates="machine", cascade="all, delete-orphan")


class MachineCapability(Base):
    __tablename__ = "machine_capabilities"
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    capability = Column(String, nullable=False)

    machine = relationship("Machine", back_populates="capabilities")


# ─── Workers ──────────────────────────────────────────────────────────────────

class Worker(Base):
    __tablename__ = "workers"
    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    name = Column(String, nullable=False)
    shift = Column(String, default="DAY")  # DAY, NIGHT, FLEX
    available = Column(Boolean, default=True)
    max_overtime_hours = Column(Float, default=0)

    factory = relationship("Factory", back_populates="workers")
    skills = relationship("WorkerSkill", back_populates="worker", cascade="all, delete-orphan")


class WorkerSkill(Base):
    __tablename__ = "worker_skills"
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    skill = Column(String, nullable=False)

    worker = relationship("Worker", back_populates="skills")


# ─── Materials ────────────────────────────────────────────────────────────────

class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    name = Column(String, nullable=False)
    total_quantity = Column(Float, default=0)
    reserved_quantity = Column(Float, default=0)
    reorder_level = Column(Float, default=0)
    unit_cost = Column(Float, default=0)

    factory = relationship("Factory", back_populates="materials")

    @property
    def available_quantity(self):
        return self.total_quantity - self.reserved_quantity


# ─── Orders ───────────────────────────────────────────────────────────────────

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    order_code = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    priority = Column(Enum(OrderPriority), default=OrderPriority.NORMAL)
    deadline = Column(DateTime, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

    factory = relationship("Factory", back_populates="orders")
    product = relationship("Product")


# ─── Schedule ─────────────────────────────────────────────────────────────────

class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(Enum(ScheduleStatus), default=ScheduleStatus.DRAFT)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_recovery = Column(Boolean, default=False)
    source_disruption_id = Column(Integer, ForeignKey("disruptions.id"), nullable=True)
    metrics = Column(JSON, default=dict)

    factory = relationship("Factory", back_populates="schedules")
    tasks = relationship("ScheduleTask", back_populates="schedule", cascade="all, delete-orphan")


class ScheduleTask(Base):
    __tablename__ = "schedule_tasks"
    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    step_id = Column(Integer, ForeignKey("production_steps.id"), nullable=False)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=True)
    unit_index = Column(Integer, default=0)  # which unit of order.quantity this task is for
    start_time = Column(Float, nullable=False)  # minutes from schedule start
    end_time = Column(Float, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.SCHEDULED)

    schedule = relationship("Schedule", back_populates="tasks")
    order = relationship("Order")
    step = relationship("ProductionStep")
    machine = relationship("Machine")
    worker = relationship("Worker")


# ─── Disruptions ──────────────────────────────────────────────────────────────

class Disruption(Base):
    __tablename__ = "disruptions"
    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    disruption_type = Column(Enum(DisruptionType), nullable=False)
    description = Column(Text, default="")
    affected_resource_id = Column(Integer, nullable=True)
    affected_resource_type = Column(String, nullable=True)  # "machine", "worker", "material"
    parameters = Column(JSON, default=dict)  # e.g. {"duration_hours": 3, "capacity_reduction": 0.5}
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    is_whatif = Column(Boolean, default=False)

    factory = relationship("Factory", back_populates="disruptions")
    recovery_plans = relationship("RecoveryPlan", back_populates="disruption", cascade="all, delete-orphan")


class RecoveryPlan(Base):
    __tablename__ = "recovery_plans"
    id = Column(Integer, primary_key=True, index=True)
    disruption_id = Column(Integer, ForeignKey("disruptions.id"), nullable=False)
    name = Column(String, nullable=False)
    strategy = Column(String, nullable=False)
    description = Column(Text, default="")
    schedule_data = Column(JSON, default=list)  # serialized schedule tasks
    metrics = Column(JSON, default=dict)
    is_recommended = Column(Boolean, default=False)
    is_feasible = Column(Boolean, default=True)
    infeasibility_reason = Column(Text, default="")
    approval_status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)
    approved_at = Column(DateTime, nullable=True)

    disruption = relationship("Disruption", back_populates="recovery_plans")


# ─── Audit ────────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    event_type = Column(String, nullable=False)  # "disruption", "recovery", "approval", etc.
    title = Column(String, nullable=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    resource_type = Column(String, nullable=True)
    resource_id = Column(Integer, nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
no alternative capable machine.
    # Nullable: when unset, the repair strategy falls back to the disruption's
    # own duration_hours parameter, and only as a last resort to a documented
    # default (see simulation.py generate_repair_plan).
    repair_duration_minutes = Column(Float, nullable=True)

    factory = relationship("Factory", back_populates="machines")
