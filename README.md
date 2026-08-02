# NutriFlavorOS

NutriFlavorOS is an **experimental household food-planning, transactional inventory, human-reviewed plan and preparation operations, immutable-evidence, and governed research platform**.

> **Safety boundary:** NutriFlavorOS is not clinically validated, is not a medical device, does not verify allergies or medication interactions, does not declare food safe, does not infer presence, and does not control appliances. High-risk capabilities remain gated until their data, validation, human-review, approval, rollback, and monitoring requirements are complete.

## Synchronized repository contract

Development is performed through coherent commits directly to `main`. Code, tests, migrations, fixtures, OpenAPI contracts, frontend bindings, catalogs, CI, and documentation must evolve together.

- Database migration head: **`20260802_0013`**
- API version: **`0.9.0`**
- OpenAPI release contract: **`2026-08-02.3`**
- Food-evidence frontend binding contract: **`2026-08-01.2`**
- Preparation-operations frontend binding contract: **`2026-08-02.2`**
- Household-plan frontend binding contract: **`2026-08-02.3`**
- Governed research catalog: **`2026-08-01.3`**

## Product platform

### Identity and household access

- Argon2 passwords and signed JWTs.
- Startup refusal for weak or missing signing secrets.
- Explicit profile-completion state; signup does not fabricate physiology or nutrition targets.
- Owner, editor, and viewer household roles with `404` non-disclosure.
- Hashed, expiring, email-bound, single-use invitations.

### Transactional household food state

- Versioned pantry lots with quantity intervals, units, provenance, expiry/open times, and optimistic concurrency.
- Append-only inventory and leftover events.
- FEFO allocation, expired-stock exclusion, reservations, overbooking prevention, shopping reconciliation, and batch grouping.
- Full-request idempotency fingerprints and PostgreSQL race probes.

### Deterministic meal planning

- Hard allergy and dietary filtering before optimization.
- Household target aggregation.
- Nutrition, taste, cost, cuisine, diversity, repetition, and pantry objectives.
- Persisted plan documents, portions, warnings, diagnostics, shopping requirements, and optional reservations.
- Pareto, optional CP-SAT/MILP, robust-scenario, and exact small-instance comparators.

## Household plan review lifecycle

Migration `20260802_0013` separates **generation** from **approval**.

Every generated household plan begins as `draft` with optimistic version `1`. The protected `/household/plans` workspace lets the household:

- inspect exact plan ID, schema, version, meals, portions, warnings, and timestamps;
- record a human decision reason;
- approve an exact version as owner;
- cancel a draft or approved plan as editor/owner;
- inspect append-only transition events.

Approval records the actor and UTC approval time, increments the version, and creates one constrained event. Identical retries collapse; contradictory idempotency reuse and stale versions fail closed.

Cancellation is atomic with downstream consequences:

- active reservations for the plan are released;
- dependent draft or approved preparation schedules are invalidated;
- plan and schedule events retain the cancellation provenance and affected-row counts.

Preparation schedule creation accepts a source plan only when the exact plan ID/version belongs to the household and is currently `approved`. Generation or persistence alone is not approval.

See [Household Plan Lifecycle](docs/HOUSEHOLD_PLAN_LIFECYCLE.md).

## Immutable reviewed evidence

NutriFlavorOS retains immutable version histories for:

- ingredient conversions;
- storage policies;
- recipe preparation profiles.

Each reviewed record carries natural/version identity, source, reviewer, UTC review time, SHA-256 content hash, supersession, evidence state, and active status. Exact evidence versions remain readable after withdrawal.

Dry-run and atomic apply tools:

```bash
python scripts/import_food_evidence.py reviewed-food-evidence.json
python scripts/import_food_evidence.py reviewed-food-evidence.json \
  --apply --operator reviewer@example.org

python scripts/manage_food_evidence_lifecycle.py lifecycle-actions.json
python scripts/manage_food_evidence_lifecycle.py lifecycle-actions.json \
  --apply --operator reviewer@example.org
```

## Deterministic preparation scheduling

The scheduler accepts only explicit resources, capacities, non-overlapping availability windows, durations, deadlines, priorities, dependencies, and provenance.

- Explicitly empty or mixed calendar forms fail closed.
- A task must fit in one continuous containing window across every demanded resource.
- Tasks cannot bridge unavailable gaps.
- The heuristic and bounded exact comparator share capacity, dependency, deadline, and window semantics.
- Structured infeasibility, utilization, peak use, critical path, and replay diagnostics are retained.

