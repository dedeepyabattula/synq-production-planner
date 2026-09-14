"""
Disruption Simulation & Recovery Plan Generation.

Creates scenario snapshots, analyzes impact, and generates
multiple recovery strategies using the deterministic scheduler.
"""

from typing import List, Dict, Any, Tuple, Set, Optional
from collections import defaultdict
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import (
    Factory, Machine, MachineCapability, Worker, WorkerSkill,
    Material, Order, Product, ProductionWorkflow, ProductionStep,
    Schedule, ScheduleTask, Disruption, RecoveryPlan,
    MachineStatus, OrderPriority, DisruptionType, TaskStatus, ScheduleStatus,
    ApprovalStatus, AuditLog, Notification
)
from app.scheduler import (
    generate_schedule, calculate_schedule_metrics,
    find_capable_machines, find_qualified_workers, validate_schedule,
    recompute_material_reservations,
)


def analyze_impact(db: Session, disruption: Disruption, schedule: Schedule) -> Dict[str, Any]:
    """Analyze the impact of a disruption on the current schedule."""
    tasks = db.query(ScheduleTask).filter(ScheduleTask.schedule_id == schedule.id).all()
    machines = db.query(Machine).filter(Machine.factory_id == disruption.factory_id).all()
    workers = db.query(Worker).filter(Worker.factory_id == disruption.factory_id).all()
    materials = db.query(Material).filter(Material.factory_id == disruption.factory_id).all()
    orders = db.query(Order).filter(Order.factory_id == disruption.factory_id).all()

    machine_map = {m.id: m for m in machines}
    worker_map = {w.id: w for w in workers}
    order_map = {o.id: o for o in orders}

    result = {
        "disruption_id": disruption.id,
        "disruption_type": disruption.disruption_type.value if hasattr(disruption.disruption_type, 'value') else str(disruption.disruption_type),
        "affected_resource": {},
        "affected_tasks": [],
        "downstream_tasks": [],
        "affected_orders": [],
        "deadlines_at_risk": [],
        "expected_delay_minutes": 0,
        "alternative_machines": [],
        "alternative_workers": [],
        "material_impact": [],
        "summary": "",
    }

    d_type = disruption.disruption_type
    if isinstance(d_type, str):
        d_type = DisruptionType(d_type)
    res_id = disruption.affected_resource_id
    params = disruption.parameters or {}

    # Identify affected resource
    if d_type in (DisruptionType.MACHINE_BREAKDOWN, DisruptionType.MACHINE_CAPACITY_REDUCTION):
        machine = machine_map.get(res_id)
        if machine:
            result["affected_resource"] = {
                "type": "machine",
                "id": machine.id,
                "name": machine.name,
                "status": machine.status.value if hasattr(machine.status, 'value') else str(machine.status),
                "capabilities": [c.capability for c in machine.capabilities],
            }

            # Find directly affected tasks
            for t in tasks:
                if t.machine_id == machine.id:
                    order = order_map.get(t.order_id)
                    step = db.query(ProductionStep).filter(ProductionStep.id == t.step_id).first()
                    result["affected_tasks"].append({
                        "task_id": t.id,
                        "order_id": t.order_id,
                        "order_code": order.order_code if order else "?",
                        "step_name": step.name if step else "?",
                        "start_time": t.start_time,
                        "end_time": t.end_time,
                        "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
                    })

            # Find downstream tasks (tasks depending on affected ones)
            affected_step_keys = set()
            for at in result["affected_tasks"]:
                affected_step_keys.add((at["order_id"], db.query(ScheduleTask).filter(ScheduleTask.id == at["task_id"]).first().step_id if at.get("task_id") else None))

            for t in tasks:
                if t.machine_id == machine.id:
                    continue
                step = db.query(ProductionStep).filter(ProductionStep.id == t.step_id).first()
                if step and step.preceding_steps:
                    for dep_id in step.preceding_steps:
                        if (t.order_id, dep_id) in affected_step_keys:
                            order = order_map.get(t.order_id)
                            result["downstream_tasks"].append({
                                "task_id": t.id,
                                "order_id": t.order_id,
                                "order_code": order.order_code if order else "?",
                                "step_name": step.name if step else "?",
                                "start_time": t.start_time,
                                "end_time": t.end_time,
                                "depends_on_step": dep_id,
                            })

            # Find alternative machines
            affected_capabilities = set()
            for at in result["affected_tasks"]:
                task_obj = db.query(ScheduleTask).filter(ScheduleTask.id == at["task_id"]).first()
                if task_obj:
                    step = db.query(ProductionStep).filter(ProductionStep.id == task_obj.step_id).first()
                    if step:
                        affected_capabilities.add(step.required_capability)

            for cap in affected_capabilities:
                for m in machines:
                    if m.id == res_id:
                        continue
                    if m.status in (MachineStatus.FAILED, MachineStatus.MAINTENANCE):
                        continue
                    caps = [c.capability for c in m.capabilities]
                    if cap in caps:
                        result["alternative_machines"].append({
                            "id": m.id,
                            "name": m.name,
                            "capability": cap,
                            "status": m.status.value if hasattr(m.status, 'value') else str(m.status),
                        })

    elif d_type in (DisruptionType.WORKER_ABSENCE, DisruptionType.WORKER_AVAILABILITY_CHANGE):
        worker = worker_map.get(res_id)
        if worker:
            result["affected_resource"] = {
                "type": "worker",
                "id": worker.id,
                "name": worker.name,
                "skills": [s.skill for s in worker.skills],
                "shift": worker.shift,
            }

            for t in tasks:
                if t.worker_id == worker.id:
                    order = order_map.get(t.order_id)
                    step = db.query(ProductionStep).filter(ProductionStep.id == t.step_id).first()
                    result["affected_tasks"].append({
                        "task_id": t.id,
                        "order_id": t.order_id,
                        "order_code": order.order_code if order else "?",
                        "step_name": step.name if step else "?",
                        "start_time": t.start_time,
                        "end_time": t.end_time,
                    })

            # Find alternative workers
            for skill_obj in worker.skills:
                for w in workers:
                    if w.id == res_id or not w.available:
                        continue
                    w_skills = [s.skill for s in w.skills]
                    if skill_obj.skill in w_skills:
                        result["alternative_workers"].append({
                            "id": w.id,
                            "name": w.name,
                            "skill": skill_obj.skill,
                            "shift": w.shift,
                        })

    elif d_type == DisruptionType.MATERIAL_SHORTAGE:
        mat = db.query(Material).filter(Material.id == res_id).first()
        if mat:
            result["affected_resource"] = {
                "type": "material",
                "id": mat.id,
                "name": mat.name,
                "available": mat.total_quantity - mat.reserved_quantity,
                "total": mat.total_quantity,
            }
            shortage_amount = params.get("shortage_amount", 0)
            result["material_impact"].append({
                "material_id": mat.id,
                "name": mat.name,
                "shortage": shortage_amount,
            })

    elif d_type == DisruptionType.URGENT_ORDER:
        result["affected_resource"] = {
            "type": "urgent_order",
            "details": params,
        }

    elif d_type == DisruptionType.PRIORITY_CHANGE:
        order_id = params.get("order_id")
        if order_id:
            order = order_map.get(order_id)
            if order:
                result["affected_resource"] = {
                    "type": "order",
                    "id": order.id,
                    "order_code": order.order_code,
                    "current_priority": order.priority.value if hasattr(order.priority, 'value') else str(order.priority),
                    "new_priority": params.get("new_priority", ""),
                }

    # Identify affected orders
    affected_order_ids = set()
    for at in result["affected_tasks"] + result["downstream_tasks"]:
        affected_order_ids.add(at["order_id"])

    for oid in affected_order_ids:
        order = order_map.get(oid)
        if order:
            result["affected_orders"].append({
                "id": order.id,
                "order_code": order.order_code,
                "product_id": order.product_id,
                "priority": order.priority.value if hasattr(order.priority, 'value') else str(order.priority),
                "deadline": order.deadline.isoformat(),
                "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
            })

    # Deadlines at risk
    duration_hours = params.get("duration_hours", 2)
    delay_minutes = duration_hours * 60
    result["expected_delay_minutes"] = delay_minutes

    now = datetime.utcnow()
    for order in result["affected_orders"]:
        o = order_map.get(order["id"])
        if o:
            # Simple check: if remaining time minus delay < 0
            order_tasks_list = [t for t in tasks if t.order_id == o.id]
            if order_tasks_list:
                completion = max(t.end_time for t in order_tasks_list)
                deadline_mins = (o.deadline - now).total_seconds() / 60
                if completion + delay_minutes > deadline_mins:
                    result["deadlines_at_risk"].append({
                        "order_id": o.id,
                        "order_code": o.order_code,
                        "priority": o.priority.value if hasattr(o.priority, 'value') else str(o.priority),
                        "deadline": o.deadline.isoformat(),
                        "estimated_completion": completion + delay_minutes,
                        "deadline_minutes": deadline_mins,
                    })

    # Generate summary
    n_tasks = len(result["affected_tasks"])
    n_downstream = len(result["downstream_tasks"])
    n_orders = len(result["affected_orders"])
    n_deadlines = len(result["deadlines_at_risk"])
    n_alt_machines = len(result["alternative_machines"])
    n_alt_workers = len(result["alternative_workers"])

    result["summary"] = (
        f"Impact: {n_tasks} tasks directly affected, {n_downstream} downstream tasks impacted, "
        f"{n_orders} orders affected, {n_deadlines} deadlines at risk. "
        f"Estimated delay: {delay_minutes:.0f} minutes. "
        f"Available alternatives: {n_alt_machines} machines, {n_alt_workers} workers."
    )

    return result


