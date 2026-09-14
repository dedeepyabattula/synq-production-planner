"""
Deterministic Scheduling Engine for SynQ.

Uses priority-based scheduling with earliest-deadline-first,
constrained by machine capability, worker skills, material
availability, and production step dependencies (DAG).
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict, deque
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import (
    Factory, Product, ProductionWorkflow, ProductionStep,
    Machine, MachineCapability, Worker, WorkerSkill,
    Material, Order, Schedule, ScheduleTask,
    MachineStatus, OrderPriority, ScheduleStatus, TaskStatus, OrderStatus
)


PRIORITY_WEIGHT = {
    OrderPriority.CRITICAL: 1000,
    OrderPriority.HIGH: 100,
    OrderPriority.NORMAL: 10,
    OrderPriority.LOW: 1,
}


def topological_sort_steps(steps: List[ProductionStep]) -> List[ProductionStep]:
    """Sort production steps respecting dependency DAG. Detects cycles."""
    step_map = {s.id: s for s in steps}
    in_degree = defaultdict(int)
    adj = defaultdict(list)

    for s in steps:
        deps = s.preceding_steps or []
        for dep_id in deps:
            if dep_id in step_map:
                adj[dep_id].append(s.id)
                in_degree[s.id] += 1

    queue = deque([s.id for s in steps if in_degree[s.id] == 0])
    result = []
    while queue:
        node = queue.popleft()
        if node in step_map:
            result.append(step_map[node])
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(steps):
        raise ValueError("Circular dependency detected in production workflow")
    return result


def find_capable_machines(
    step: ProductionStep,
    machines: List[Machine],
    excluded_machine_ids: Set[int] = None
) -> List[Machine]:
    """Find machines that have the required capability and are not FAILED/MAINTENANCE."""
    excluded = excluded_machine_ids or set()
    capable = []
    for m in machines:
        if m.id in excluded:
            continue
        if m.status in (MachineStatus.FAILED, MachineStatus.MAINTENANCE):
            continue
        caps = [c.capability for c in m.capabilities]
        if step.required_capability in caps:
            capable.append(m)
    return capable


def find_qualified_workers(
    step: ProductionStep,
    workers: List[Worker],
    excluded_worker_ids: Set[int] = None
) -> List[Worker]:
    """Find available workers with required skill."""
    if not step.required_skill:
        return workers[:1] if workers else []
    excluded = excluded_worker_ids or set()
    qualified = []
    for w in workers:
        if w.id in excluded:
            continue
        if not w.available:
            continue
        skills = [s.skill for s in w.skills]
        if step.required_skill in skills:
            qualified.append(w)
    return qualified


def check_material_availability(
    step: ProductionStep,
    materials: List[Material],
    quantity: int = 1
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Check if materials are available for a step. Returns (ok, shortages).

    NOTE: this checks against the material's `total_quantity` (the physical
    stock on hand), not `total_quantity - reserved_quantity`. `reserved_quantity`
    tracks what is committed to the *currently active* schedule for reporting
    purposes (see recompute_material_reservations) — but generate_schedule always
    produces a brand-new, complete replacement schedule, so a fresh generation
    should be checked against total physical stock, with cumulative consumption
    across the new candidate schedule tracked separately by the caller
    (see `material_usage` in generate_schedule).
    """
    mat_reqs = step.material_requirements or []
    if not mat_reqs:
        return True, []

    mat_map = {m.id: m for m in materials}
    shortages = []

    for req in mat_reqs:
        mat_id = req.get("material_id")
        needed = req.get("quantity", 0) * quantity
        mat = mat_map.get(mat_id)
        if not mat:
            shortages.append({"material_id": mat_id, "needed": needed, "available": 0})
        elif mat.total_quantity < needed:
            shortages.append({
                "material_id": mat_id,
                "name": mat.name,
                "needed": needed,
                "available": mat.total_quantity
            })

    return len(shortages) == 0, shortages