## Persisted preparation operations

Migrations `20260801_0009` through `20260801_0012` provide:

- immutable reviewed household resource calendars;
- structured calendar builder at `/preparation/operations/calendars/new`;
- complete canonical occurrence documents;
- exact preparation-profile versions;
- optional approved source-plan ID/version;
- complete scheduler request/hash and deterministic response;
- combined schedule hashes;
- replay before persistence and approval;
- draft, approved, invalidated, completed, and cancelled lifecycle;
- append-only schedule events;
- provenance coverage dashboard.

The calendar builder includes resource templates, dynamic multi-window editing, strict validation, operational predecessor diff, canonical JSON import/export, mandatory review confirmations, automatic stale-review reset, and owner-only activation.

The schedule API rejects unapproved or stale source plans. Cancelling an approved plan invalidates dependent operational schedules in the same transaction.

See [Preparation Operations](docs/PREPARATION_OPERATIONS.md).

## Frontend

Protected routes include:

- dashboard and personal meal planner;
- household, pantry, invitations, leftovers, reservations, shopping, and batch preparation;
- household plan review;
- preparation profile editor and reviewed pipeline;
- preparation operations;
- structured resource-calendar builder;
- preparation provenance coverage;
- research registry and settings.

TypeScript clients for food evidence, preparation operations, and household plan lifecycle are mechanically checked against generated OpenAPI.

## Governed research platform

Catalog `2026-08-01.3` defines:

- **37 task contracts**
- **30 dataset families**
- **75 model or algorithm families**
- **29 experiment contracts**
- **39 feature contracts**

Readiness is explicit. Runtime importability does not imply enablement, training evidence, quality, or clinical validation.

Executable offline families include retrieval and ranking baselines, temporal ranking evaluation, dense and intermittent-demand forecasting, uncertainty baselines, Pareto/CP-SAT/MILP/robust planning, exact preparation comparison, FEFO replay, and forecast-to-inventory evaluation.

## Validation matrix

The direct-`main` workflow is configured to run:

- compile, dependency, backend, repository, Alembic, catalog, OpenAPI, and three frontend-binding gates;
- planner, preparation, ranking, forecasting, inventory, and closed-loop benchmarks;
- fresh SQLite and PostgreSQL migrations;
- evidence import and lifecycle manifests;
- PostgreSQL inventory, idempotency, evidence, preparation, preparation-operations, and household-plan lifecycle race probes;
- frontend lint, Vitest, Vite build, and container build;
- retained machine-readable reports.

A committed test or configured workflow is not an executed green-build or safety claim. The exact hosted run must be inspected before the current commit is described as green.

## Local setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows PowerShell
pip install -r backend/requirements.txt
alembic upgrade head
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend
npm ci
npm run dev
```

PostgreSQL is recommended for hosted or concurrent deployments.

## Deliberately incomplete or disabled

- Clinical, medication, allergy-safety, food-safety, and health-outcome claims are not validated.
- Approved-plan occurrence generation and serving/deadline confirmation remain incomplete.
- Raw schedule-bundle JSON still needs a structured review replacement.
- Per-task execution/deviation events, timers, and reminders remain incomplete.
- Joint meal/preparation repair remains offline future work.
- Authenticated Playwright/PostgreSQL and automated accessibility coverage remain incomplete.
- Vision, multimodal nutrition, constrained generation, graph learning, causal/off-policy promotion, continual/federated personalization, privacy-sensitive learning, sustainability claims, and autonomous appliance/procurement control remain gated research.
- The latest exact hosted workflow has not yet been observed green in this execution context.

## Documentation

- [Exhaustive Repository Audit](docs/EXHAUSTIVE_AUDIT_2026-08-02.md)
- [Plan Lifecycle Audit Continuation](docs/EXHAUSTIVE_AUDIT_2026-08-02_PLAN_LIFECYCLE.md)
- [Implementation Status](docs/IMPLEMENTATION_STATUS.md)
- [Engineering and Research Roadmap](docs/ROADMAP.md)
- [Household Plan Lifecycle](docs/HOUSEHOLD_PLAN_LIFECYCLE.md)
- [Preparation Operations](docs/PREPARATION_OPERATIONS.md)
- [Governed Research Platform](docs/RESEARCH_PLATFORM.md)