def generate_recovery_plans(
    db: Session,
    disruption: Disruption,
    impact: Dict[str, Any],
    weights: Dict[str, float] = None
) -> List[RecoveryPlan]:
    """Generate multiple recovery plan alternatives."""
    factory_id = disruption.factory_id
    d_type = disruption.disruption_type
    if isinstance(d_type, str):
        d_type = DisruptionType(d_type)
    params = disruption.parameters or {}

    # Default weights
    w = weights or {
        "deadline": 80, "cost": 60, "delay": 70,
        "utilization": 50, "energy": 40
    }

    machines = db.query(Machine).filter(Machine.factory_id == factory_id).all()
    workers = db.query(Worker).filter(Worker.factory_id == factory_id).all()
    orders = db.query(Order).filter(Order.factory_id == factory_id).all()

    plans = []

    # Determine excluded resources based on disruption type
    excluded_machines: Set[int] = set()
    excluded_workers: Set[int] = set()
    order_overrides: Dict[int, Dict] = {}

    if d_type == DisruptionType.MACHINE_BREAKDOWN:
        excluded_machines.add(disruption.affected_resource_id)
    elif d_type == DisruptionType.WORKER_ABSENCE:
        excluded_workers.add(disruption.affected_resource_id)
    elif d_type == DisruptionType.PRIORITY_CHANGE:
        order_id = params.get("order_id")
        new_priority = params.get("new_priority", "HIGH")
        if order_id:
            order_overrides[order_id] = {"priority": new_priority}

    # ─── Strategy 1: Reroute to alternative machines/workers ─────────────
    try:
        plan1_schedule, plan1_errors = generate_schedule(
            db, factory_id,
            name="Recovery: Reroute Tasks",
            excluded_machine_ids=excluded_machines,
            excluded_worker_ids=excluded_workers,
            order_overrides=order_overrides,
            strategy="default",
            commit=False,
        )
        if plan1_schedule:
            plan1 = RecoveryPlan(
                disruption_id=disruption.id,
                name="Plan A: Reroute Tasks",
                strategy="reroute",
                description="Reroute affected tasks to alternative compatible resources. "
                           "Minimizes schedule changes by only reassigning disrupted tasks.",
                schedule_data=serialize_schedule_tasks(db, plan1_schedule),
                metrics=plan1_schedule.metrics or {},
                is_feasible=len(plan1_errors) == 0,
                infeasibility_reason="; ".join(e.get("error", "") for e in plan1_errors) if plan1_errors else "",
            )
            db.add(plan1)
            plans.append(plan1)
    except Exception as e:
        plan1 = RecoveryPlan(
            disruption_id=disruption.id,
            name="Plan A: Reroute Tasks",
            strategy="reroute",
            description="Reroute affected tasks to alternative compatible resources.",
            is_feasible=False,
            infeasibility_reason=str(e),
        )
        db.add(plan1)
        plans.append(plan1)

    # ─── Strategy 2: Delay lower-priority orders, protect critical ───────
    try:
        # Override low/normal priority orders
        delay_overrides = dict(order_overrides)
        for o in orders:
            p = o.priority
            if isinstance(p, str):
                p = OrderPriority(p)
            if p in (OrderPriority.LOW, OrderPriority.NORMAL):
                delay_overrides[o.id] = {"priority": "LOW"}
            elif p in (OrderPriority.HIGH, OrderPriority.CRITICAL):
                delay_overrides[o.id] = {"priority": "CRITICAL"}

        plan2_schedule, plan2_errors = generate_schedule(
            db, factory_id,
            name="Recovery: Protect Critical Deadlines",
            excluded_machine_ids=excluded_machines,
            excluded_worker_ids=excluded_workers,
            order_overrides=delay_overrides,
            strategy="default",
            commit=False,
        )
        if plan2_schedule:
            plan2 = RecoveryPlan(
                disruption_id=disruption.id,
                name="Plan B: Protect Critical Deadlines",
                strategy="protect_critical",
                description="Delay lower-priority orders to protect critical and high-priority deadlines. "
                           "Non-critical orders may experience additional delays.",
                schedule_data=serialize_schedule_tasks(db, plan2_schedule),
                metrics=plan2_schedule.metrics or {},
                is_feasible=len(plan2_errors) == 0,
                infeasibility_reason="; ".join(e.get("error", "") for e in plan2_errors) if plan2_errors else "",
            )
            db.add(plan2)
            plans.append(plan2)
    except Exception as e:
        plan2 = RecoveryPlan(
            disruption_id=disruption.id,
            name="Plan B: Protect Critical Deadlines",
            strategy="protect_critical",
            description="Delay lower-priority orders to protect critical deadlines.",
            is_feasible=False,
            infeasibility_reason=str(e),
        )
        db.add(plan2)
        plans.append(plan2)

    # ─── Strategy 3: Minimize cost ───────────────────────────────────────
    try:
        plan3_schedule, plan3_errors = generate_schedule(
            db, factory_id,
            name="Recovery: Minimize Cost",
            excluded_machine_ids=excluded_machines,
            excluded_worker_ids=excluded_workers,
            order_overrides=order_overrides,
            strategy="minimize_cost",
            commit=False,
        )
        if plan3_schedule:
            plan3 = RecoveryPlan(
                disruption_id=disruption.id,
                name="Plan C: Minimize Cost",
                strategy="minimize_cost",
                description="Prioritize lowest-cost machines and resources. "
                           "May result in longer processing times but lower operational cost.",
                schedule_data=serialize_schedule_tasks(db, plan3_schedule),
                metrics=plan3_schedule.metrics or {},
                is_feasible=len(plan3_errors) == 0,
                infeasibility_reason="; ".join(e.get("error", "") for e in plan3_errors) if plan3_errors else "",
            )
            db.add(plan3)
            plans.append(plan3)
    except Exception as e:
        plan3 = RecoveryPlan(
            disruption_id=disruption.id,
            name="Plan C: Minimize Cost",
            strategy="minimize_cost",
            description="Prioritize lowest-cost machines and resources.",
            is_feasible=False,
            infeasibility_reason=str(e),
        )
        db.add(plan3)
        plans.append(plan3)

    # ─── Strategy 4: Balance load ────────────────────────────────────────
    try:
        plan4_schedule, plan4_errors = generate_schedule(
            db, factory_id,
            name="Recovery: Balance Load",
            excluded_machine_ids=excluded_machines,
            excluded_worker_ids=excluded_workers,
            order_overrides=order_overrides,
            strategy="balance_load",
            commit=False,
        )
        if plan4_schedule:
            plan4 = RecoveryPlan(
                disruption_id=disruption.id,
                name="Plan D: Balance Load",
                strategy="balance_load",
                description="Distribute tasks evenly across available machines. "
                           "Improves utilization and reduces bottlenecks.",
                schedule_data=serialize_schedule_tasks(db, plan4_schedule),
                metrics=plan4_schedule.metrics or {},
                is_feasible=len(plan4_errors) == 0,
                infeasibility_reason="; ".join(e.get("error", "") for e in plan4_errors) if plan4_errors else "",
            )
            db.add(plan4)
            plans.append(plan4)
    except Exception as e:
        plan4 = RecoveryPlan(
            disruption_id=disruption.id,
            name="Plan D: Balance Load",
            strategy="balance_load",
            description="Distribute tasks evenly across available machines.",
            is_feasible=False,
            infeasibility_reason=str(e),
        )
        db.add(plan4)
        plans.append(plan4)

    # ─── Score and recommend ─────────────────────────────────────────────
    best_plan = score_and_recommend(plans, w)
    if best_plan:
        best_plan.is_recommended = True

    db.flush()
    db.commit()

    return plans