def generate_schedule(
    db: Session,
    factory_id: int,
    name: str = "Auto Schedule",
    excluded_machine_ids: Set[int] = None,
    excluded_worker_ids: Set[int] = None,
    order_overrides: Dict[int, Dict] = None,
    strategy: str = "default",
    commit: bool = True,
) -> Tuple[Optional[Schedule], List[Dict[str, Any]]]:
    """
    Generate a deterministic production schedule.

    IMPORTANT (scenario isolation): `order_overrides` is used ONLY to compute an
    *effective* priority for sequencing/scoring purposes within this hypothetical
    schedule. It must NEVER be written back onto the real `Order` rows, since this
    function is called repeatedly to generate what-if / recovery-plan candidates
    that must not mutate live factory state. Only an explicit, approved action
    (e.g. applying a recovery plan, or a dedicated "change order priority" edit)
    may persist a priority change.

    `commit` controls whether this call commits the transaction itself. Callers
    that generate several candidate schedules in a row (e.g. generate_recovery_plans)
    should pass commit=False and commit once at the end, so a failure partway
    through does not leave a half-written set of candidate schedules in the DB.

    Returns (schedule, errors).
    If critical errors occur, schedule may be None.
    """
    factory = db.query(Factory).filter(Factory.id == factory_id).first()
    if not factory:
        return None, [{"error": "Factory not found"}]

    machines = db.query(Machine).filter(Machine.factory_id == factory_id).all()
    workers = db.query(Worker).filter(Worker.factory_id == factory_id).all()
    materials = db.query(Material).filter(Material.factory_id == factory_id).all()
    orders = db.query(Order).filter(
        Order.factory_id == factory_id,
        Order.status.in_([OrderStatus.PENDING, OrderStatus.IN_PROGRESS])
    ).all()

    if not orders:
        return None, [{"error": "No active orders to schedule"}]

    # Compute an *effective* priority per order for this hypothetical schedule only.
    # This is intentionally NOT written back onto the Order ORM objects: doing so
    # would permanently corrupt real order priorities the next time this session
    # is committed (see docstring above).
    override_map = order_overrides or {}
    effective_priority: Dict[int, OrderPriority] = {}
    for o in orders:
        ov = override_map.get(o.id)
        if ov and "priority" in ov:
            effective_priority[o.id] = OrderPriority(ov["priority"])
        else:
            effective_priority[o.id] = o.priority

    # Sort orders by effective priority (CRITICAL first) then deadline (earliest first)
    orders.sort(key=lambda o: (-PRIORITY_WEIGHT.get(effective_priority[o.id], 10), o.deadline))

    excluded_m = excluded_machine_ids or set()
    excluded_w = excluded_worker_ids or set()

    # Track machine and worker availability (next available time)
    machine_avail: Dict[int, float] = {m.id: 0.0 for m in machines if m.id not in excluded_m}
    worker_avail: Dict[int, float] = {w.id: 0.0 for w in workers if w.id not in excluded_w}

    # Track when each step for each order finishes (for dependency resolution)
    step_finish_time: Dict[str, float] = {}  # "order_id-step_id" -> finish_time

    schedule = Schedule(
        factory_id=factory_id,
        name=name,
        status=ScheduleStatus.DRAFT
    )
    db.add(schedule)
    db.flush()

    tasks_created = []
    errors = []
    material_usage: Dict[int, float] = defaultdict(float)

    for order in orders:
        product = db.query(Product).filter(Product.id == order.product_id).first()
        if not product:
            errors.append({"order": order.order_code, "error": "Product not found"})
            continue

        workflows = db.query(ProductionWorkflow).filter(
            ProductionWorkflow.product_id == product.id
        ).all()

        for wf in workflows:
            steps = db.query(ProductionStep).filter(
                ProductionStep.workflow_id == wf.id
            ).all()

            if not steps:
                continue

            try:
                sorted_steps = topological_sort_steps(steps)
            except ValueError as e:
                errors.append({"order": order.order_code, "workflow": wf.name, "error": str(e)})
                continue

            for qty_idx in range(order.quantity):
                for step in sorted_steps:
                    # Calculate earliest start based on dependencies
                    earliest_start = 0.0
                    for dep_id in (step.preceding_steps or []):
                        key = f"{order.id}-{dep_id}-{qty_idx}"
                        if key in step_finish_time:
                            earliest_start = max(earliest_start, step_finish_time[key])

                    # Find capable machine
                    capable = find_capable_machines(step, machines, excluded_m)
                    if not capable:
                        errors.append({
                            "order": order.order_code,
                            "step": step.name,
                            "error": f"No capable machine for '{step.required_capability}'"
                        })
                        continue

                    # Find qualified worker
                    qualified = find_qualified_workers(step, workers, excluded_w)
                    if step.required_skill and not qualified:
                        errors.append({
                            "order": order.order_code,
                            "step": step.name,
                            "error": f"No qualified worker for skill '{step.required_skill}'"
                        })
                        continue

                    # Check materials: both per-step availability and cumulative
                    # consumption across everything already scheduled in this
                    # candidate schedule (material_usage), against total physical
                    # stock. This prevents double/over-consumption of materials
                    # by earlier orders/steps in the same schedule.
                    mat_ok, shortages = check_material_availability(step, materials, 1)
                    for req in (step.material_requirements or []):
                        mat_id = req.get("material_id")
                        qty = req.get("quantity", 0)
                        total_stock = sum(m.total_quantity for m in materials if m.id == mat_id)
                        if material_usage[mat_id] + qty > total_stock:
                            mat_ok = False
                            shortages.append({"material_id": mat_id, "error": "Insufficient after allocation"})

                    if not mat_ok:
                        errors.append({
                            "order": order.order_code,
                            "step": step.name,
                            "error": "Material shortage",
                            "details": shortages
                        })
                        # A step that cannot get its materials cannot be scheduled;
                        # skip creating this task so we don't fabricate a task that
                        # silently ignores an unmet material constraint.
                        continue

                    # Strategy-dependent machine selection
                    if strategy == "minimize_cost":
                        capable.sort(key=lambda m: m.operating_cost)
                    elif strategy == "minimize_energy":
                        capable.sort(key=lambda m: m.energy_consumption)
                    elif strategy == "balance_load":
                        capable.sort(key=lambda m: machine_avail.get(m.id, 0))
                    else:
                        # Default: earliest available
                        capable.sort(key=lambda m: machine_avail.get(m.id, 0))

                    best_machine = capable[0]
                    best_worker = qualified[0] if qualified else None

                    # Calculate timing
                    machine_ready = machine_avail.get(best_machine.id, 0)
                    worker_ready = worker_avail.get(best_worker.id, 0) if best_worker else 0
                    start = max(earliest_start, machine_ready, worker_ready)

                    duration = (step.processing_duration + step.setup_duration) / best_machine.processing_speed
                    end = start + duration

                    # Create task
                    task = ScheduleTask(
                        schedule_id=schedule.id,
                        order_id=order.id,
                        step_id=step.id,
                        machine_id=best_machine.id,
                        worker_id=best_worker.id if best_worker else None,
                        unit_index=qty_idx,
                        start_time=start,
                        end_time=end,
                        status=TaskStatus.SCHEDULED
                    )
                    db.add(task)
                    tasks_created.append(task)

                    # Update availability
                    machine_avail[best_machine.id] = end
                    if best_worker:
                        worker_avail[best_worker.id] = end

                    step_finish_time[f"{order.id}-{step.id}-{qty_idx}"] = end

                    # Track material usage
                    for req in (step.material_requirements or []):
                        material_usage[req.get("material_id", 0)] += req.get("quantity", 0)

    db.flush()

    # Calculate metrics
    metrics = calculate_schedule_metrics(db, schedule, orders, machines, workers)
    schedule.metrics = metrics

    db.flush()
    if commit:
        db.commit()
    return schedule, errors


