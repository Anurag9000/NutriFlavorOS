# NutriFlavorOS

NutriFlavorOS is an **experimental household food-planning, inventory,
preparation-operations, immutable-evidence, and governed research platform**.
It combines deterministic meal planning, transactional pantry and leftover
workflows, role-aware collaboration, reviewed evidence histories,
dependency-aware preparation scheduling, ranking evaluation, demand
forecasting, and perishable-inventory replay.

> **Safety status:** NutriFlavorOS is not clinically validated, is not a medical
> device, and must not autonomously diagnose, treat, manage allergies or
> medication interactions, declare food safe, or make procurement decisions.
> Experimental and high-risk capabilities remain disabled until their declared
> data, validation, calibration, human-review, artifact, approval, rollback,
> and monitoring gates are complete.

## Repository contract

Development is performed directly on `main` in coherent commits. Code, tests,
migrations, fixtures, capability registrations, catalog declarations, CI, and
public documentation must remain synchronized. The repository does not use
feature pull requests or automated dependency-update branches.

- Database migration head: **`20260801_0008`**.
- OpenAPI release contract: **`2026-08-01.2`**.
- Effective governed research catalog: **`2026-08-01.3`**.

## Product platform

### Identity and household access

- Argon2 password hashing and signed JWT bearer tokens.
- Startup refusal for missing or weak signing secrets.
- Authenticated self-only user resources.
- Explicit profile-completion state; signup never fabricates physiological
  values or nutrition targets.
- Owner, editor, and viewer household roles with object-access `404` behavior.
- Email-bound, expiring invitation tokens stored only as hashes.
- One-time invitation token handoff, replacement, revocation, exact-email
  acceptance, and retry-safe repeated acceptance.
- Linked accounts require accepted invitations; ordinary member operations
  cannot transfer ownership.

### Transactional household food state

- Pantry lots with canonical ingredient, display name, quantity interval,
  unit, source, expiry/open timestamps, metadata, and optimistic version.
- Leftovers linked to real recipes and optional source plans.
- Append-only purchase, consumption, discard, adjustment, leftover,
  reservation, and reservation-commit events.
- Full request fingerprints written atomically with inventory events.
- Contradictory idempotency-key reuse and ambiguous legacy keys fail closed.
- Negative-stock and cross-dimensional subtraction prevention.
- Earliest-expiry allocation and expired-stock exclusion.
- Stock reservations with active, released, consumed, and expired states.
- Cross-plan overbooking prevention and PostgreSQL concurrency probes.
- Shopping reconciliation, batch-preparation grouping, and audit-event views.

### Meal planning

- Deterministic horizon-level beam search.
- Hard allergy and dietary filtering before optimization.
- Joint calorie, macro, taste, cost, cuisine, variety, repeat, and pantry
  objective components.
- Household target aggregation from complete linked profiles or explicit
  member overrides.
- Structured infeasibility and disclosed non-safety relaxation diagnostics.
- Persisted plan schema, portions, warnings, provenance, and optimizer
  diagnostics.
- Optional pantry reservation after household plan generation.
- Pareto, optional CP-SAT, optional MILP, robust scenario stress, and
  worst-case robust enumeration as offline comparators.

## Immutable reviewed evidence

### Preparation evidence

Preparation timing, dependencies, resource demands, and unattended-cooking
suitability are never inferred from recipe titles. Each preparation profile
retains recipe and schema versions, reviewed serving range, task DAG, duration
interval, resource demands, activity/supervision declarations, source,
reviewer, UTC review time, SHA-256 content hash, supersession link, and active
state.

Identical same-version registration is idempotent. Contradictory reuse is
rejected. One active reviewed profile is permitted per recipe. Batch imports
are all-or-nothing and emit integrity-checked manifests.

```bash
python scripts/import_preparation_profiles.py reviewed-profiles.json
python scripts/import_preparation_profiles.py reviewed-profiles.json \
  --apply --operator reviewer@example.org
```

### Conversion and storage-policy evidence

Migration `20260801_0007` introduced immutable histories for:

- ingredient-specific unit conversions;
- reviewed storage policies;
- exact leftover-to-storage-policy-version links.

Each immutable version retains its natural key, version, source provenance,
evidence status, reviewer, UTC review time, content hash, supersession link,
and active state. Automatic conversion requires one exact active reviewed
record and returns the evidence ID, version, hash, source, reviewer, and output
interval.

A new leftover selects one active reviewed policy version, validates storage
state and expiry bounds, persists the exact version link, and writes the
policy ID/version/hash into the inventory event in the same transaction.
Frozen `quality_guidance` is never converted into a safety-expiry timestamp.

Reviewed conversions and policies can be validated and imported together:

