# SynQ

**"The factory changes. The plan adapts."**

SynQ is an AI-assisted, industry-agnostic production planning and disruption
recovery platform for factory managers. It turns a disruption (a machine
breakdown, a worker absence, an urgent order, ...) into a set of independently
validated recovery plans, compares their trade-offs, explains the AI's
recommendation, and only ever updates the live schedule once a manager
approves a plan.

```
Factory → Current Schedule → Disruption → Impact Analysis →
Recovery Plans → Trade-Off Comparison → AI Recommendation →
Human Approval → Updated Schedule → Audit History
```

Nothing about SynQ is hardcoded to a specific factory. Machines, workers,
products, workflows, materials, and orders are all configured data — the two
demo factories (an EV battery plant and a furniture shop) are just seed data,
not special-cased logic.

---

## Architecture

```
backend/            FastAPI + SQLAlchemy (SQLite by default)
  app/models.py      Generic factory data model (machines, workers, workflows,
                      materials, orders — all ID/relationship driven, no
                      hardcoded factory logic)
  app/scheduler.py    Deterministic scheduling engine — the single source of
                      truth for all times, costs, delays, and utilization.
                      Handles dependency DAGs, machine/worker/material
                      constraints, and cycle detection.
  app/simulation.py   Impact analysis, recovery-plan generation (4 distinct
                      strategies), weighted scoring/recommendation, and
                      approve/reject/modify/apply logic. Enforces scenario
                      isolation (What-If never touches the active schedule).
  app/agent.py        AI layer: natural-language chat, disruption/preference
                      extraction, and AI-assisted factory setup. Falls back to
                      deterministic logic when no AI key is configured — the
                      app is fully demoable without any API key.
  app/api.py          All REST endpoints.

frontend/            React + TypeScript + Vite + Tailwind
  src/pages/          Dashboard, Factory Builder (create/view), Production
                      Schedule (Gantt), Disruption Simulator, Recovery
                      Center, Approval Center, History/Audit.
  src/components/     Gantt chart, AI chat widget, layout/nav.
```

**Design principle enforced throughout:** the AI can reason, interpret
requests, and explain trade-offs, but it never invents a schedule time, a
feasibility verdict, a cost, or a delay number — those always come from the
deterministic scheduler in `scheduler.py` / `simulation.py`. Every candidate
schedule is validated (`validate_schedule`) before it is allowed to become
the active schedule.

---

## Features

- **Dynamic factory model** — arbitrary machines/capabilities, worker
  skills/shifts, materials, multi-step production workflows with dependency
  DAGs (cycles rejected), and customer orders with priority/deadline.
- **Two ways to create a factory**: a manual builder, and an AI-assisted flow
  that parses a plain-language description ("I run a furniture factory
  producing tables and chairs, with 3 cutting machines and 2 assembly
  machines...") into structured, **editable** data — nothing is saved until
  you review and confirm it.
- **Deterministic scheduler** — respects machine capability/availability,
  worker skill/availability, material stock, task dependencies, and setup
  time; detects circular dependencies; produces the same result for the same
  input every time.
- **Disruption simulator** — machine breakdown, worker absence, material
  shortage, urgent order, priority change, capacity reduction, availability
  change.
- **Impact analysis** — what changed, what's affected (direct + downstream
  tasks), why, and what's at risk (deadlines, orders), plus alternative
  machines/workers where available.
- **4 independently-generated, independently-validated recovery strategies**
  per disruption (reroute, protect critical deadlines, minimize cost, balance
  load) — never a hardcoded winner.
- **Manager-adjustable weights** (deadline / cost / delay / utilization /
  energy) that can change which plan is recommended.
- **Human-in-the-loop**: Approve, Modify (adjust exclusions/priorities and
  re-validate), or Reject — with a full audit trail.
- **What-If / scenario isolation**: a what-if disruption can be simulated and
  compared, but can never be approved into the active schedule.
