"""
Seed data: Demo factories for SynQ.
These are pre-built datasets for demonstration - the application
works identically with user-created factories.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import (
    Factory, Product, ProductionWorkflow, ProductionStep,
    Machine, MachineCapability, Worker, WorkerSkill,
    Material, Order,
    MachineStatus, OrderPriority, OrderStatus
)


def _backfill_repair_data(db: Session, factory: Factory, default_repair_minutes: float, maintenance_worker_name: str) -> None:
    """
    Ensure this factory has at least one available worker with the
    "maintenance" skill, and that every machine has a configured
    repair_duration_minutes — backfilling either if missing.

    Safe to call repeatedly (idempotent): needed because seeding a factory
    that already exists just returns it as-is (see the `existing` checks
    below), so a demo factory created before this feature existed wouldn't
    otherwise ever pick up the new maintenance worker / repair durations.
    Used by the repair-based recovery strategy in simulation.py.
    """
    machines = db.query(Machine).filter(Machine.factory_id == factory.id).all()
    changed = False
    for m in machines:
        if m.repair_duration_minutes is None:
            m.repair_duration_minutes = default_repair_minutes
            changed = True

    workers = db.query(Worker).filter(Worker.factory_id == factory.id).all()
    has_maintenance = any(
        w.available and any(s.skill == "maintenance" for s in w.skills)
        for w in workers
    )
    if not has_maintenance:
        w = Worker(factory_id=factory.id, name=maintenance_worker_name, shift="FLEX",
                   available=True, max_overtime_hours=4)
        db.add(w)
        db.flush()
        db.add(WorkerSkill(worker_id=w.id, skill="maintenance"))
        changed = True

    if changed:
        db.commit()


def seed_ev_battery_factory(db: Session) -> Factory:
    """Create an EV Battery Manufacturing demo factory."""
    # Check if already seeded
    existing = db.query(Factory).filter(Factory.name == "EV Battery Plant", Factory.is_demo == True).first()
    if existing:
        _backfill_repair_data(db, existing, default_repair_minutes=180, maintenance_worker_name="Robert Diaz")
        return existing

    factory = Factory(name="EV Battery Plant", industry="EV Battery Manufacturing",
                      description="Electric vehicle battery cell, module, and pack manufacturing facility.",
                      is_demo=True)
    db.add(factory)
    db.flush()

    # ─── Products ─────────────────────────────────────────
    cell = Product(factory_id=factory.id, name="Battery Cell", description="Lithium-ion battery cell")
    module = Product(factory_id=factory.id, name="Battery Module", description="Battery module (12 cells)")
    pack = Product(factory_id=factory.id, name="Battery Pack", description="Complete battery pack assembly")
    db.add_all([cell, module, pack])
    db.flush()

    # ─── Machines ─────────────────────────────────────────
    machines_data = [
        ("Electrode Coater EC-01", ["electrode_coating"], 1, 1.0, 15, 25, 45),
        ("Electrode Coater EC-02", ["electrode_coating"], 1, 0.9, 15, 25, 45),
        ("Cell Assembler CA-01", ["cell_assembly"], 1, 1.0, 10, 18, 35),
        ("Cell Assembler CA-02", ["cell_assembly"], 1, 1.1, 10, 18, 35),
        ("Formation Cycler FC-01", ["formation_cycling"], 2, 1.0, 5, 30, 50),
        ("Module Assembler MA-01", ["module_assembly"], 1, 1.0, 20, 15, 30),
        ("Pack Assembler PA-01", ["pack_assembly"], 1, 1.0, 25, 20, 40),
        ("Quality Tester QT-01", ["quality_testing"], 2, 1.0, 5, 10, 20),
    ]
    machine_objs = []
    for name, caps, capacity, speed, setup, energy, cost in machines_data:
        m = Machine(factory_id=factory.id, name=name, status=MachineStatus.AVAILABLE,
                    capacity=capacity, processing_speed=speed, setup_time=setup,
                    energy_consumption=energy, operating_cost=cost)
        db.add(m)
        db.flush()
        for c in caps:
            db.add(MachineCapability(machine_id=m.id, capability=c))
        machine_objs.append(m)
    db.flush()

    # ─── Workers ──────────────────────────────────────────
    workers_data = [
        ("Wei Chen", "DAY", ["electrode_coating", "cell_assembly"], 2),
        ("Maria Santos", "DAY", ["cell_assembly", "quality_testing"], 2),
        ("James Park", "DAY", ["formation_cycling", "quality_testing"], 1),
        ("Aisha Patel", "DAY", ["module_assembly", "pack_assembly"], 2),
        ("Yuki Tanaka", "DAY", ["electrode_coating", "formation_cycling"], 1),
        ("Carlos Rivera", "NIGHT", ["cell_assembly", "module_assembly"], 2),
        ("Sophie Mueller", "NIGHT", ["quality_testing", "pack_assembly"], 1),
        ("David Kim", "FLEX", ["electrode_coating", "cell_assembly", "module_assembly"], 3),
    ]
    for name, shift, skills, overtime in workers_data:
        w = Worker(factory_id=factory.id, name=name, shift=shift, available=True,
                   max_overtime_hours=overtime)
        db.add(w)
        db.flush()
        for s in skills:
            db.add(WorkerSkill(worker_id=w.id, skill=s))
    db.flush()

    # ─── Materials ────────────────────────────────────────
    materials_data = [
        ("Cathode Material (NMC)", 5000, 0, 500, 85),
        ("Anode Material (Graphite)", 6000, 0, 600, 40),
        ("Electrolyte Solution", 3000, 0, 300, 120),
        ("Separator Film", 8000, 0, 800, 15),
        ("Cell Casing", 2000, 0, 200, 8),
        ("Bus Bars", 500, 0, 50, 25),
        ("Module Housing", 200, 0, 20, 150),
        ("BMS Board", 100, 0, 10, 300),
        ("Thermal Paste", 1000, 0, 100, 30),
        ("Pack Enclosure", 50, 0, 5, 500),
    ]
    mat_objs = []
    for name, total, reserved, reorder, cost in materials_data:
        m = Material(factory_id=factory.id, name=name, total_quantity=total,
                     reserved_quantity=reserved, reorder_level=reorder, unit_cost=cost)
        db.add(m)
        mat_objs.append(m)
    db.flush()

    # ─── Workflows ────────────────────────────────────────
    # Battery Cell Workflow
    cell_wf = ProductionWorkflow(product_id=cell.id, name="Cell Production",
                                  description="Full battery cell production process")
    db.add(cell_wf)
    db.flush()

    step1 = ProductionStep(workflow_id=cell_wf.id, name="Electrode Coating",
                           required_capability="electrode_coating", required_skill="electrode_coating",
                           processing_duration=45, setup_duration=15,
                           material_requirements=[
                               {"material_id": mat_objs[0].id, "quantity": 2},
                               {"material_id": mat_objs[1].id, "quantity": 2},
                           ],
                           preceding_steps=[])
    db.add(step1)
    db.flush()

    step2 = ProductionStep(workflow_id=cell_wf.id, name="Cell Assembly",
                           required_capability="cell_assembly", required_skill="cell_assembly",
                           processing_duration=30, setup_duration=10,
                           material_requirements=[
                               {"material_id": mat_objs[2].id, "quantity": 1},
                               {"material_id": mat_objs[3].id, "quantity": 2},
                               {"material_id": mat_objs[4].id, "quantity": 1},
                           ],
                           preceding_steps=[step1.id])
    db.add(step2)
    db.flush()

    step3 = ProductionStep(workflow_id=cell_wf.id, name="Formation Cycling",
                           required_capability="formation_cycling", required_skill="formation_cycling",
                           processing_duration=60, setup_duration=5,
                           preceding_steps=[step2.id])
    db.add(step3)
    db.flush()

    step4 = ProductionStep(workflow_id=cell_wf.id, name="Cell Quality Test",
                           required_capability="quality_testing", required_skill="quality_testing",
                           processing_duration=15, setup_duration=5,
                           preceding_steps=[step3.id])
    db.add(step4)
    db.flush()

    # Module Workflow
    mod_wf = ProductionWorkflow(product_id=module.id, name="Module Assembly",
                                 description="Battery module assembly from cells")
    db.add(mod_wf)
    db.flush()

    mod_step1 = ProductionStep(workflow_id=mod_wf.id, name="Module Assembly",
                                required_capability="module_assembly", required_skill="module_assembly",
                                processing_duration=40, setup_duration=20,
                                material_requirements=[
                                    {"material_id": mat_objs[5].id, "quantity": 12},
                                    {"material_id": mat_objs[6].id, "quantity": 1},
                                ],
                                preceding_steps=[])
    db.add(mod_step1)
    db.flush()

    mod_step2 = ProductionStep(workflow_id=mod_wf.id, name="Module Test",
                                required_capability="quality_testing", required_skill="quality_testing",
                                processing_duration=20, setup_duration=5,
                                preceding_steps=[mod_step1.id])
    db.add(mod_step2)
    db.flush()

    # ─── Orders ───────────────────────────────────────────
    now = datetime.utcnow()
    orders_data = [
        ("ORD-B001", cell.id, 10, OrderPriority.CRITICAL, now + timedelta(hours=48)),
        ("ORD-B002", cell.id, 5, OrderPriority.HIGH, now + timedelta(hours=72)),
        ("ORD-B003", module.id, 3, OrderPriority.NORMAL, now + timedelta(hours=96)),
        ("ORD-B004", cell.id, 8, OrderPriority.NORMAL, now + timedelta(hours=120)),
        ("ORD-B005", module.id, 2, OrderPriority.LOW, now + timedelta(hours=144)),
    ]
    for code, pid, qty, priority, deadline in orders_data:
        db.add(Order(factory_id=factory.id, product_id=pid, order_code=code,
                     quantity=qty, priority=priority, deadline=deadline,
                     status=OrderStatus.PENDING))

    db.commit()
    return factory


def seed_furniture_factory(db: Session) -> Factory:
    """Create a Furniture Manufacturing demo factory."""
    existing = db.query(Factory).filter(Factory.name == "Craftwood Furniture", Factory.is_demo == True).first()
    if existing:
        return existing

    factory = Factory(name="Craftwood Furniture", industry="Furniture Manufacturing",
                      description="Premium wood furniture manufacturing - tables, chairs, and bookshelves.",
                      is_demo=True)
    db.add(factory)
    db.flush()

    # Products
    table = Product(factory_id=factory.id, name="Oak Dining Table", description="Solid oak dining table, seats 6")
    chair = Product(factory_id=factory.id, name="Office Chair", description="Ergonomic office chair with lumbar support")
    shelf = Product(factory_id=factory.id, name="Bookshelf", description="5-shelf walnut bookshelf")
    db.add_all([table, chair, shelf])
    db.flush()

    # Machines
    machines_data = [
        ("CNC Router CNC-01", ["cutting", "carving"], 1, 1.0, 10, 12, 25),
        ("CNC Router CNC-02", ["cutting", "carving"], 1, 0.9, 10, 12, 25),
        ("Table Saw TS-01", ["cutting"], 1, 1.2, 5, 8, 15),
        ("Drill Press DP-01", ["drilling"], 1, 1.0, 3, 5, 10),
        ("Drill Press DP-02", ["drilling"], 1, 1.0, 3, 5, 10),
        ("Assembly Station AS-01", ["assembly"], 2, 1.0, 5, 3, 12),
        ("Assembly Station AS-02", ["assembly"], 2, 1.0, 5, 3, 12),
        ("Sanding Machine SD-01", ["sanding", "finishing"], 1, 1.0, 5, 6, 10),
        ("Finishing Booth FB-01", ["finishing", "painting"], 1, 1.0, 15, 10, 20),
        ("Upholstery Station US-01", ["upholstery"], 1, 1.0, 10, 2, 15),
    ]
    machine_objs = []
    for name, caps, capacity, speed, setup, energy, cost in machines_data:
        m = Machine(factory_id=factory.id, name=name, status=MachineStatus.AVAILABLE,
                    capacity=capacity, processing_speed=speed, setup_time=setup,
                    energy_consumption=energy, operating_cost=cost)
        db.add(m)
        db.flush()
        for c in caps:
            db.add(MachineCapability(machine_id=m.id, capability=c))
        machine_objs.append(m)
    db.flush()

    # Workers
    workers_data = [
        ("John Carpenter", "DAY", ["cutting", "carving", "sanding"], 2),
        ("Emily Wood", "DAY", ["cutting", "drilling"], 1),
        ("Mike Frame", "DAY", ["assembly", "drilling"], 2),
        ("Sarah Finish", "DAY", ["finishing", "painting", "sanding"], 1),
        ("Tom Builder", "DAY", ["assembly", "upholstery"], 2),
        ("Lisa Craft", "NIGHT", ["cutting", "assembly"], 1),
        ("Robert Stain", "FLEX", ["finishing", "painting", "sanding"], 3),
        ("Anna Weave", "DAY", ["upholstery", "assembly"], 1),
    ]
    for name, shift, skills, overtime in workers_data:
        w = Worker(factory_id=factory.id, name=name, shift=shift, available=True,
                   max_overtime_hours=overtime)
        db.add(w)
        db.flush()
        for s in skills:
            db.add(WorkerSkill(worker_id=w.id, skill=s))
    db.flush()

    # Materials
    materials_data = [
        ("Oak Lumber (board ft)", 500, 0, 50, 12),
        ("Walnut Lumber (board ft)", 300, 0, 30, 18),
        ("Plywood Sheets", 200, 0, 20, 25),
        ("Wood Screws (box)", 100, 0, 10, 8),
        ("Wood Glue (gallon)", 50, 0, 5, 15),
        ("Sandpaper Assorted", 200, 0, 20, 3),
        ("Wood Finish (gallon)", 40, 0, 4, 35),
        ("Fabric (yards)", 150, 0, 15, 20),
        ("Foam Padding (sheets)", 80, 0, 8, 12),
        ("Metal Hardware Kit", 100, 0, 10, 15),
    ]
    mat_objs = []
    for name, total, reserved, reorder, cost in materials_data:
        m = Material(factory_id=factory.id, name=name, total_quantity=total,
                     reserved_quantity=reserved, reorder_level=reorder, unit_cost=cost)
        db.add(m)
        mat_objs.append(m)
    db.flush()

    # Workflow: Oak Table
    table_wf = ProductionWorkflow(product_id=table.id, name="Table Production",
                                   description="Oak dining table manufacturing process")
    db.add(table_wf)
    db.flush()

    ts1 = ProductionStep(workflow_id=table_wf.id, name="Cut Table Top",
                         required_capability="cutting", required_skill="cutting",
                         processing_duration=30, setup_duration=10,
                         material_requirements=[{"material_id": mat_objs[0].id, "quantity": 8}],
                         preceding_steps=[])
    db.add(ts1)
    db.flush()

    ts2 = ProductionStep(workflow_id=table_wf.id, name="Cut Table Legs",
                         required_capability="cutting", required_skill="cutting",
                         processing_duration=20, setup_duration=5,
                         material_requirements=[{"material_id": mat_objs[0].id, "quantity": 4}],
                         preceding_steps=[])
    db.add(ts2)
    db.flush()

    ts3 = ProductionStep(workflow_id=table_wf.id, name="Drill Joints",
                         required_capability="drilling", required_skill="drilling",
                         processing_duration=15, setup_duration=3,
                         material_requirements=[],
                         preceding_steps=[ts1.id, ts2.id])
    db.add(ts3)
    db.flush()

    ts4 = ProductionStep(workflow_id=table_wf.id, name="Assemble Table",
                         required_capability="assembly", required_skill="assembly",
                         processing_duration=25, setup_duration=5,
                         material_requirements=[
                             {"material_id": mat_objs[3].id, "quantity": 1},
                             {"material_id": mat_objs[4].id, "quantity": 1},
                         ],
                         preceding_steps=[ts3.id])
    db.add(ts4)
    db.flush()

    ts5 = ProductionStep(workflow_id=table_wf.id, name="Sand & Finish",
                         required_capability="finishing", required_skill="finishing",
                         processing_duration=35, setup_duration=15,
                         material_requirements=[
                             {"material_id": mat_objs[5].id, "quantity": 2},
                             {"material_id": mat_objs[6].id, "quantity": 1},
                         ],
                         preceding_steps=[ts4.id])
    db.add(ts5)
    db.flush()

    # Workflow: Office Chair
    chair_wf = ProductionWorkflow(product_id=chair.id, name="Chair Production",
                                    description="Office chair manufacturing process")
    db.add(chair_wf)
    db.flush()

    cs1 = ProductionStep(workflow_id=chair_wf.id, name="Cut Frame Parts",
                         required_capability="cutting", required_skill="cutting",
                         processing_duration=20, setup_duration=5,
                         material_requirements=[{"material_id": mat_objs[2].id, "quantity": 2}],
                         preceding_steps=[])
    db.add(cs1)
    db.flush()

    cs2 = ProductionStep(workflow_id=chair_wf.id, name="Drill & Shape",
                         required_capability="drilling", required_skill="drilling",
                         processing_duration=15, setup_duration=3,
                         preceding_steps=[cs1.id])
    db.add(cs2)
    db.flush()

    cs3 = ProductionStep(workflow_id=chair_wf.id, name="Upholster Seat",
                         required_capability="upholstery", required_skill="upholstery",
                         processing_duration=25, setup_duration=10,
                         material_requirements=[
                             {"material_id": mat_objs[7].id, "quantity": 2},
                             {"material_id": mat_objs[8].id, "quantity": 1},
                         ],
                         preceding_steps=[])
    db.add(cs3)
    db.flush()

    cs4 = ProductionStep(workflow_id=chair_wf.id, name="Assemble Chair",
                         required_capability="assembly", required_skill="assembly",
                         processing_duration=20, setup_duration=5,
                         material_requirements=[
                             {"material_id": mat_objs[3].id, "quantity": 1},
                             {"material_id": mat_objs[9].id, "quantity": 1},
                         ],
                         preceding_steps=[cs2.id, cs3.id])
    db.add(cs4)
    db.flush()

    cs5 = ProductionStep(workflow_id=chair_wf.id, name="Final Finish",
                         required_capability="finishing", required_skill="finishing",
                         processing_duration=20, setup_duration=5,
                         material_requirements=[{"material_id": mat_objs[6].id, "quantity": 1}],
                         preceding_steps=[cs4.id])
    db.add(cs5)
    db.flush()

    # Orders
    now = datetime.utcnow()
    orders_data = [
        ("ORD-F001", table.id, 4, OrderPriority.HIGH, now + timedelta(hours=72)),
        ("ORD-F002", chair.id, 8, OrderPriority.CRITICAL, now + timedelta(hours=48)),
        ("ORD-F003", shelf.id, 3, OrderPriority.NORMAL, now + timedelta(hours=120)),
        ("ORD-F004", table.id, 2, OrderPriority.LOW, now + timedelta(hours=168)),
    ]
    for code, pid, qty, priority, deadline in orders_data:
        db.add(Order(factory_id=factory.id, product_id=pid, order_code=code,
                     quantity=qty, priority=priority, deadline=deadline,
                     status=OrderStatus.PENDING))

    db.commit()
    return factory


def seed_all(db: Session) -> list:
    """Seed all demo factories."""
    factories = []
    factories.append(seed_ev_battery_factory(db))
    factories.append(seed_furniture_factory(db))
    return factories