def calculate_schedule_metrics(
    db: Session,
    schedule: Schedule,
    orders: List[Order],
    machines: List[Machine],
    workers: List[Worker]
) -> Dict[str, Any]:
    """Calculate trade-off metrics for a schedule."""
    tasks = db.query(ScheduleTask).filter(ScheduleTask.schedule_id == schedule.id).all()

    if not tasks:
        return {
            "deadline_adherence": 0,
            "total_delay": 0,
            "delayed_orders": 0,
            "estimated_cost": 0,
            "machine_utilization": 0,
            "worker_utilization": 0,
            "energy_impact": 0,
            "total_tasks": 0,
            "makespan": 0,
        }

    # Group tasks by order
    order_tasks: Dict[int, List[ScheduleTask]] = defaultdict(list)
    for t in tasks:
        order_tasks[t.order_id].append(t)

    order_map = {o.id: o for o in orders}
    makespan = max(t.end_time for t in tasks)
    now = datetime.utcnow()

    # Deadline adherence
    on_time = 0
    total_delay = 0.0
    delayed_count = 0

    for order_id, otasks in order_tasks.items():
        order = order_map.get(order_id)
        if not order:
            continue
        completion = max(t.end_time for t in otasks)
        # Convert deadline to minutes from now for comparison
        deadline_minutes = (order.deadline - now).total_seconds() / 60
        if completion <= deadline_minutes:
            on_time += 1
        else:
            delayed_count += 1
            total_delay += completion - deadline_minutes

    total_orders = len(order_tasks)
    deadline_adherence = (on_time / total_orders * 100) if total_orders > 0 else 100

    # Machine utilization
    machine_busy: Dict[int, float] = defaultdict(float)
    for t in tasks:
        machine_busy[t.machine_id] += (t.end_time - t.start_time)

    machine_map = {m.id: m for m in machines}
    total_machine_util = 0.0
    active_machines = 0
    for mid, busy in machine_busy.items():
        if makespan > 0:
            total_machine_util += busy / makespan
            active_machines += 1

    machine_utilization = (total_machine_util / active_machines * 100) if active_machines > 0 else 0

    # Worker utilization
    worker_busy: Dict[int, float] = defaultdict(float)
    for t in tasks:
        if t.worker_id:
            worker_busy[t.worker_id] += (t.end_time - t.start_time)

    active_workers = len(worker_busy)
    total_worker_util = 0.0
    for wid, busy in worker_busy.items():
        if makespan > 0:
            total_worker_util += busy / makespan

    worker_utilization = (total_worker_util / active_workers * 100) if active_workers > 0 else 0

    # Cost
    estimated_cost = 0.0
    for t in tasks:
        m = machine_map.get(t.machine_id)
        if m:
            hours = (t.end_time - t.start_time) / 60
            estimated_cost += m.operating_cost * hours

    # Energy
    energy_impact = 0.0
    for t in tasks:
        m = machine_map.get(t.machine_id)
        if m:
            hours = (t.end_time - t.start_time) / 60
            energy_impact += m.energy_consumption * hours

    return {
        "deadline_adherence": round(deadline_adherence, 1),
        "total_delay": round(total_delay, 1),
        "delayed_orders": delayed_count,
        "estimated_cost": round(estimated_cost, 2),
        "machine_utilization": round(machine_utilization, 1),
        "worker_utilization": round(worker_utilization, 1),
        "energy_impact": round(energy_impact, 2),
        "total_tasks": len(tasks),
        "makespan": round(makespan, 1),
        "total_orders": total_orders,
        "on_time_orders": on_time,
    }


