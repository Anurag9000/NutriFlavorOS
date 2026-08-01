# NutriFlavorOS

NutriFlavorOS is an **experimental household food-planning, inventory,
preparation-operations, immutable-evidence, and governed research platform**.
It combines deterministic meal planning, transactional pantry and leftover
workflows, role-aware household collaboration, reviewed evidence histories,
dependency-aware preparation scheduling, leakage-safe ranking evaluation,
demand forecasting, and perishable-inventory replay.

> **Safety status:** NutriFlavorOS is not clinically validated, is not a medical
> device, and must not autonomously diagnose, treat, manage allergies or
> medication interactions, declare food safe, or make procurement decisions.
> Experimental and high-risk capabilities remain disabled until their declared
> data, validation, calibration, human-review, artifact, approval, rollback,
> and monitoring gates are complete.

## Repository policy

Development is performed directly on `main` in coherent commits. Code, tests,
migrations, fixtures, capability registrations, catalog declarations, and
public documentation must remain synchronized. The project does not use
feature pull requests or automated dependency-update branches.

- Current database migration head: **`20260801_0007`**.
- Effective governed research catalog: **`2026-08-01.3`**.

## Implemented product platform

### Identity and household access

- Argon2 password hashing and signed JWT bearer tokens.
- Startup refusal for missing or weak signing secrets.
- Authenticated self-only user resources.
- Explicit profile-completion state; signup never fabricates physiological
  values or nutrition targets.
- Owner, editor, and viewer household roles with object-access `404` behavior.
- Email-bound, expiring invitation tokens stored as hashes.
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
suitability are never inferred from recipe titles.

Every preparation profile retains:

- recipe ID and immutable profile version;
- schema version and reviewed serving range;
- task-template dependency DAG;
- minimum and maximum duration;
- resource demands;
- active-work and unattended-cooking declarations;
- source name, URL, and version;
- evidence status, reviewer, and UTC-normalized review time;
- SHA-256 content hash;
- supersession link and active state.

Identical same-version registration is idempotent. Contradictory reuse is
rejected. A partial unique index permits only one active reviewed profile per
recipe. Evidence-file imports are all-or-nothing and emit integrity-checked
manifests.

```bash
python scripts/import_preparation_profiles.py reviewed-profiles.json
python scripts/import_preparation_profiles.py reviewed-profiles.json \
  --apply --operator reviewer@example.org
```

### Conversion and storage-policy evidence

Migration `20260801_0007` introduces immutable histories for:

- ingredient-specific unit conversions;
- reviewed storage policies;
- exact leftover-to-storage-policy-version links.

Each immutable conversion version retains the ingredient and unit direction,
multiplier interval, record version, source provenance, evidence status,
reviewer, UTC review time, content hash, supersession link, and active state.
Automatic conversion through the immutable API requires one exact active
reviewed version and returns its ID, version, and hash.

Each immutable storage-policy version retains its policy key/version, food
category, storage state, duration interval, temperature assumption, source,
reviewer, review time, safety scope, content hash, supersession link, and active
state. New leftovers select one active reviewed policy version, validate the
storage state and expiry bound, persist the exact version link, and write the
version/hash into the inventory event in the same transaction.

Frozen duration guidance marked as `quality_guidance` is never converted into
a safety-expiry timestamp.

Authenticated read-only history API:

- `GET /api/v1/food-evidence/history/conversions`
- `POST /api/v1/food-evidence/history/convert-reviewed`
- `GET /api/v1/food-evidence/history/storage-policies`
- `GET /api/v1/food-evidence/history/storage-policies/{key}/active-reviewed`

Ordinary API users cannot register or supersede global evidence.

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
- Exact bounded branch-and-bound comparator with explicit task/node budgets
  and proven optimal makespan when search completes.

Integrated endpoint:

`POST /api/v1/preparation/compile-and-schedule`

## Active frontend

The routed React/TypeScript application includes:

- verified authentication bootstrap and incomplete-profile routing;
- persisted-plan dashboard and descriptive analytics;
- personal meal planner;
- household members, invitations, pantry, leftovers, reservations, shopping,
  batch prep, and event ledger;
- strictly typed manual preparation editor;
- separate immutable reviewed-evidence preparation pipeline;
- research catalog, runtime capability, conversion evidence, and
  storage-policy views;
