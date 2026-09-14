"""
SynQ API Routes — All endpoints for factory management,
scheduling, disruption, recovery, and AI.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from app.database import get_db
from app.models import (
    Factory, Product, ProductionWorkflow, ProductionStep,
    Machine, MachineCapability, Worker, WorkerSkill,
    Material, Order, Schedule, ScheduleTask,
    Disruption, RecoveryPlan, AuditLog, Notification,
    MachineStatus, OrderPriority, OrderStatus, ScheduleStatus,
    DisruptionType, ApprovalStatus, TaskStatus
)
from app.schemas import (
    FactoryCreate, FactoryResponse, FactoryDetail,
    ProductCreate, ProductResponse,
    WorkflowCreate, WorkflowResponse, ProductionStepCreate, ProductionStepResponse,
    MachineCreate, MachineResponse,
    WorkerCreate, WorkerResponse,
    MaterialCreate, MaterialResponse,
    OrderCreate, OrderResponse,
    ScheduleResponse, ScheduleTaskResponse,
    DisruptionCreate, DisruptionResponse,
    RecoveryPlanResponse, PriorityWeights, RecoveryPlanModify,
    AuditLogResponse, NotificationResponse,
    AIMessage, AIResponse, ImpactAnalysis,
    BulkFactoryCreate,
)
from app.scheduler import generate_schedule, validate_schedule, recompute_material_reservations
from app.simulation import (
    analyze_impact, generate_recovery_plans,
    apply_recovery_plan, score_and_recommend, modify_recovery_plan
)
from app.agent import process_ai_message, get_factory_summary, parse_factory_setup
from app.seed import seed_all

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORIES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/factories", response_model=List[FactoryResponse])
def list_factories(db: Session = Depends(get_db)):
    return db.query(Factory).all()


@router.get("/factories/{factory_id}")
def get_factory(factory_id: int, db: Session = Depends(get_db)):
    factory = db.query(Factory).filter(Factory.id == factory_id).first()
    if not factory:
        raise HTTPException(404, "Factory not found")

    machines = db.query(Machine).filter(Machine.factory_id == factory_id).all()
    workers = db.query(Worker).filter(Worker.factory_id == factory_id).all()
    materials = db.query(Material).filter(Material.factory_id == factory_id).all()
    orders = db.query(Order).filter(Order.factory_id == factory_id).all()
    products = db.query(Product).filter(Product.factory_id == factory_id).all()

    def machine_to_dict(m):
        return {
            "id": m.id, "factory_id": m.factory_id, "name": m.name,
            "status": m.status.value if hasattr(m.status, 'value') else str(m.status),
            "capacity": m.capacity, "processing_speed": m.processing_speed,
            "setup_time": m.setup_time, "energy_consumption": m.energy_consumption,
            "operating_cost": m.operating_cost,
            "capabilities": [c.capability for c in m.capabilities],
        }

    def worker_to_dict(w):
        return {
            "id": w.id, "factory_id": w.factory_id, "name": w.name,
            "shift": w.shift, "available": w.available,
            "max_overtime_hours": w.max_overtime_hours,
            "skills": [s.skill for s in w.skills],
        }

    def material_to_dict(m):
        return {
            "id": m.id, "factory_id": m.factory_id, "name": m.name,
            "total_quantity": m.total_quantity, "reserved_quantity": m.reserved_quantity,
            "available_quantity": m.total_quantity - m.reserved_quantity,
            "reorder_level": m.reorder_level, "unit_cost": m.unit_cost,
        }

    def order_to_dict(o):
        product = db.query(Product).filter(Product.id == o.product_id).first()
        return {
            "id": o.id, "factory_id": o.factory_id, "product_id": o.product_id,
            "order_code": o.order_code, "quantity": o.quantity,
            "priority": o.priority.value if hasattr(o.priority, 'value') else str(o.priority),
            "deadline": o.deadline.isoformat() if o.deadline else None,
            "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
            "product_name": product.name if product else "",
        }

    return {
        "id": factory.id, "name": factory.name, "industry": factory.industry,
        "description": factory.description, "created_at": factory.created_at.isoformat(),
        "is_demo": factory.is_demo,
        "products": [{"id": p.id, "factory_id": p.factory_id, "name": p.name, "description": p.description} for p in products],
        "machines": [machine_to_dict(m) for m in machines],
        "workers": [worker_to_dict(w) for w in workers],
        "materials": [material_to_dict(m) for m in materials],
        "orders": [order_to_dict(o) for o in orders],
    }


@router.post("/factories", response_model=FactoryResponse)
def create_factory(data: FactoryCreate, db: Session = Depends(get_db)):
    factory = Factory(name=data.name, industry=data.industry, description=data.description)
    db.add(factory)
    db.commit()
    db.refresh(factory)
    return factory


@router.delete("/factories/{factory_id}")
def delete_factory(factory_id: int, db: Session = Depends(get_db)):
    factory = db.query(Factory).filter(Factory.id == factory_id).first()
    if not factory:
        raise HTTPException(404, "Factory not found")
    db.delete(factory)
    db.commit()
    return {"message": "Factory deleted"}


@router.post("/ai/parse-factory")
def ai_parse_factory(payload: Dict[str, str] = Body(...)):
    """
    AI-assisted factory setup: convert a natural-language description into a
    structured DRAFT (same shape /factories/bulk expects). This does NOT save
    anything — the manager reviews/edits the draft in the UI and explicitly
    confirms before POSTing it to /factories/bulk. Falls back to a
    deterministic parser if no AI API key is configured.
    """
    description = (payload.get("description") or "").strip()
    if not description:
        raise HTTPException(400, "description is required")
    draft = parse_factory_setup(description)
    return draft


@router.post("/factories/bulk")
def create_factory_bulk(data: BulkFactoryCreate, db: Session = Depends(get_db)):
    """Create a factory with all resources in one request."""
    factory = Factory(name=data.factory.name, industry=data.factory.industry,
                      description=data.factory.description)
    db.add(factory)
    db.flush()

    # Products
    product_map = {}
    for p in data.products:
        prod = Product(factory_id=factory.id, name=p.name, description=p.description)
        db.add(prod)
        db.flush()
        product_map[p.name] = prod.id

    # Machines
    for m in data.machines:
        machine = Machine(
            factory_id=factory.id, name=m.name,
            status=MachineStatus(m.status) if m.status else MachineStatus.AVAILABLE,
            capacity=m.capacity, processing_speed=m.processing_speed,
            setup_time=m.setup_time, energy_consumption=m.energy_consumption,
            operating_cost=m.operating_cost,
        )
        db.add(machine)
        db.flush()
        for c in m.capabilities:
            db.add(MachineCapability(machine_id=machine.id, capability=c))

    # Workers
    for w in data.workers:
        worker = Worker(
            factory_id=factory.id, name=w.name,
            shift=w.shift, available=w.available,
            max_overtime_hours=w.max_overtime_hours,
        )
        db.add(worker)
        db.flush()
        for s in w.skills:
            db.add(WorkerSkill(worker_id=worker.id, skill=s))

    # Materials
    mat_map = {}
    for m in data.materials:
        material = Material(
            factory_id=factory.id, name=m.name,
            total_quantity=m.total_quantity, reserved_quantity=m.reserved_quantity,
            reorder_level=m.reorder_level, unit_cost=m.unit_cost,
        )
        db.add(material)
        db.flush()
        mat_map[m.name] = material.id

    # Workflows
    for wf_data in data.workflows:
        product_name = wf_data.get("product_name", "")
        product_id = product_map.get(product_name)
        if not product_id:
            continue

        wf = ProductionWorkflow(
            product_id=product_id, name=wf_data.get("name", ""),
            description=wf_data.get("description", ""),
        )
        db.add(wf)
        db.flush()

        step_id_map = {}
        for i, step_data in enumerate(wf_data.get("steps", [])):
            mat_reqs = []
            for mr in step_data.get("material_requirements", []):
                mat_name = mr.get("material_name", "")
                mid = mat_map.get(mat_name)
                if mid:
                    mat_reqs.append({"material_id": mid, "quantity": mr.get("quantity", 0)})

            preceding = []
            for dep_idx in step_data.get("preceding_step_indices", []):
                if dep_idx in step_id_map:
                    preceding.append(step_id_map[dep_idx])

            step = ProductionStep(
                workflow_id=wf.id,
                name=step_data.get("name", f"Step {i+1}"),
                required_capability=step_data.get("required_capability", "general"),
                required_skill=step_data.get("required_skill", ""),
                processing_duration=step_data.get("processing_duration", 30),
                setup_duration=step_data.get("setup_duration", 0),
                material_requirements=mat_reqs,
                preceding_steps=preceding,
            )
            db.add(step)
            db.flush()
            step_id_map[i] = step.id

    # Orders
    for o_data in data.orders:
        product_name = o_data.get("product_name", "")
        product_id = product_map.get(product_name)
        if not product_id:
            continue
        if o_data.get("deadline"):
            deadline = datetime.fromisoformat(o_data["deadline"])
        elif o_data.get("deadline_days_from_now") is not None:
            deadline = datetime.utcnow() + timedelta(days=float(o_data["deadline_days_from_now"]))
        else:
            deadline = datetime.utcnow() + timedelta(days=7)
        order = Order(
            factory_id=factory.id, product_id=product_id,
            order_code=o_data.get("order_code", f"ORD-{factory.id}"),
            quantity=o_data.get("quantity", 1),
            priority=OrderPriority(o_data.get("priority", "NORMAL")),
            deadline=deadline,
            status=OrderStatus.PENDING,
        )
        db.add(order)

    db.commit()
    db.refresh(factory)
    return {"id": factory.id, "name": factory.name, "message": "Factory created successfully"}


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/factories/{factory_id}/products")
def list_products(factory_id: int, db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.factory_id == factory_id).all()
    return [{"id": p.id, "factory_id": p.factory_id, "name": p.name, "description": p.description} for p in products]


@router.post("/factories/{factory_id}/products")
def create_product(factory_id: int, data: ProductCreate, db: Session = Depends(get_db)):
    product = Product(factory_id=factory_id, name=data.name, description=data.description)
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"id": product.id, "factory_id": product.factory_id, "name": product.name, "description": product.description}


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOWS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/factories/{factory_id}/workflows")
def list_workflows(factory_id: int, db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.factory_id == factory_id).all()
    product_ids = [p.id for p in products]
    workflows = db.query(ProductionWorkflow).filter(ProductionWorkflow.product_id.in_(product_ids)).all()
    result = []
    for wf in workflows:
        steps = db.query(ProductionStep).filter(ProductionStep.workflow_id == wf.id).all()
        product = db.query(Product).filter(Product.id == wf.product_id).first()
        result.append({
            "id": wf.id, "product_id": wf.product_id, "name": wf.name,
            "description": wf.description,
            "product_name": product.name if product else "",
            "steps": [{
                "id": s.id, "workflow_id": s.workflow_id, "name": s.name,
                "required_capability": s.required_capability,
                "required_skill": s.required_skill,
                "processing_duration": s.processing_duration,
                "setup_duration": s.setup_duration,
                "priority": s.priority,
                "material_requirements": s.material_requirements or [],
                "preceding_steps": s.preceding_steps or [],
            } for s in steps]
        })
    return result


@router.post("/factories/{factory_id}/workflows")
def create_workflow(factory_id: int, data: WorkflowCreate, db: Session = Depends(get_db)):
    wf = ProductionWorkflow(product_id=data.product_id, name=data.name, description=data.description)
    db.add(wf)
    db.flush()

    step_id_map = {}
    for i, step_data in enumerate(data.steps):
        preceding = []
        for dep_idx in step_data.preceding_steps:
            if dep_idx in step_id_map:
                preceding.append(step_id_map[dep_idx])

        step = ProductionStep(
            workflow_id=wf.id, name=step_data.name,
            required_capability=step_data.required_capability,
            required_skill=step_data.required_skill,
            processing_duration=step_data.processing_duration,
            setup_duration=step_data.setup_duration,
            material_requirements=step_data.material_requirements,
            preceding_steps=preceding,
        )
        db.add(step)
        db.flush()
        step_id_map[i] = step.id

    db.commit()
    return {"id": wf.id, "message": "Workflow created"}


# ═══════════════════════════════════════════════════════════════════════════════
# MACHINES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/factories/{factory_id}/machines")
def list_machines(factory_id: int, db: Session = Depends(get_db)):
    machines = db.query(Machine).filter(Machine.factory_id == factory_id).all()
    return [
        {
            "id": m.id, "factory_id": m.factory_id, "name": m.name,
            "status": m.status.value if hasattr(m.status, 'value') else str(m.status),
            "capacity": m.capacity, "processing_speed": m.processing_speed,
            "setup_time": m.setup_time, "energy_consumption": m.energy_consumption,
            "operating_cost": m.operating_cost,
            "capabilities": [c.capability for c in m.capabilities],
        }
        for m in machines
    ]


@router.post("/factories/{factory_id}/machines")
def create_machine(factory_id: int, data: MachineCreate, db: Session = Depends(get_db)):
    machine = Machine(
        factory_id=factory_id, name=data.name,
        status=MachineStatus(data.status) if data.status else MachineStatus.AVAILABLE,
        capacity=data.capacity, processing_speed=data.processing_speed,
        setup_time=data.setup_time, energy_consumption=data.energy_consumption,
        operating_cost=data.operating_cost,
    )
    db.add(machine)
    db.flush()
    for c in data.capabilities:
        db.add(MachineCapability(machine_id=machine.id, capability=c))
    db.commit()
    db.refresh(machine)
    return {"id": machine.id, "name": machine.name, "message": "Machine created"}


@router.delete("/factories/{factory_id}/machines/{machine_id}")
def delete_machine(factory_id: int, machine_id: int, db: Session = Depends(get_db)):
    machine = db.query(Machine).filter(Machine.id == machine_id, Machine.factory_id == factory_id).first()
    if not machine:
        raise HTTPException(404, "Machine not found")
    db.delete(machine)
    db.commit()
    return {"message": "Machine deleted"}


# ═══════════════════════════════════════════════════════════════════════════════
# WORKERS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/factories/{factory_id}/workers")
def list_workers(factory_id: int, db: Session = Depends(get_db)):
    workers = db.query(Worker).filter(Worker.factory_id == factory_id).all()
    return [
        {
            "id": w.id, "factory_id": w.factory_id, "name": w.name,
            "shift": w.shift, "available": w.available,
            "max_overtime_hours": w.max_overtime_hours,
            "skills": [s.skill for s in w.skills],
        }
        for w in workers
    ]


@router.post("/factories/{factory_id}/workers")
def create_worker(factory_id: int, data: WorkerCreate, db: Session = Depends(get_db)):
    worker = Worker(
        factory_id=factory_id, name=data.name,
        shift=data.shift, available=data.available,
        max_overtime_hours=data.max_overtime_hours,
    )
    db.add(worker)
    db.flush()
    for s in data.skills:
        db.add(WorkerSkill(worker_id=worker.id, skill=s))
    db.commit()
    return {"id": worker.id, "name": worker.name, "message": "Worker created"}


@router.delete("/factories/{factory_id}/workers/{worker_id}")
def delete_worker(factory_id: int, worker_id: int, db: Session = Depends(get_db)):
    worker = db.query(Worker).filter(Worker.id == worker_id, Worker.factory_id == factory_id).first()
    if not worker:
        raise HTTPException(404, "Worker not found")
    db.delete(worker)
    db.commit()
    return {"message": "Worker deleted"}


# ═══════════════════════════════════════════════════════════════════════════════
# MATERIALS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/factories/{factory_id}/materials")
def list_materials(factory_id: int, db: Session = Depends(get_db)):
    materials = db.query(Material).filter(Material.factory_id == factory_id).all()
    return [
        {
            "id": m.id, "factory_id": m.factory_id, "name": m.name,
            "total_quantity": m.total_quantity, "reserved_quantity": m.reserved_quantity,
            "available_quantity": m.total_quantity - m.reserved_quantity,
            "reorder_level": m.reorder_level, "unit_cost": m.unit_cost,
        }
        for m in materials
    ]


@router.post("/factories/{factory_id}/materials")
def create_material(factory_id: int, data: MaterialCreate, db: Session = Depends(get_db)):
    material = Material(
        factory_id=factory_id, name=data.name,
        total_quantity=data.total_quantity, reserved_quantity=data.reserved_quantity,
        reorder_level=data.reorder_level, unit_cost=data.unit_cost,
    )
    db.add(material)
    db.commit()
    return {"id": material.id, "name": material.name, "message": "Material created"}


# ═══════════════════════════════════════════════════════════════════════════════
# ORDERS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/factories/{factory_id}/orders")
def list_orders(factory_id: int, db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.factory_id == factory_id).all()
    result = []
    for o in orders:
        product = db.query(Product).filter(Product.id == o.product_id).first()
        result.append({
            "id": o.id, "factory_id": o.factory_id, "product_id": o.product_id,
            "order_code": o.order_code, "quantity": o.quantity,
            "priority": o.priority.value if hasattr(o.priority, 'value') else str(o.priority),
            "deadline": o.deadline.isoformat() if o.deadline else None,
            "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
            "product_name": product.name if product else "",
        })
    return result


@router.post("/factories/{factory_id}/orders")
def create_order(factory_id: int, data: OrderCreate, db: Session = Depends(get_db)):
    order = Order(
        factory_id=factory_id, product_id=data.product_id,
        order_code=data.order_code, quantity=data.quantity,
        priority=OrderPriority(data.priority),
        deadline=data.deadline, status=OrderStatus.PENDING,
    )
    db.add(order)
    db.commit()
    return {"id": order.id, "order_code": order.order_code, "message": "Order created"}


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/factories/{factory_id}/schedules")
def list_schedules(factory_id: int, db: Session = Depends(get_db)):
    schedules = db.query(Schedule).filter(Schedule.factory_id == factory_id).order_by(Schedule.created_at.desc()).all()
    return [
        {
            "id": s.id, "factory_id": s.factory_id, "name": s.name,
            "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
            "created_at": s.created_at.isoformat(),
            "is_recovery": s.is_recovery, "metrics": s.metrics or {},
        }
        for s in schedules
    ]


@router.get("/factories/{factory_id}/schedules/active")
def get_active_schedule(factory_id: int, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(
        Schedule.factory_id == factory_id,
        Schedule.status == ScheduleStatus.ACTIVE
    ).first()
    if not schedule:
        return {"id": None, "tasks": [], "metrics": {}, "message": "No active schedule"}

    tasks = db.query(ScheduleTask).filter(ScheduleTask.schedule_id == schedule.id).all()
    return {
        "id": schedule.id,
        "name": schedule.name,
        "status": schedule.status.value if hasattr(schedule.status, 'value') else str(schedule.status),
        "created_at": schedule.created_at.isoformat(),
        "is_recovery": schedule.is_recovery,
        "metrics": schedule.metrics or {},
        "tasks": [_task_to_dict(db, t) for t in tasks],
    }


@router.post("/factories/{factory_id}/schedules/generate")
def generate_new_schedule(factory_id: int, db: Session = Depends(get_db)):
    """Generate a new production schedule and set it as active."""
    schedule, errors = generate_schedule(db, factory_id, name="Production Schedule", commit=False)
    if not schedule:
        db.rollback()
        raise HTTPException(400, detail={"message": "Failed to generate schedule", "errors": errors})

    # No invalid schedule may become active: validate constraints before
    # activating, and never activate a schedule that failed to place every step
    # (missing machine/worker/material errors) even if some tasks were created.
    is_valid, validation_errors = validate_schedule(db, schedule.id)
    if errors or not is_valid:
        db.rollback()
        raise HTTPException(400, detail={
            "message": "Generated schedule is not fully feasible and was not activated",
            "errors": errors,
            "validation_errors": validation_errors,
        })

    # Supersede old active schedules only once we know the new one is valid
    old = db.query(Schedule).filter(
        Schedule.factory_id == factory_id,
        Schedule.status == ScheduleStatus.ACTIVE
    ).all()
    for s in old:
        s.status = ScheduleStatus.SUPERSEDED

    schedule.status = ScheduleStatus.ACTIVE
    recompute_material_reservations(db, factory_id)
    db.commit()

    # Add audit log
    audit = AuditLog(
        factory_id=factory_id,
        event_type="schedule_generated",
        title="Production Schedule Generated",
        details={"schedule_id": schedule.id, "metrics": schedule.metrics, "errors": errors}
    )
    db.add(audit)
    db.commit()

    tasks = db.query(ScheduleTask).filter(ScheduleTask.schedule_id == schedule.id).all()
    return {
        "id": schedule.id,
        "name": schedule.name,
        "status": schedule.status.value,
        "metrics": schedule.metrics or {},
        "errors": errors,
        "tasks": [_task_to_dict(db, t) for t in tasks],
    }


def _task_to_dict(db: Session, t: ScheduleTask) -> dict:
    order = db.query(Order).filter(Order.id == t.order_id).first()
    step = db.query(ProductionStep).filter(ProductionStep.id == t.step_id).first()
    machine = db.query(Machine).filter(Machine.id == t.machine_id).first()
    worker = db.query(Worker).filter(Worker.id == t.worker_id).first() if t.worker_id else None
    return {
        "id": t.id, "schedule_id": t.schedule_id,
        "order_id": t.order_id, "step_id": t.step_id,
        "machine_id": t.machine_id, "worker_id": t.worker_id,
        "unit_index": t.unit_index,
        "start_time": t.start_time, "end_time": t.end_time,
        "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
        "order_code": order.order_code if order else "",
        "step_name": step.name if step else "",
        "machine_name": machine.name if machine else "",
        "worker_name": worker.name if worker else "",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DISRUPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/factories/{factory_id}/disruptions")
def list_disruptions(factory_id: int, db: Session = Depends(get_db)):
    disruptions = db.query(Disruption).filter(
        Disruption.factory_id == factory_id
    ).order_by(Disruption.created_at.desc()).all()
    return [
        {
            "id": d.id, "factory_id": d.factory_id,
            "disruption_type": d.disruption_type.value if hasattr(d.disruption_type, 'value') else str(d.disruption_type),
            "description": d.description,
            "affected_resource_id": d.affected_resource_id,
            "affected_resource_type": d.affected_resource_type,
            "parameters": d.parameters or {},
            "created_at": d.created_at.isoformat(),
            "resolved": d.resolved,
            "is_whatif": d.is_whatif,
        }
        for d in disruptions
    ]


@router.post("/factories/{factory_id}/disruptions")
def create_disruption(factory_id: int, data: DisruptionCreate, db: Session = Depends(get_db)):
    """Create a disruption and automatically run impact analysis."""
    disruption = Disruption(
        factory_id=factory_id,
        disruption_type=DisruptionType(data.disruption_type),
        description=data.description,
        affected_resource_id=data.affected_resource_id,
        affected_resource_type=data.affected_resource_type,
        parameters=data.parameters,
        is_whatif=data.is_whatif,
    )
    db.add(disruption)
    db.flush()

    # Audit log
    audit = AuditLog(
        factory_id=factory_id,
        event_type="disruption_created",
        title=f"Disruption: {data.disruption_type.value}",
        details={
            "disruption_id": disruption.id,
            "type": data.disruption_type.value,
            "resource_id": data.affected_resource_id,
            "resource_type": data.affected_resource_type,
            "is_whatif": data.is_whatif,
        }
    )
    db.add(audit)
    db.commit()

    # Run impact analysis
    schedule = db.query(Schedule).filter(
        Schedule.factory_id == factory_id,
        Schedule.status == ScheduleStatus.ACTIVE
    ).first()

    impact = {}
    if schedule:
        impact = analyze_impact(db, disruption, schedule)

    return {
        "disruption": {
            "id": disruption.id,
            "disruption_type": disruption.disruption_type.value,
            "description": disruption.description,
            "affected_resource_id": disruption.affected_resource_id,
            "affected_resource_type": disruption.affected_resource_type,
            "parameters": disruption.parameters,
            "is_whatif": disruption.is_whatif,
        },
        "impact": impact,
    }


@router.get("/factories/{factory_id}/disruptions/{disruption_id}/impact")
def get_disruption_impact(factory_id: int, disruption_id: int, db: Session = Depends(get_db)):
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        raise HTTPException(404, "Disruption not found")

    schedule = db.query(Schedule).filter(
        Schedule.factory_id == factory_id,
        Schedule.status == ScheduleStatus.ACTIVE
    ).first()
    if not schedule:
        raise HTTPException(400, "No active schedule to analyze impact against")

    impact = analyze_impact(db, disruption, schedule)
    impact["is_whatif"] = disruption.is_whatif
    return impact


# ═══════════════════════════════════════════════════════════════════════════════
# RECOVERY
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/factories/{factory_id}/disruptions/{disruption_id}/recover")
def generate_recovery(
    factory_id: int,
    disruption_id: int,
    weights: Optional[PriorityWeights] = None,
    db: Session = Depends(get_db)
):
    """Generate recovery plans for a disruption."""
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        raise HTTPException(404, "Disruption not found")

    schedule = db.query(Schedule).filter(
        Schedule.factory_id == factory_id,
        Schedule.status == ScheduleStatus.ACTIVE
    ).first()
    if not schedule:
        raise HTTPException(400, "No active schedule")

    impact = analyze_impact(db, disruption, schedule)

    w = {
        "deadline": weights.deadline if weights else 80,
        "cost": weights.cost if weights else 60,
        "delay": weights.delay if weights else 70,
        "utilization": weights.utilization if weights else 50,
        "energy": weights.energy if weights else 40,
    }

    # Delete old recovery plans for this disruption
    db.query(RecoveryPlan).filter(RecoveryPlan.disruption_id == disruption_id).delete()
    db.flush()

    # Also delete draft schedules that were generated for old plans
    draft_schedules = db.query(Schedule).filter(
        Schedule.factory_id == factory_id,
        Schedule.status == ScheduleStatus.DRAFT,
        Schedule.is_recovery == False,
        Schedule.name.like("Recovery%"),
    ).all()
    for s in draft_schedules:
        db.query(ScheduleTask).filter(ScheduleTask.schedule_id == s.id).delete()
        db.delete(s)
    db.flush()

    plans = generate_recovery_plans(db, disruption, impact, w)

    # Audit log
    audit = AuditLog(
        factory_id=factory_id,
        event_type="recovery_generated",
        title=f"Recovery Plans Generated for Disruption #{disruption_id}",
        details={
            "disruption_id": disruption_id,
            "plans_count": len(plans),
            "feasible_count": sum(1 for p in plans if p.is_feasible),
            "weights": w,
        }
    )
    db.add(audit)
    db.commit()

    return {
        "impact": impact,
        "plans": [
            {
                "id": p.id, "name": p.name, "strategy": p.strategy,
                "description": p.description, "metrics": p.metrics or {},
                "is_recommended": p.is_recommended, "is_feasible": p.is_feasible,
                "infeasibility_reason": p.infeasibility_reason,
                "approval_status": p.approval_status.value if hasattr(p.approval_status, 'value') else str(p.approval_status),
                "schedule_data": p.schedule_data or [],
            }
            for p in plans
        ],
        "weights": w,
    }


@router.post("/factories/{factory_id}/disruptions/{disruption_id}/reweight")
def reweight_plans(
    factory_id: int,
    disruption_id: int,
    weights: PriorityWeights,
    db: Session = Depends(get_db)
):
    """Recalculate recommendation with new weights without regenerating plans."""
    plans = db.query(RecoveryPlan).filter(RecoveryPlan.disruption_id == disruption_id).all()
    if not plans:
        raise HTTPException(404, "No recovery plans found")

    w = {
        "deadline": weights.deadline,
        "cost": weights.cost,
        "delay": weights.delay,
        "utilization": weights.utilization,
        "energy": weights.energy,
    }

    # Reset recommendations
    for p in plans:
        p.is_recommended = False

    best = score_and_recommend(plans, w)
    if best:
        best.is_recommended = True

    db.commit()

    return {
        "plans": [
            {
                "id": p.id, "name": p.name, "strategy": p.strategy,
                "description": p.description, "metrics": p.metrics or {},
                "is_recommended": p.is_recommended, "is_feasible": p.is_feasible,
                "infeasibility_reason": p.infeasibility_reason,
                "approval_status": p.approval_status.value if hasattr(p.approval_status, 'value') else str(p.approval_status),
                "schedule_data": p.schedule_data or [],
            }
            for p in plans
        ],
        "weights": w,
    }


@router.get("/factories/{factory_id}/recovery-plans")
def list_recovery_plans(factory_id: int, db: Session = Depends(get_db)):
    disruptions = db.query(Disruption).filter(Disruption.factory_id == factory_id).all()
    d_ids = [d.id for d in disruptions]
    plans = db.query(RecoveryPlan).filter(RecoveryPlan.disruption_id.in_(d_ids)).all()
    return [
        {
            "id": p.id, "disruption_id": p.disruption_id,
            "name": p.name, "strategy": p.strategy,
            "description": p.description, "metrics": p.metrics or {},
            "is_recommended": p.is_recommended, "is_feasible": p.is_feasible,
            "approval_status": p.approval_status.value if hasattr(p.approval_status, 'value') else str(p.approval_status),
        }
        for p in plans
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/recovery-plans/{plan_id}/approve")
def approve_plan(plan_id: int, db: Session = Depends(get_db)):
    """Approve and apply a recovery plan."""
    plan = db.query(RecoveryPlan).filter(RecoveryPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Recovery plan not found")

    if not plan.is_feasible:
        raise HTTPException(400, "Cannot approve an infeasible plan")

    success, message = apply_recovery_plan(db, plan_id)
    if not success:
        raise HTTPException(400, message)

    return {"message": message, "plan_id": plan_id}


@router.post("/recovery-plans/{plan_id}/reject")
def reject_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(RecoveryPlan).filter(RecoveryPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Recovery plan not found")
    plan.approval_status = ApprovalStatus.REJECTED
    db.commit()
    return {"message": "Plan rejected", "plan_id": plan_id}


@router.post("/recovery-plans/{plan_id}/modify")
def modify_plan(plan_id: int, data: RecoveryPlanModify, db: Session = Depends(get_db)):
    """
    Manager MODIFY action: adjust a draft recovery plan (exclude additional
    machines/workers, override order priorities) and regenerate + re-validate it.
    Does not touch the active schedule. The manager must still call /approve
    afterward to apply the modified plan.
    """
    plan, errors = modify_recovery_plan(
        db, plan_id,
        additional_excluded_machine_ids=set(data.additional_excluded_machine_ids),
        additional_excluded_worker_ids=set(data.additional_excluded_worker_ids),
        order_priority_overrides={k: v.value for k, v in data.order_priority_overrides.items()},
    )
    if not plan:
        raise HTTPException(404, "; ".join(errors) or "Recovery plan not found")

    return {
        "id": plan.id, "name": plan.name, "strategy": plan.strategy,
        "description": plan.description, "metrics": plan.metrics or {},
        "is_recommended": plan.is_recommended, "is_feasible": plan.is_feasible,
        "infeasibility_reason": plan.infeasibility_reason,
        "approval_status": plan.approval_status.value if hasattr(plan.approval_status, 'value') else str(plan.approval_status),
        "schedule_data": plan.schedule_data or [],
        "validation_errors": errors,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT & NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/factories/{factory_id}/audit")
def get_audit_log(factory_id: int, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).filter(
        AuditLog.factory_id == factory_id
    ).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [
        {
            "id": l.id, "factory_id": l.factory_id,
            "event_type": l.event_type, "title": l.title,
            "details": l.details or {}, "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.get("/factories/{factory_id}/notifications")
def get_notifications(factory_id: int, db: Session = Depends(get_db)):
    notifications = db.query(Notification).filter(
        Notification.factory_id == factory_id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    return [
        {
            "id": n.id, "title": n.title, "message": n.message,
            "resource_type": n.resource_type, "resource_id": n.resource_id,
            "read": n.read, "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# AI
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/factories/{factory_id}/ai/chat")
async def ai_chat(factory_id: int, data: AIMessage, db: Session = Depends(get_db)):
    result = await process_ai_message(db, factory_id, data.message)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# SEED
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/seed")
def seed_data(db: Session = Depends(get_db)):
    factories = seed_all(db)
    return {"message": f"Seeded {len(factories)} demo factories",
            "factories": [{"id": f.id, "name": f.name} for f in factories]}