def recompute_material_reservations(db: Session, factory_id: int) -> None:
    """
    Recompute each material's reserved_quantity from the tasks in the factory's
    current ACTIVE schedule only. This keeps material availability checks
    grounded in what is actually committed to production, without double
    counting consumption across superseded/draft/what-if schedules.

    Call this after a schedule is set ACTIVE (initial generation or recovery
    plan approval). Does not commit; caller is responsible for committing.
    """
    active_schedule = db.query(Schedule).filter(
        Schedule.factory_id == factory_id,
        Schedule.status == ScheduleStatus.ACTIVE
    ).first()

    materials = db.query(Material).filter(Material.factory_id == factory_id).all()

    usage: Dict[int, float] = defaultdict(float)
    if active_schedule:
        tasks = db.query(ScheduleTask).filter(ScheduleTask.schedule_id == active_schedule.id).all()
        step_cache: Dict[int, ProductionStep] = {}
        for t in tasks:
            step = step_cache.get(t.step_id)
            if step is None:
                step = db.query(ProductionStep).filter(ProductionStep.id == t.step_id).first()
                step_cache[t.step_id] = step
            if not step:
                continue
            for req in (step.material_requirements or []):
                usage[req.get("material_id")] += req.get("quantity", 0)

    for m in materials:
        m.reserved_quantity = usage.get(m.id, 0)


