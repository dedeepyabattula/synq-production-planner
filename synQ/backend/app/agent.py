"""
AI Agent for SynQ.

Uses Google Gemini when available, falls back to
deterministic template-based responses.
"""

import os
import json
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.models import (
    Factory, Machine, Worker, Material, Order, Schedule, ScheduleTask,
    Product, ProductionWorkflow, ProductionStep, Disruption, RecoveryPlan,
    MachineStatus, DisruptionType, OrderPriority
)
from app.simulation import analyze_impact, generate_recovery_plans


def parse_factory_setup(description: str) -> Dict[str, Any]:
    """
    Convert a natural-language factory description into a structured DRAFT
    matching the /factories/bulk request shape, for the manager to review and
    edit before saving (never saved automatically — see FactoryBuilder AI tab).

    Uses Gemini when GEMINI_API_KEY is set; otherwise falls back to a
    deterministic heuristic parser so the "AI-assisted factory setup" feature
    still works without an API key, per the hackathon fallback requirement.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            return _gemini_parse_factory_setup(description, gemini_key)
        except Exception:
            pass  # fall through to deterministic parser
    return _deterministic_parse_factory_setup(description)


def _gemini_parse_factory_setup(description: str, api_key: str) -> Dict[str, Any]:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    schema_hint = """Return ONLY valid JSON (no markdown fences, no commentary) matching exactly this shape:
{
  "factory": {"name": str, "industry": str, "description": str},
  "products": [{"name": str, "description": str}],
  "machines": [{"name": str, "capabilities": [str], "capacity": int, "processing_speed": 1.0, "setup_time": 0, "energy_consumption": 1.0, "operating_cost": 10.0}],
  "workers": [{"name": str, "skills": [str], "shift": "DAY", "hourly_cost": 20.0}],
  "materials": [{"name": str, "total_quantity": 1000, "unit_cost": 1.0}],
  "workflows": [{"product_name": str, "name": str, "steps": [
      {"name": str, "required_capability": str, "required_skill": str,
       "processing_duration": 30, "setup_duration": 5,
       "material_requirements": [], "preceding_step_indices": []}
  ]}],
  "orders": []
}
Rules: never invent specific real company names; use generic realistic names for machines/workers/materials (e.g. "Cutting Machine 1", "Worker 1") based on the counts and roles mentioned. Each workflow's steps should form a valid linear or branching DAG using preceding_step_indices (indices into that workflow's own steps list, each index must be SMALLER than the current step's index — no forward references, no cycles). If the description doesn't mention materials or workers, it's fine to return empty lists for those."""

    prompt = f"Factory description from a manager:\n\"{description}\"\n\n{schema_hint}"
    response = model.generate_content(prompt)
    text = response.text.strip()
    # Strip markdown fences if the model added them despite instructions
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    draft = json.loads(text)
    draft["_source"] = "ai"
    return draft