- **AI chat** for natural-language commands ("Machine CNC-02 failed for 3
  hours", "protect all critical orders", "what happens if M-03 fails for 4
  hours?") — interpreted into structured constraints, then run through the
  same deterministic engine.

---

## Local Setup

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

On first boot the backend creates `synq.db` (SQLite) and seeds two demo
factories automatically (seeding is idempotent — it checks for existing demo
data before inserting, so re-starting the server won't duplicate them).

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173 (Vite's default dev port)

### Environment Variables

| Variable | Where | Required? | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | backend | No | Enables Gemini-powered AI chat and AI-assisted factory setup. Without it, both features still work via a deterministic fallback (regex/rule-based parsing) — the full hackathon demo does **not** require this key. |
| `DATABASE_URL` | backend | No | Defaults to `sqlite:///./synq.db`. Set to a Postgres URL (`postgresql://...`) for a production deployment — see Deployment below. |
| `CORS_ORIGINS` | backend | No | Comma-separated allowed origins. Defaults to `*` (fine for local dev / a quick demo deploy). Set to your exact deployed frontend URL for a locked-down production deployment. |
| `VITE_API_URL` | frontend (build-time) | No | Defaults to `http://localhost:8000/api`. **Must** be set to your deployed backend's `/api` URL when deploying the frontend (see below). |

---

## Demo Factory Data

Two seeded demo factories, generated fresh (idempotently) on every backend
startup:

1. **EV Battery Plant** — electrode coating → cell assembly → module → pack,
   5 orders, mixed priorities, machines with different capabilities
   (coating, assembly, testing...).
2. **Craftwood Furniture** — cutting → assembly → finishing, 3 orders,
   matches the "furniture factory" example used throughout this brief.

Switch between them (or create a new one) from the factory switcher in the
top navigation bar.

---

## Hackathon Demo Flow

1. Open the **Dashboard** for the EV Battery Plant (loaded by default) —
   shows machine/worker/material/order status at a glance.
2. Go to **Production Schedule** — generate the initial schedule if one
   doesn't exist yet, see the Gantt chart.
3. Go to **Disruption Simulator** — trigger a **Machine Breakdown** on one of
   the coating machines.
4. You're taken to **Recovery Center**, which immediately shows the impact
   analysis (what changed / what's affected / why / what's at risk) and 4
   recovery plans (Reroute, Protect Critical, Minimize Cost, Balance Load).
5. Compare cost / delay / deadline adherence / utilization across the plans;
   note the AI-recommended plan and its explanation.
6. Drag the priority-weight sliders toward "Deadline" or "Cost" and hit
   **Recalculate** — watch the recommended plan change.
7. Click **Modify** on a plan to exclude an additional machine and
   re-validate, or **Reject** a plan you don't want.
8. Click **Approve & Apply** on your chosen plan — the active schedule
   updates, and the Production Schedule page reflects it.
9. Go to **History** — see the full audit trail (disruption → plans
   generated → approval → applied).
10. Go back to **Disruption Simulator**, toggle **What-If mode**, and run a
    second disruption — show that its recovery plans **cannot** be applied
    (the Approve button is disabled with an explanation) and the real
    schedule is untouched.
11. Go to the factory switcher → **New Factory** → **AI-Assisted Setup** →
    type something like *"I run a metal fabrication shop making brackets and
    frames. We have 2 welding machines and 1 cutting machine."* → review the
    generated draft (editable) → **Create Factory** → generate its schedule.

---

## Deployment

The project is not deployed from this environment (I don't have a way to
reach an external hosting provider from here), but it's set up to deploy
cleanly. Below are exact steps for a typical free-tier setup.

### Backend → Render (or Railway/Fly.io — same idea)

1. Push this repo to GitHub.
2. Create a new **Web Service** on Render, pointing at the `backend/`
   directory.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Environment variables:
   - `GEMINI_API_KEY` (optional)
   - `CORS_ORIGINS` = the frontend URL you'll get in the next section (you
     can leave this unset / `*` for a quick demo deploy)
   - `DATABASE_URL` (optional — see SQLite limitation below)
6. Your backend URL will look like `https://synq-backend.onrender.com`. The
   API is under `/api`, e.g. `https://synq-backend.onrender.com/api/factories`.

### Frontend → Vercel (or Netlify)

1. Import the same repo, set the project root to `frontend/`.
2. Build command: `npm run build`
3. Output directory: `dist`
4. Environment variable: `VITE_API_URL` = `https://synq-backend.onrender.com/api`
   (your actual Render URL + `/api`)
5. Your frontend URL will look like `https://synq.vercel.app`.
6. Go back to the backend's `CORS_ORIGINS` env var and set it to your exact
   Vercel URL (`https://synq.vercel.app`), then redeploy the backend.

### SQLite limitation

The default `sqlite:///./synq.db` file lives on the backend's local disk.
On most free-tier hosts (Render's free web services included) this disk is
**ephemeral** — it resets on every redeploy/restart, which is fine for a demo
(seed data regenerates automatically) but means any factories/schedules a
judge creates during a live session will be lost if the service restarts. For
anything longer-lived, set `DATABASE_URL` to a managed Postgres instance
(e.g. Render's free Postgres, Supabase, or Neon) — you'll also need to add
`psycopg2-binary` to `requirements.txt` — and the app will use it with no
other code changes, since all queries go through SQLAlchemy.

### Final URL format

- Backend: `https://<your-backend-service>.onrender.com/api/...`
- Frontend: `https://<your-frontend-project>.vercel.app`

---

## Known Limitations

- **SQLite on ephemeral disk** in the default deploy path (see above).
- **Ties in recommendations**: for a mild disruption with ample slack
  capacity, multiple recovery strategies can converge on numerically
  identical schedules — in that case changing weights won't change the
  winner because there's genuinely nothing to differentiate. Try a more
  severe disruption (a longer breakdown, or one affecting a
  scarcer/higher-utilization machine) to see weights clearly change the
  recommendation.
- **Every schedule generation is a full reschedule**, not an incremental
  patch — this keeps the scheduler simple and fully deterministic, but means
  recovery plans reschedule every order, not just the disrupted ones (the
  metrics/comparison still reflect only what changed relative to the active
  schedule).
- **AI-assisted factory setup** (both the Gemini path and the deterministic
  fallback) produces a reasonable **starting draft**, not a guaranteed-perfect
  parse of arbitrary prose — it's designed to be reviewed and edited before
  saving, per the "AI-generated data must be reviewed before saving"
  requirement, not to be perfect out of the box.
- The **Modify** action's UI is intentionally minimal (a prompt for
  additional excluded machine IDs) rather than a full constraint-builder —
  the backend endpoint (`/recovery-plans/{id}/modify`) supports excluded
  workers and order-priority overrides too, but the frontend only exposes
  the machine-exclusion case given the time available.