def validate_schedule(db: Session, schedule_id: int) -> Tuple[bool, List[str]]:
    """Validate a schedule against all constraints. Returns (valid, errors)."""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        return False, ["Schedule not found"]

    tasks = db.query(ScheduleTask).filter(ScheduleTask.schedule_id == schedule_id).all()
    errors = []

    if not tasks:
        return False, ["Schedule has no tasks"]

    machines = db.query(Machine).filter(Machine.factory_id == schedule.factory_id).all()
    workers = db.query(Worker).filter(Worker.factory_id == schedule.factory_id).all()
    machine_map = {m.id: m for m in machines}
    worker_map = {w.id: w for w in workers}

    # Check machine capability for each task
    for t in tasks:
        step = db.query(ProductionStep).filter(ProductionStep.id == t.step_id).first()
        machine = machine_map.get(t.machine_id)
        if not machine:
            errors.append(f"Task {t.id}: Machine {t.machine_id} not found")
            continue
        caps = [c.capability for c in machine.capabilities]
        if step and step.required_capability not in caps:
            errors.append(
                f"Task {t.id}: Machine '{machine.name}' lacks capability '{step.required_capability}'"
            )

    # Check machine conflicts (overlapping tasks on same machine)
    machine_tasks: Dict[int, List[ScheduleTask]] = defaultdict(list)
    for t in tasks:
        machine_tasks[t.machine_id].append(t)

    for mid, mtasks in machine_tasks.items():
        mtasks.sort(key=lambda x: x.start_time)
        for i in range(len(mtasks) - 1):
            if mtasks[i].end_time > mtasks[i + 1].start_time:
                errors.append(
                    f"Machine conflict: Machine {mid} has overlapping tasks "
                    f"[{mtasks[i].start_time}-{mtasks[i].end_time}] and "
                    f"[{mtasks[i+1].start_time}-{mtasks[i+1].end_time}]"
                )

    # Check worker conflicts
    worker_tasks: Dict[int, List[ScheduleTask]] = defaultdict(list)
    for t in tasks:
        if t.worker_id:
            worker_tasks[t.worker_id].append(t)

    for wid, wtasks in worker_tasks.items():
        wtasks.sort(key=lambda x: x.start_time)
        for i in range(len(wtasks) - 1):
            if wtasks[i].end_time > wtasks[i + 1].start_time:
                errors.append(
                    f"Worker conflict: Worker {wid} has overlapping tasks "
                    f"[{wtasks[i].start_time}-{wtasks[i].end_time}] and "
                    f"[{wtasks[i+1].start_time}-{wtasks[i+1].end_time}]"
                )

    # Check dependency ordering (per-unit: with order.quantity > 1, units are
    # legitimately pipelined, so dependency checks must be scoped to the same
    # unit_index, not aggregated across all units of a step).
    step_starts: Dict[Tuple[int, int, int], float] = {}
    for t in tasks:
        key = (t.order_id, t.step_id, t.unit_index)
        if key not in step_starts or t.start_time < step_starts[key]:
            step_starts[key] = t.start_time

    step_ends: Dict[Tuple[int, int, int], float] = {}
    for t in tasks:
        key = (t.order_id, t.step_id, t.unit_index)
        if key not in step_ends or t.end_time > step_ends[key]:
            step_ends[key] = t.end_time

    for t in tasks:
        step = db.query(ProductionStep).filter(ProductionStep.id == t.step_id).first()
        if step and step.preceding_steps:
            for dep_id in step.preceding_steps:
                dep_key = (t.order_id, dep_id, t.unit_index)
                if dep_key in step_ends:
                    if t.start_time < step_ends[dep_key]:
                        errors.append(
                            f"Dependency violation: Task for step {step.name} (unit {t.unit_index}) starts at "
                            f"{t.start_time} before dependency step {dep_id} finishes at "
                            f"{step_ends[dep_key]}"
                        )

    return len(errors) == 0, errors