def _deterministic_parse_factory_setup(description: str) -> Dict[str, Any]:
    """
    Regex/keyword based fallback. Handles patterns like:
    "I run a furniture factory producing tables and chairs. We have 3 cutting
    machines and 2 assembly machines."
    Deliberately conservative: only extracts what it's reasonably confident
    about, and leaves the rest for the manager to fill in during review.
    """
    import re
    text = description.strip()
    lower = text.lower()

    # Industry / factory name: "<adjective> factory" e.g. "furniture factory"
    industry = "General Manufacturing"
    m = re.search(r'([a-zA-Z\- ]{2,30}?)\s+factory', lower)
    if m:
        candidate = m.group(1).strip()
        # Strip common lead-in phrases so "I run a furniture factory" -> "furniture"
        candidate = re.sub(
            r'^(i run|i operate|i own|we run|we operate|we own|my|our|a|an|the)\s+',
            '', candidate
        ).strip()
        candidate = re.sub(r'^(a|an|the)\s+', '', candidate).strip()
        if candidate:
            industry = candidate.title() + " Manufacturing"

    factory_name = industry.replace(" Manufacturing", "") + " Co."

    # Products: "producing X and Y" / "produces X, Y and Z" / "makes X and Y"
    products: List[str] = []
    m = re.search(r'(?:producing|produces|produce|makes|making|make)\s+([a-zA-Z0-9,\- ]+?)(?:\.|,\s*(?:we|and we|with)|$)', lower)
    if m:
        raw = m.group(1)
        raw = re.sub(r'\band\b', ',', raw)
        products = [p.strip().title() for p in raw.split(',') if p.strip()]

    if not products:
        products = ["Product A"]

    # Machines: "<N> <type> machines" e.g. "3 cutting machines", "2 assembly machines"
    machine_groups = re.findall(r'(\d+)\s+([a-zA-Z\-]+)\s+machines?', lower)
    # Workers: "<N> <type> workers" or "<N> operators"
    worker_groups = re.findall(r'(\d+)\s+([a-zA-Z\-]+)\s+(?:workers?|operators?|staff)', lower)

    machines = []
    capabilities_in_order = []
    for count_str, cap in machine_groups:
        count = max(1, int(count_str))
        cap = cap.strip()
        capabilities_in_order.append(cap)
        for i in range(count):
            machines.append({
                "name": f"{cap.title()} Machine {i+1}",
                "capabilities": [cap],
                "capacity": 1,
                "processing_speed": 1.0,
                "setup_time": 10,
                "energy_consumption": 5.0,
                "operating_cost": 25.0,
            })

    if not machines:
        machines = [{
            "name": "Machine 1", "capabilities": ["general"], "capacity": 1,
            "processing_speed": 1.0, "setup_time": 10, "energy_consumption": 5.0,
            "operating_cost": 25.0,
        }]
        capabilities_in_order = ["general"]

    workers = []
    if worker_groups:
        for count_str, role in worker_groups:
            count = max(1, int(count_str))
            for i in range(count):
                workers.append({
                    "name": f"{role.title()} Worker {i+1}",
                    "skills": capabilities_in_order[:1] or ["general"],
                    "shift": "DAY",
                    "hourly_cost": 20.0,
                })
    else:
        # Default: one worker per distinct capability so every machine has someone qualified
        for cap in dict.fromkeys(capabilities_in_order) or ["general"]:
            workers.append({
                "name": f"{cap.title()} Operator", "skills": [cap],
                "shift": "DAY", "hourly_cost": 20.0,
            })

    # Build one simple linear workflow per product using the detected capabilities
    # in the order they were mentioned. This is a reasonable starting default —
    # the manager reviews and can restructure it (branch, add steps, etc.)
    # before saving; SynQ does not require workflows to stay linear.
    workflows = []
    caps_for_workflow = list(dict.fromkeys(capabilities_in_order)) or ["general"]
    for pname in products:
        steps = []
        for i, cap in enumerate(caps_for_workflow):
            steps.append({
                "name": f"{cap.title()} Step",
                "required_capability": cap,
                "required_skill": cap,
                "processing_duration": 30,
                "setup_duration": 10,
                "material_requirements": [],
                "preceding_step_indices": [i - 1] if i > 0 else [],
            })
        workflows.append({
            "product_name": pname,
            "name": f"{pname} Production",
            "steps": steps,
        })

    return {
        "_source": "deterministic",
        "factory": {
            "name": factory_name,
            "industry": industry,
            "description": text,
        },
        "products": [{"name": p, "description": ""} for p in products],
        "machines": machines,
        "workers": workers,
        "materials": [],
        "workflows": workflows,
        "orders": [],
    }


def get_factory_summary(db: Session, factory_id: int) -> Dict[str, Any]:
    """Get a summary of the factory state for AI context."""
    factory = db.query(Factory).filter(Factory.id == factory_id).first()
    if not factory:
        return {"error": "Factory not found"}

    machines = db.query(Machine).filter(Machine.factory_id == factory_id).all()
    workers = db.query(Worker).filter(Worker.factory_id == factory_id).all()
    materials = db.query(Material).filter(Material.factory_id == factory_id).all()
    orders = db.query(Order).filter(Order.factory_id == factory_id).all()
    products = db.query(Product).filter(Product.factory_id == factory_id).all()

    active_schedule = db.query(Schedule).filter(
        Schedule.factory_id == factory_id,
        Schedule.status == "ACTIVE"
    ).first()

    return {
        "factory": {"id": factory.id, "name": factory.name, "industry": factory.industry},
        "machines": [{"id": m.id, "name": m.name, "status": m.status.value if hasattr(m.status, 'value') else str(m.status)} for m in machines],
        "workers": [{"id": w.id, "name": w.name, "available": w.available, "shift": w.shift} for w in workers],
        "materials": [{"id": m.id, "name": m.name, "available": m.total_quantity - m.reserved_quantity} for m in materials],
        "orders": [{"id": o.id, "code": o.order_code, "priority": o.priority.value if hasattr(o.priority, 'value') else str(o.priority), "deadline": o.deadline.isoformat()} for o in orders],
        "products": [{"id": p.id, "name": p.name} for p in products],
        "has_active_schedule": active_schedule is not None,
        "active_schedule_id": active_schedule.id if active_schedule else None,
    }