- shared authenticated HTTP transport;
- lazy protected routes, skip link, keyboard navigation, and reduced-motion
  handling.

The obsolete parallel JSX application and duplicate providers/pages/API client
have been removed.

## Governed research catalog

The effective catalog `2026-08-01.3` defines:

- **37 task contracts**;
- **30 dataset families**;
- **75 model/algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

Readiness is explicit: implemented, baseline available, adapter available,
research only, blocked by data, blocked by validation, or announced. Runtime
importability never means product enablement, training evidence, accuracy, or
clinical validation.

### Executable offline baseline families

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
- rolling-origin evaluation with MAE, RMSE, sMAPE, and MASE where defined;
- ridge regression, Kaplan-Meier, Mahalanobis OOD, and split conformal
  intervals.

Planning and operations:

- beam, pantry-aware, Pareto, optional CP-SAT/MILP, robust stress, and robust
  enumeration;
- reviewed preparation compiler and dependency-aware scheduler;
- exact bounded preparation scheduler;
- deterministic FEFO perishable-inventory replay;
- forecast-to-inventory closed-loop evaluation.

Policy research:

- Bradley-Terry, LinUCB, and Beta-Bernoulli Thompson sampling, all offline only.

Governance:

- deterministic group-aware and temporal splits;
- cards, manifests, drift reports, callable validation, repository-contract
  validation, integrity-checked artifact registry, promotion stages, and
  rollback metadata.

See [Governed Research Platform](docs/RESEARCH_PLATFORM.md).

## Benchmark protocols

```bash
# Planner
python scripts/benchmark_planners.py \
  --generate-seed 17 --slots 4 --options-per-slot 3 --repeats 3 \
  --max-objective-gap 1.0 \
  --output reports/experiments/planner-benchmark.json

# Preparation heuristic versus exact bounded search
python scripts/benchmark_preparation_schedulers.py \
  benchmarks/preparation_scheduler_small.json \
  --require-heuristic-complete --require-exact-optimal \
  --maximum-gap-minutes 0 \
  --output reports/experiments/preparation-scheduler.json

# Temporal ranking
python scripts/benchmark_rankers.py \
  --generate-seed 17 --user-count 18 --item-group-count 3 \
  --items-per-group 8 --interactions-per-user 6 --k 5 \
  --maximum-hard-violations 0 \
  --output reports/experiments/ranking-benchmark.json

# Forecasting
python scripts/benchmark_forecasters.py \
  --generate-seed 17 --length 84 --season-length 7 \
  --intermittent-probability 0.25 --minimum-train-size 28 \
  --horizon 7 --step 7 \
  --output reports/experiments/forecast-benchmark.json

# Perishable inventory replay
python scripts/simulate_inventory.py \
  benchmarks/inventory_small.json \
  --minimum-fill-rate 1.0 --maximum-waste-units 1.0 \
  --maximum-stockout-units 0.0 \
  --output reports/experiments/inventory-simulation.json

# Forecast-to-inventory closed loop
python scripts/evaluate_forecast_inventory.py \
  benchmarks/forecast_inventory_small.json \
  --require-model seasonal_naive \
  --require-model tsb_intermittent_demand \
  --output reports/experiments/forecast-inventory.json
```

Forecast error, service level, stockout, waste, ranking accuracy, diversity, and
coverage leaders are reported separately. No benchmark automatically selects a
runtime model or procurement policy.

## Validation

The direct-`main` workflow runs:

- Python compileall and all backend tests;
- repository cross-contract validation;
- planner, exact preparation, ranking, forecasting, inventory, and
  forecast-inventory gates;
- fresh SQLite and PostgreSQL migrations;
- PostgreSQL inventory, reservation, idempotency, preparation-evidence, and
  immutable food-evidence concurrency probes;
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
- Forecasting, ranking benchmarks, and inventory replay are offline evaluation
  tools, not autonomous personalization or procurement.
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

Immediate priorities are to inspect and close the latest complete workflow,
finish immutable evidence import/deactivation operations, expose exact leftover
policy provenance in the frontend, persist reviewed household resource
calendars and approved schedules, add OpenAPI/client drift checks, and add
authenticated Playwright/accessibility coverage.