def score_and_recommend(
    plans: List[RecoveryPlan],
    weights: Dict[str, float]
) -> Optional[RecoveryPlan]:
    """Score recovery plans based on weighted metrics and recommend the best."""
    # Normalize weights
    total_w = sum(weights.values()) or 1
    w = {k: v / total_w for k, v in weights.items()}

    best_score = -float("inf")
    best_plan = None

    for plan in plans:
        if not plan.is_feasible:
            continue

        m = plan.metrics or {}
        if not m:
            continue

        # Higher is better for: deadline_adherence, machine_utilization, worker_utilization
        # Lower is better for: total_delay, estimated_cost, energy_impact
        score = 0.0
        score += w.get("deadline", 0) * m.get("deadline_adherence", 0)
        score -= w.get("delay", 0) * min(m.get("total_delay", 0) / 100, 100)
        score -= w.get("cost", 0) * min(m.get("estimated_cost", 0) / 1000, 100)
        score += w.get("utilization", 0) * m.get("machine_utilization", 0)
        score -= w.get("energy", 0) * min(m.get("energy_impact", 0) / 100, 100)

        # IMPORTANT: reassign (don't mutate in place). SQLAlchemy does not
        # auto-detect in-place mutation of JSON/dict column values once an
        # object has already been flushed once (which happens here because
        # generate_recovery_plans flushes each candidate schedule as it's
        # generated) — an in-place `plan.metrics["weighted_score"] = ...`
        # would silently fail to persist on commit for any plan generated
        # before the last one. Reassigning the attribute makes the change
        # detectable regardless of prior flush state.
        plan.metrics = {**m, "weighted_score": round(score, 2)}

        if score > best_score:
            best_score = score
            best_plan = plan

    return best_plan