def parse_natural_language_disruption(message: str, factory_summary: Dict) -> Optional[Dict[str, Any]]:
    """Parse natural language into a structured disruption. Deterministic fallback."""
    msg = message.lower().strip()

    # Try to detect disruption type
    disruption_type = None
    affected_resource_id = None
    affected_resource_type = None
    params = {}

    # Machine breakdown patterns
    machine_keywords = ["machine", "broke", "broken", "failed", "failure", "down", "breakdown"]
    worker_keywords = ["worker", "absent", "absence", "sick", "unavailable", "left"]
    material_keywords = ["material", "shortage", "out of", "ran out", "supply"]
    urgent_keywords = ["urgent", "rush", "emergency order", "new order"]
    priority_keywords = ["priority", "prioritize", "change priority", "reprioritize"]

    if any(k in msg for k in machine_keywords):
        disruption_type = "MACHINE_BREAKDOWN"
        affected_resource_type = "machine"
        # Try to find which machine
        for m in factory_summary.get("machines", []):
            if m["name"].lower() in msg or m["name"].split()[-1].lower() in msg:
                affected_resource_id = m["id"]
                break

        # Try to find duration
        import re
        hours_match = re.search(r'(\d+)\s*hours?', msg)
        if hours_match:
            params["duration_hours"] = int(hours_match.group(1))
        else:
            params["duration_hours"] = 2  # default

    elif any(k in msg for k in worker_keywords):
        disruption_type = "WORKER_ABSENCE"
        affected_resource_type = "worker"
        for w in factory_summary.get("workers", []):
            if w["name"].lower() in msg:
                affected_resource_id = w["id"]
                break
        params["duration_hours"] = 8  # default full shift

    elif any(k in msg for k in material_keywords):
        disruption_type = "MATERIAL_SHORTAGE"
        affected_resource_type = "material"
        for m in factory_summary.get("materials", []):
            if m["name"].lower() in msg:
                affected_resource_id = m["id"]
                break
        params["shortage_amount"] = 50

    elif any(k in msg for k in urgent_keywords):
        disruption_type = "URGENT_ORDER"
        params["description"] = message

    elif any(k in msg for k in priority_keywords):
        disruption_type = "PRIORITY_CHANGE"
        for o in factory_summary.get("orders", []):
            if o["code"].lower() in msg:
                params["order_id"] = o["id"]
                break
        params["new_priority"] = "CRITICAL"

    if disruption_type:
        return {
            "disruption_type": disruption_type,
            "description": message,
            "affected_resource_id": affected_resource_id,
            "affected_resource_type": affected_resource_type,
            "parameters": params,
        }
    return None


async def process_ai_message(
    db: Session,
    factory_id: int,
    message: str
) -> Dict[str, Any]:
    """Process a natural language message from the manager."""
    factory_summary = get_factory_summary(db, factory_id)
    if "error" in factory_summary:
        return {"response": factory_summary["error"], "actions": [], "structured_data": {}}

    # Try to parse as a disruption command
    parsed = parse_natural_language_disruption(message, factory_summary)

    # Try Gemini first
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            return await _gemini_response(message, factory_summary, parsed, gemini_key)
        except Exception as e:
            pass  # Fall through to deterministic fallback

    # Deterministic fallback
    return _deterministic_response(message, factory_summary, parsed)


async def _gemini_response(
    message: str,
    factory_summary: Dict,
    parsed: Optional[Dict],
    api_key: str
) -> Dict[str, Any]:
    """Use Gemini to generate a contextual response."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    system_prompt = f"""You are SynQ AI, a production planning assistant for factory managers.
You are helping manage: {factory_summary['factory']['name']} ({factory_summary['factory']['industry']})

Current factory state:
- {len(factory_summary['machines'])} machines
- {len(factory_summary['workers'])} workers
- {len(factory_summary['materials'])} materials
- {len(factory_summary['orders'])} active orders
- Active schedule: {'Yes' if factory_summary['has_active_schedule'] else 'No'}

Machines: {json.dumps(factory_summary['machines'])}
Orders: {json.dumps(factory_summary['orders'])}