```bash
python scripts/import_food_evidence.py reviewed-food-evidence.json
python scripts/import_food_evidence.py reviewed-food-evidence.json \
  --apply --operator reviewer@example.org
```

The importer performs typed preflight, deterministic natural-key locking,
all-or-nothing registration, idempotent reapplication, exact supersession,
source-file hashing, and durable pre- and post-apply manifests.

### Append-only evidence lifecycle

Migration `20260801_0008` adds audited deactivation and rejection without
rewriting immutable evidence content. Each lifecycle event records the exact
target, action, actor, reason, metadata, idempotency key, request fingerprint,
prior active state, and creation time.

```bash
python scripts/manage_food_evidence_lifecycle.py lifecycle-actions.json
python scripts/manage_food_evidence_lifecycle.py lifecycle-actions.json \
  --apply --operator reviewer@example.org
```

Lifecycle documents are atomic. Identical retries collapse to the original
events; contradictory idempotency-key reuse fails. Reactivation is deliberately
unsupported: corrected evidence must be registered as a new version that
supersedes the latest reviewed predecessor, including an inactive predecessor.

### Authenticated evidence APIs

- `GET /api/v1/food-evidence/history/conversions`
- `POST /api/v1/food-evidence/history/convert-reviewed`
- `GET /api/v1/food-evidence/history/storage-policies`
- `GET /api/v1/food-evidence/history/storage-policies/{key}/active-reviewed`
- `GET /api/v1/food-evidence/history/lifecycle-events`
- `GET /api/v1/food-evidence/history/households/{household_id}/leftovers/{leftover_id}/storage-policy`

Product clients can inspect immutable history and apply already-reviewed exact
conversions. They cannot register, supersede, reject, deactivate, or reactivate
global evidence.

## Preparation scheduling

- Explicit resources with capacity and availability windows.
- Explicit tasks with duration, earliest start, deadline, priority, resource
  demands, dependencies, and metadata.
- Duplicate, unknown, self, and cyclic dependency rejection.
- Deterministic topological ready-set scheduling.
- Cumulative interval-capacity checks.
- Dependency-constrained starts and blocked downstream propagation.
- Missing-resource, capacity, availability, deadline, dependency-window, and
  infeasibility diagnostics.
- Makespan, utilization, peak usage, critical-path lower bound, and search
  diagnostics.
- Fail-closed reviewed-profile compile-and-schedule endpoint.
- Partial scheduling only through explicit `allow_partial=true`.
- Evidence versions and hashes propagated into tasks and diagnostics.
- Exact bounded branch-and-bound comparator with task/node budgets and proven
  optimal makespan when search completes.

Integrated endpoint:

`POST /api/v1/preparation/compile-and-schedule`

## Active frontend

The routed React/TypeScript application includes:

- verified authentication bootstrap and incomplete-profile routing;
- persisted-plan dashboard and descriptive analytics;
- personal meal planner;
- household members, invitations, pantry, leftovers, reservations, shopping,
  batch preparation, and inventory events;
- strictly typed manual preparation editor;
- separate immutable reviewed-evidence preparation pipeline;
- research catalog, capability, conversion history, storage-policy history,
  and evidence-version views;
- shared authenticated HTTP transport;
- lazy protected routes, skip link, keyboard navigation, and reduced-motion
  handling.

The obsolete parallel JSX application and duplicate providers/pages/API client
have been removed.

## Governed research catalog

Catalog `2026-08-01.3` defines:

- **37 task contracts**;
- **30 dataset families**;
- **75 model/algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

Readiness is explicit: implemented, baseline available, adapter available,
research only, blocked by data, blocked by validation, or announced. Runtime
importability never means product enablement, training evidence, accuracy, or
clinical validation.

### Executable offline families

Retrieval and ranking:

- TF-IDF and BM25;
- popularity and Bayesian-smoothed popularity;
- content preference, item-kNN, matrix factorization, and MMR reranking;
- temporal leave-last-out evaluation with hard candidate filtering,
  Recall/HitRate/MRR/NDCG, coverage, novelty, diversity, group metrics, and
  hard-violation audits.

Forecasting and uncertainty:

- moving average, seasonal naive, simple exponential smoothing, damped Holt,
  Croston, and TSB;
- rolling-origin MAE, RMSE, sMAPE, and MASE where defined;
- ridge regression, Kaplan-Meier, Mahalanobis OOD, and split conformal
  intervals.

Planning and operations:

- beam, pantry-aware, Pareto, optional CP-SAT/MILP, robust stress, and robust
  enumeration;
- reviewed preparation compiler and dependency-aware scheduler;
- exact bounded preparation scheduler;
- deterministic FEFO perishable-inventory replay;
- forecast-to-inventory closed-loop evaluation.

Policy research remains offline: Bradley-Terry, LinUCB, and Beta-Bernoulli
Thompson sampling.