def modify_recovery_plan(
    db: Session,
    plan_id: int,
    additional_excluded_machine_ids: Optional[Set[int]] = None,
    additional_excluded_worker_ids: Optional[Set[int]] = None,
    order_priority_overrides: Optional[Dict[int, str]] = None,
) -> Tuple[Optional[RecoveryPlan], List[str]]:
    """
    Manager modification of a draft recovery plan (human-in-the-loop MODIFY action).

    Regenerates the plan's candidate schedule using its original strategy plus
    any additional manager-specified constraints, re-validates it, and updates
    the stored plan in place. Sets approval_status to MODIFIED. Does NOT touch
    the active schedule — that only happens on a subsequent /approve call.
    """
    plan = db.query(RecoveryPlan).filter(RecoveryPlan.id == plan_id).first()
    if not plan:
        return None, ["Recovery plan not found"]

    disruption = db.query(Disruption).filter(Disruption.id == plan.disruption_id).first()
    if not disruption:
        return None, ["Disruption not found"]

    factory_id = disruption.factory_id
    d_type = disruption.disruption_type
    if isinstance(d_type, str):
        d_type = DisruptionType(d_type)
    params = disruption.parameters or {}

    # Rebuild the same base exclusions the plan originally used from the disruption...
    excluded_machines: Set[int] = set()
    excluded_workers: Set[int] = set()
    order_overrides: Dict[int, Dict] = {}

    if d_type == DisruptionType.MACHINE_BREAKDOWN:
        excluded_machines.add(disruption.affected_resource_id)
    elif d_type == DisruptionType.WORKER_ABSENCE:
        excluded_workers.add(disruption.affected_resource_id)
    elif d_type == DisruptionType.PRIORITY_CHANGE:
        order_id = params.get("order_id")
        new_priority = params.get("new_priority", "HIGH")
        if order_id:
            order_overrides[order_id] = {"priority": new_priority}

    # ...then layer the manager's additional modifications on top.
    excluded_machines |= (additional_excluded_machine_ids or set())
    excluded_workers |= (additional_excluded_worker_ids or set())
    for oid, pr in (order_priority_overrides or {}).items():
        order_overrides[oid] = {"priority": pr}

    strategy = plan.strategy
    if strategy == "protect_critical":
        # Recreate the same delay/protect override pattern the original strategy used.
        orders = db.query(Order).filter(Order.factory_id == factory_id).all()
        for o in orders:
            if o.id in order_overrides:
                continue
            p = o.priority
            if isinstance(p, str):
                p = OrderPriority(p)
            if p in (OrderPriority.LOW, OrderPriority.NORMAL):
                order_overrides[o.id] = {"priority": "LOW"}
            elif p in (OrderPriority.HIGH, OrderPriority.CRITICAL):
                order_overrides[o.id] = {"priority": "CRITICAL"}

    try:
        new_schedule, errors = generate_schedule(
            db, factory_id,
            name=f"Recovery (Modified): {plan.name}",
            excluded_machine_ids=excluded_machines,
            excluded_worker_ids=excluded_workers,
            order_overrides=order_overrides,
            strategy=strategy,
            commit=False,
        )
    except Exception as e:
        plan.is_feasible = False
        plan.infeasibility_reason = str(e)
        plan.approval_status = ApprovalStatus.MODIFIED
        db.commit()
        return plan, [str(e)]

    if not new_schedule:
        plan.is_feasible = False
        plan.infeasibility_reason = "; ".join(e.get("error", "") for e in errors) if errors else "Modification produced no feasible schedule"
        plan.schedule_data = []
        plan.metrics = {}
        plan.approval_status = ApprovalStatus.MODIFIED
        db.commit()
        return plan, [plan.infeasibility_reason]

    is_valid, validation_errors = validate_schedule(db, new_schedule.id)

    plan.schedule_data = serialize_schedule_tasks(db, new_schedule)
    plan.metrics = new_schedule.metrics or {}
    plan.is_feasible = (len(errors) == 0) and is_valid
    plan.infeasibility_reason = (
        "; ".join([e.get("error", "") for e in errors] + validation_errors)
        if (errors or not is_valid) else ""
    )
    plan.approval_status = ApprovalStatus.MODIFIED
    plan.is_recommended = False  # a manually modified plan needs a fresh recommendation pass

    db.commit()
    return plan, (validation_errors if not is_valid else [])