RULES:
1. Only reference actual factory data provided above.
2. Never fabricate metrics, machine names, or order details.
3. If a disruption is detected, acknowledge it and describe what should happen next.
4. Be concise and actionable.
5. If the user seems to be reporting a disruption, confirm what you understood.
"""

    context = f"Manager says: {message}"
    if parsed:
        context += f"\n\nParsed disruption: {json.dumps(parsed)}"

    response = model.generate_content(f"{system_prompt}\n\n{context}")

    return {
        "response": response.text,
        "actions": [{"type": "disruption", "data": parsed}] if parsed else [],
        "structured_data": parsed or {},
    }


def _deterministic_response(
    message: str,
    factory_summary: Dict,
    parsed: Optional[Dict]
) -> Dict[str, Any]:
    """Generate a deterministic template-based response."""
    msg = message.lower().strip()
    factory_name = factory_summary["factory"]["name"]

    # Status queries
    if any(k in msg for k in ["status", "overview", "how is", "dashboard", "summary"]):
        machines = factory_summary["machines"]
        available = sum(1 for m in machines if m["status"] == "AVAILABLE")
        orders = factory_summary["orders"]
        critical = sum(1 for o in orders if o["priority"] == "CRITICAL")

        return {
            "response": (
                f"**{factory_name} Status Overview**\n\n"
                f"• **Machines**: {available}/{len(machines)} available\n"
                f"• **Workers**: {sum(1 for w in factory_summary['workers'] if w['available'])}/{len(factory_summary['workers'])} available\n"
                f"• **Orders**: {len(orders)} active ({critical} critical)\n"
                f"• **Active Schedule**: {'Yes' if factory_summary['has_active_schedule'] else 'No - generate a schedule first'}\n\n"
                f"Use the Dashboard for real-time monitoring."
            ),
            "actions": [],
            "structured_data": {},
        }

    # Disruption detected
    if parsed:
        d_type = parsed["disruption_type"].replace("_", " ").title()
        resource_name = "Unknown"

        if parsed["affected_resource_type"] == "machine":
            for m in factory_summary["machines"]:
                if m["id"] == parsed["affected_resource_id"]:
                    resource_name = m["name"]
                    break
        elif parsed["affected_resource_type"] == "worker":
            for w in factory_summary["workers"]:
                if w["id"] == parsed["affected_resource_id"]:
                    resource_name = w["name"]
                    break

        return {
            "response": (
                f"**Disruption Detected: {d_type}**\n\n"
                f"I understood that **{resource_name}** is affected.\n\n"
                f"**Recommended next steps:**\n"
                f"1. Go to the **Disruption Simulator** to formalize this disruption\n"
                f"2. The system will automatically analyze impact on current schedule\n"
                f"3. Review the generated recovery plans in the **Recovery Center**\n"
                f"4. Compare trade-offs and approve a recovery plan\n\n"
                f"Would you like me to create this disruption automatically?"
            ),
            "actions": [{"type": "disruption_detected", "data": parsed}],
            "structured_data": parsed,
        }

    # What-if queries
    if "what if" in msg or "what happens" in msg:
        return {
            "response": (
                f"**What-If Simulation Mode**\n\n"
                f"To run a what-if scenario:\n"
                f"1. Go to the **Disruption Simulator**\n"
                f"2. Check the 'What-If Mode' option\n"
                f"3. Configure your hypothetical disruption\n"
                f"4. The system will simulate without modifying the active schedule\n\n"
                f"You can compare the simulated schedule against the current one."
            ),
            "actions": [],
            "structured_data": {},
        }

    # Protect orders
    if "protect" in msg:
        return {
            "response": (
                f"**Order Protection**\n\n"
                f"To protect critical orders, adjust the **Priority Weights** in the Recovery Center:\n"
                f"• Set **Deadline** weight to maximum (100)\n"
                f"• The recovery engine will prioritize plans that protect deadlines\n\n"
                f"Current critical orders: {sum(1 for o in factory_summary['orders'] if o['priority'] == 'CRITICAL')}"
            ),
            "actions": [],
            "structured_data": {},
        }

    # Default help
    return {
        "response": (
            f"**SynQ AI Assistant** — {factory_name}\n\n"
            f"I can help you with:\n"
            f"• **Factory status** — Ask about current machine/worker/order status\n"
            f"• **Disruptions** — Report issues like 'Machine X failed for 3 hours'\n"
            f"• **What-If** — Ask 'What happens if worker Y is absent?'\n"
            f"• **Priorities** — 'Protect all critical orders' or 'Prioritize order O-104'\n\n"
            f"Try: *'What is the current factory status?'*"
        ),
        "actions": [],
        "structured_data": {},
    }