See [Governed Research Platform](docs/RESEARCH_PLATFORM.md).

## Benchmark protocols

```bash
python scripts/benchmark_planners.py \
  --generate-seed 17 --slots 4 --options-per-slot 3 --repeats 3 \
  --max-objective-gap 1.0 \
  --output reports/experiments/planner-benchmark.json

python scripts/benchmark_preparation_schedulers.py \
  benchmarks/preparation_scheduler_small.json \
  --require-heuristic-complete --require-exact-optimal \
  --maximum-gap-minutes 0 \
  --output reports/experiments/preparation-scheduler.json

python scripts/benchmark_rankers.py \
  --generate-seed 17 --user-count 18 --item-group-count 3 \
  --items-per-group 8 --interactions-per-user 6 --k 5 \
  --maximum-hard-violations 0 \
  --output reports/experiments/ranking-benchmark.json

python scripts/benchmark_forecasters.py \
  --generate-seed 17 --length 84 --season-length 7 \
  --intermittent-probability 0.25 --minimum-train-size 28 \
  --horizon 7 --step 7 \
  --output reports/experiments/forecast-benchmark.json

python scripts/simulate_inventory.py \
  benchmarks/inventory_small.json \
  --minimum-fill-rate 1.0 --maximum-waste-units 1.0 \
  --maximum-stockout-units 0.0 \
  --output reports/experiments/inventory-simulation.json

python scripts/evaluate_forecast_inventory.py \
  benchmarks/forecast_inventory_small.json \
  --require-model seasonal_naive \
  --require-model tsb_intermittent_demand \
  --output reports/experiments/forecast-inventory.json
```

Forecast error, service level, stockout, waste, ranking accuracy, diversity,
and coverage leaders are reported separately. No benchmark automatically
selects a runtime model or procurement policy.

## Direct-main validation

The workflow runs:

- Python compileall and all backend tests;
- repository cross-contract validation;
- generated OpenAPI path/schema/authentication validation;
- planner, exact preparation, ranking, forecasting, inventory, and
  forecast-inventory gates;
- fresh SQLite and PostgreSQL migrations;
- reviewed food-evidence dry-run/apply/idempotent-reapply manifests;
- evidence lifecycle dry-run/apply/idempotent-reapply manifests;
- PostgreSQL inventory, reservation, request-idempotency,
  preparation-evidence, immutable-evidence, and lifecycle concurrency probes;
- frontend lint, Vitest, and TypeScript/Vite build;
- container build;
- retained machine-readable backend validation reports.

A committed test or synthetic result is not a safety claim. The exact workflow
run for a commit must be inspected before describing that commit as green.

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

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

## Container deployment

```bash
docker build -t nutriflavos .
docker volume create nutriflavos-data

docker run --rm \
  -v nutriflavos-data:/app/data \
  -e DATABASE_URL="sqlite:////app/data/nutriflavor.db" \
  nutriflavos alembic upgrade head

docker run --rm -p 8000:8000 \
  -v nutriflavos-data:/app/data \
  -e SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  -e DATABASE_URL="sqlite:////app/data/nutriflavor.db" \
  -e AUTO_CREATE_SCHEMA=false \
  nutriflavos
```

PostgreSQL is recommended for hosted or concurrent deployments.

## Deliberately incomplete or disabled

- Medical-condition, medication, allergy-safety, food-safety, and health-outcome
  claims are not clinically validated.
- Micronutrients are not hard optimization constraints until normalized
  provenance coverage is sufficient.
- Sustainability remains disabled without geography, production method,
  functional unit, source, and uncertainty coverage.
- Preparation capacity is not yet jointly optimized with meal selection.
- Real recipes need reviewed preparation profiles before automatic compilation.
- Forecasting, ranking benchmarks, and inventory replay are offline tools, not
  autonomous personalization or procurement.
- Vision, multimodal nutrition, constrained generation, graph-neural
  substitution, continual personalization, causal analysis, and privacy attacks
  remain gated research programs.
- Social, leaderboard, achievement, and predictive-purchase surfaces remain
  disabled.

## Status and roadmap

- [Exhaustive Implementation Status](docs/IMPLEMENTATION_STATUS.md)
- [Engineering and Research Roadmap](docs/ROADMAP.md)
- [Governed Research Platform](docs/RESEARCH_PLATFORM.md)
- [Optimizer Benchmarks](docs/OPTIMIZER_BENCHMARKS.md)
- [Household Access and Evidence](docs/HOUSEHOLD_ACCESS_AND_EVIDENCE.md)

Immediate priorities are to inspect and close one exact complete workflow,
finish frontend exact leftover-policy and lifecycle provenance, persist reviewed
household resource calendars and approved schedules, add generated frontend
schema drift validation, and add authenticated Playwright/accessibility
coverage.