def serialize_schedule_tasks(db: Session, schedule: Schedule) -> List[Dict[str, Any]]:
    """Serialize schedule tasks to JSON-safe format."""
    tasks = db.query(ScheduleTask).filter(ScheduleTask.schedule_id == schedule.id).all()
    result = []
    for t in tasks:
        order = db.query(Order).filter(Order.id == t.order_id).first()
        step = db.query(ProductionStep).filter(ProductionStep.id == t.step_id).first()
        machine = db.query(Machine).filter(Machine.id == t.machine_id).first()
        worker = db.query(Worker).filter(Worker.id == t.worker_id).first() if t.worker_id else None

        result.append({
            "id": t.id,
            "task_id": t.id,
            "order_id": t.order_id,
            "order_code": order.order_code if order else "",
            "step_id": t.step_id,
            "step_name": step.name if step else "",
            "machine_id": t.machine_id,
            "machine_name": machine.name if machine else "",
            "worker_id": t.worker_id,
            "worker_name": worker.name if worker else "",
            "unit_index": t.unit_index,
            "start_time": t.start_time,
            "end_time": t.end_time,
            "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
        })
    return result


def apply_recovery_plan(db: Session, plan_id: int) -> Tuple[bool, str]:
    """Apply an approved recovery plan as the active schedule."""
    plan = db.query(RecoveryPlan).filter(RecoveryPlan.id == plan_id).first()
    if not plan:
        return False, "Recovery plan not found"

    if not plan.is_feasible:
        return False, "Cannot apply infeasible recovery plan"

    disruption = db.query(Disruption).filter(Disruption.id == plan.disruption_id).first()
    if not disruption:
        return False, "Disruption not found"

    # Scenario isolation: a What-If disruption is for exploration only. It must
    # never be allowed to become the real active schedule.
    if disruption.is_whatif:
        return False, (
            "This recovery plan belongs to a What-If scenario and cannot be applied "
            "to the active schedule. Create a real disruption to act on this."
        )

    # Mark old active schedules as superseded
    old_schedules = db.query(Schedule).filter(
        Schedule.factory_id == disruption.factory_id,
        Schedule.status == ScheduleStatus.ACTIVE
    ).all()
    for s in old_schedules:
        s.status = ScheduleStatus.SUPERSEDED

    # Create a new active schedule from recovery plan data
    new_schedule = Schedule(
        factory_id=disruption.factory_id,
        name=f"Recovery: {plan.name}",
        status=ScheduleStatus.ACTIVE,
        is_recovery=True,
        source_disruption_id=disruption.id,
        metrics=plan.metrics,
    )
    db.add(new_schedule)
    db.flush()

    # Recreate tasks from plan data
    for td in plan.schedule_data:
        task = ScheduleTask(
            schedule_id=new_schedule.id,
            order_id=td["order_id"],
            step_id=td["step_id"],
            machine_id=td["machine_id"],
            worker_id=td.get("worker_id"),
            unit_index=td.get("unit_index", 0),
            start_time=td["start_time"],
            end_time=td["end_time"],
            status=TaskStatus.SCHEDULED,
        )
        db.add(task)

    db.flush()

    # No invalid schedule may become active: re-validate against current
    # machine/worker/dependency constraints before committing. If the factory
    # state has drifted since the plan was generated (e.g. another disruption
    # occurred), this catches it instead of silently activating a bad schedule.
    is_valid, validation_errors = validate_schedule(db, new_schedule.id)
    if not is_valid:
        db.rollback()
        return False, (
            "Cannot apply recovery plan: the schedule is no longer valid "
            "(factory state may have changed): " + "; ".join(validation_errors[:5])
        )

    # Update plan approval status
    plan.approval_status = ApprovalStatus.APPROVED
    plan.approved_at = datetime.utcnow()

    # Mark disruption as resolved
    disruption.resolved = True

    recompute_material_reservations(db, disruption.factory_id)

    # Add audit log
    audit = AuditLog(
        factory_id=disruption.factory_id,
        event_type="recovery_approved",
        title=f"Recovery Plan Approved: {plan.name}",
        details={
            "disruption_id": disruption.id,
            "plan_id": plan.id,
            "plan_name": plan.name,
            "strategy": plan.strategy,
            "metrics": plan.metrics,
        }
    )
    db.add(audit)

    # Generate notifications
    for td in plan.schedule_data:
        if td.get("machine_name"):
            notif = Notification(
                factory_id=disruption.factory_id,
                title=f"Task Assigned: {td.get('step_name', 'Task')}",
                message=f"Machine {td['machine_name']}: New task for order {td.get('order_code', '')}. "
                       f"Scheduled {td['start_time']:.0f}-{td['end_time']:.0f} min.",
                resource_type="machine",
                resource_id=td.get("machine_id"),
            )
            db.add(notif)

    db.commit()
    return True, f"Recovery plan '{plan.name}' applied successfully"
