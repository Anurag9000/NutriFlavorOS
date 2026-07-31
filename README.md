# NutriFlavorOS

NutriFlavorOS is an **experimental meal-planning, household-food-state, preparation-operations, and governed food-research platform**. It combines deterministic quantity-aware planning, transactional pantry and leftover workflows, household collaboration, reviewed evidence records, dependency-aware preparation scheduling, and reproducible offline research infrastructure.

> **Safety status:** this repository is not clinically validated, is not a medical device, and must not be used to diagnose, treat, or autonomously manage allergies, diseases, medication interactions, food safety, or health outcomes. Experimental ML components remain disabled until licensed/consented data, evaluations, calibrated uncertainty, versioned artifacts, approval gates, and rollback controls exist.

## Repository policy

Development is performed directly on `main` in coherent commits. Code, tests, migrations, benchmark protocols, capability registrations, catalog records, and documentation must remain synchronized. The project does not use feature pull requests or automated dependency-update PR branches.

## Implemented platform

### Identity, persistence, and safety

- Argon2 password hashing.
- Signed JWT bearer tokens with issuer, audience, expiry, not-before, issued-at, and token IDs.
- Authenticated self-only resources and role-aware household access.
- Explicit profile-completion state; signup and legacy reads never invent physiological values.
- SQLAlchemy persistence and versioned Alembic migrations for SQLite and PostgreSQL.
- Current migration head: `20260801_0006`.
- Hosted startup verifies the exact migration revision.
- Append-only feedback and inventory events.
- Structured `404`, `409`, `422`, and `501` states instead of demo values or unsafe model fallbacks.
- Request-time online model mutation and automatic model promotion are disabled.

### Quantity-aware personal planning

- Deterministic horizon-level beam search.
- Joint portion, calorie, protein, carbohydrate, fat, taste, cost, cuisine, ingredient-variety, and repeat objectives.
- Hard allergy and dietary filtering before optimization.
- Structured infeasibility diagnostics and disclosed non-safety relaxations.
- Conservative ingredient parsing that retains quantity ranges, raw text, source units, canonical units, and parse status.
- Automatic conversion only across compatible dimensions.
- Serving-scaled shopping aggregation with normalized, mixed-unit, partial, and unquantified states.
- Persisted plan provenance, optimizer diagnostics, portion multipliers, warnings, recipe yield, and nutrition basis.

### Household collaboration and planning

- User-owned households with `owner`, `editor`, and `viewer` roles.
- Email-bound, expiring invitation tokens stored as hashes.
- One-time plaintext token handoff and explicit dismissal.
- Invitation replacement, revocation, exact-email acceptance, and retry-safe acceptance.
- Active-member serving multipliers, restrictions, allergies, dislikes, explicit targets, and linked profiles.
- Household planning that unions hard restrictions and separately reports pantry coverage.
- Stock reservations allocated from compatible earliest-expiring lots.
- Explicit reservation release and commit; plan generation alone does not consume stock.
- Optimistic versions and complete request fingerprints for retry-safe writes.

See [Household Access and Evidence](docs/HOUSEHOLD_ACCESS_AND_EVIDENCE.md).

### Pantry, leftovers, shopping, and batch preparation

- Transactional pantry lots with quantity intervals, canonical units, expiry/open timestamps, source metadata, and optimistic versions.
- Append-only purchase, consume, adjust, discard, reservation, and leftover events.
- Full-request idempotency fingerprints written atomically with the event.
- Cross-dimensional subtraction rejection and negative-stock prevention.
- Expired-stock exclusion and near-expiry use-first behavior.
- Conservative shopping reconciliation that propagates pantry uncertainty.
- Leftovers linked to real recipes and optional source plans.
- Reviewed storage-policy provenance retained on leftover batches.
- Storage-state/policy matching and reviewed-expiry bound checks.
- Deterministic batch-preparation grouping.
- PostgreSQL concurrency probes for inventory, reservations, and contradictory retries.

See [Household Inventory, Leftovers and Batch Preparation](docs/HOUSEHOLD_INVENTORY.md).

### Food and recipe evidence

- Ingredient-specific conversion records with multiplier intervals, source URL/version, evidence status, review time, and notes.
- FoodData Central portion gram weights create conversions only for the exact imported food and measure.
- No generic density, package-size, or household-measure guessing when evidence is absent.
- Reviewed storage policies retain category, storage state, duration interval, temperature assumption, source, review date, scope, and limitations.
- Unknown foods remain without fabricated shelf lives.
- Recipe API preserves ingredient structures, servings, nutrition basis, and source provenance.

### Reviewed preparation evidence

Preparation timing and appliance data are not inferred from recipe titles.

Versioned preparation profiles retain:

- recipe and immutable profile version;
- schema version;
- reviewed serving range;
- task-template dependency DAG;
- duration interval;
- resource demands;
- active-work and unattended-cooking declarations;
- source name/URL/version;
- evidence status, review time, and reviewer;
- SHA-256 content hash;
- supersession link and active state.

Behavior:

- identical same-version registration is idempotent;
- contradictory same-version content is rejected;
- one active reviewed profile per recipe is database-enforced;
- a new active reviewed version supersedes the prior active review;
- ordinary API users receive read/compile access but cannot mutate global evidence;
- offline import validates before optional commit.

```bash
python scripts/import_preparation_profiles.py reviewed-profiles.json
python scripts/import_preparation_profiles.py reviewed-profiles.json --apply
```

### Dependency-aware preparation scheduling

- Explicit resources with capacity and availability windows.
- Explicit tasks with duration, earliest start, deadline, priority, demands, dependencies, and metadata.
- Validation for duplicate/unknown/self/cyclic dependencies.
- Deterministic topological ready-set scheduling.
- Cumulative interval-capacity checks.
- Dependency-constrained earliest starts.
- Explicit blocked-task propagation.
- Missing resource, capacity, availability, deadline, dependency-window, and infeasibility diagnostics.
- Utilization, peak usage, makespan, critical-path lower bound, and search diagnostics.

Integrated endpoint:

`POST /api/v1/preparation/compile-and-schedule`

Default behavior is fail-closed: one unresolved occurrence prevents scheduling. Partial scheduling requires explicit `allow_partial=true` and retains unresolved occurrences and evidence-version diagnostics.

### Active frontend

The routed React/TypeScript application provides:

- verified authentication bootstrap and incomplete-profile routing;
- persisted-plan dashboard and descriptive analytics;
- deterministic meal planning with provenance;
- household members, invitations, pantry, leftovers, reservations, shopping, batch preparation, and audit events;
- reviewed preparation profiles, occurrence compilation, dependency editing, and resource schedules;
- research catalog, runtime capability, conversion evidence, and storage-policy views;
- shared authenticated HTTP transport;
- keyboard-accessible navigation, skip link, lazy routes, reduced-motion handling, and one React Query cache.

The obsolete parallel JSX application, fake providers, duplicate pages, and duplicate API service have been removed.

## Governed research platform

Catalog version: `2026-08-01.1`

- **37 task contracts**
- **30 dataset families**
- **72 model/algorithm families**
- **28 experiment contracts**
- **37 feature contracts**

### Executable offline baselines

Retrieval/ranking:

- TF-IDF and BM25;
- popularity and Bayesian-smoothed popularity;
- content preference;
- item-kNN;
- matrix factorization;
- MMR diversity reranking.

Forecasting/uncertainty:

- moving average;
- seasonal naive;
- simple exponential smoothing;
- damped Holt trend;
- Croston and TSB intermittent demand;
- rolling-origin evaluation;
- ridge regression;
- Kaplan–Meier expiry;
- Mahalanobis OOD;
- split conformal intervals.

Preferences/policies:

- Bradley–Terry;
- LinUCB;
- Beta-Bernoulli Thompson sampling.

Rules/planning/operations:

- ingredient parser and instruction DAG rules;
- substitution graph;
- beam and household pantry-aware planners;
- Pareto enumeration;
- optional CP-SAT and MILP;
- scenario stress testing and robust worst-case enumeration;
- reviewed preparation compiler and dependency-aware scheduler;
- deterministic FEFO perishable-inventory replay simulator.

Runtime availability is mechanically checked through imports and callable lookup. It never means production enablement, training evidence, accuracy, or clinical validity.

See [Research Platform](docs/RESEARCH_PLATFORM.md).

## Benchmark protocols

### Planner

```bash
python scripts/benchmark_planners.py \
  --generate-seed 17 \
  --slots 4 \
  --options-per-slot 3 \
  --repeats 3 \
  --max-objective-gap 1.0 \
  --output reports/experiments/planner-benchmark.json
```

### Forecasting

```bash
python scripts/benchmark_forecasters.py \
  --generate-seed 17 \
  --length 84 \
  --season-length 7 \
  --intermittent-probability 0.25 \
  --minimum-train-size 28 \
  --horizon 7 \
  --step 7 \
  --output reports/experiments/forecast-benchmark.json
```

### Perishable inventory replay

```bash
python scripts/simulate_inventory.py \
  benchmarks/inventory_small.json \
  --minimum-fill-rate 1.0 \
  --maximum-waste-units 1.0 \
  --maximum-stockout-units 0.0 \
  --output reports/experiments/inventory-simulation.json
```

The simulator is offline-only and never mutates household inventory.

## Experimental or incomplete

- Medical-condition, medication, allergy, storage-duration, and health guidance are not clinically validated.
- Micronutrients are not hard constraints until normalized provenance coverage is sufficient.
- Sustainability estimation remains disabled without geography, production, functional-unit, source, and uncertainty coverage.
- Preparation capacity is evaluated after meal selection; joint meal/schedule optimization remains research work.
- Real recipes require reviewed preparation profiles before automatic compilation.
- Forecasting and inventory simulation are offline evaluation tools, not procurement automation.
- Vision, multimodal nutrition estimation, constrained generation, graph-neural substitution, continual personalization, causal analysis, and privacy attacks remain gated research contracts.
- Social, leaderboard, achievement, and predictive-purchase surfaces remain disabled.
- A catalog entry or source file is not evidence that a model was trained, benchmarked on representative data, promoted, or enabled.

## Architecture

![NutriFlavorOS Architecture](docs/images/architecture.png)

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Framer Motion, Recharts, TanStack Query.
- **Backend:** FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Planning:** deterministic beam search, pantry-aware search, Pareto, optional CP-SAT/MILP, robust scenario evaluation.
- **Operations:** role-aware households, transactional inventory, reservations, reviewed evidence, preparation DAG scheduling.
- **Research:** catalog, baselines, metrics, splits, cards, registry, drift, manifests, benchmarks, and whitelisted offline execution.
- **Persistence:** SQLite for local development and PostgreSQL for hosted/multi-replica deployment.

## Local setup

```bash
cp .env.example .env
# Replace SECRET_KEY with at least 32 unpredictable characters.
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

Open `http://localhost:5173`.

## Validation

The direct-`main` workflow runs:

```bash
python -m compileall -q backend scripts
pytest -q backend/tests
python scripts/benchmark_planners.py ...
python scripts/benchmark_forecasters.py ...
python scripts/simulate_inventory.py ...
DATABASE_URL=sqlite:///ci-fresh.db alembic upgrade head

cd frontend
npm ci
npm run lint
npm test
npm run build

# Separate jobs run PostgreSQL migrations/concurrency probes and Docker build.
```

A successful synthetic run is not evidence of safety. New claims require provenance, leakage-safe splits, reproducibility, calibrated uncertainty, subgroup/OOD evaluation where applicable, integrity-checked artifacts, explicit approval, and rollback.

## Offline experiments and artifacts

```bash
python scripts/run_offline_experiment.py --config experiment.json
python scripts/manage_artifact_registry.py register-dataset usda_fdc_foundation 2026-04
python scripts/manage_artifact_registry.py register-model tfidf_retriever 1.0 reports/model.bin
python scripts/manage_artifact_registry.py verify model tfidf_retriever 1.0
```

The API validates experiment configurations and previews manifests. It does not accept arbitrary experiment code.

## USDA FoodData Central

Set:

```bash
ENABLE_FOODDATA_CENTRAL=true
FOODDATA_CENTRAL_API_KEY=your-key
```

The adapter preserves identifiers, measures, missing values, source/license metadata, retrieval time, and external-unverified state. No zero-filled or mock nutrient fallback is permitted.

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

Migration and application containers must share the same database. PostgreSQL is recommended for hosted or concurrent deployment.

## Status and roadmap

- [Exhaustive Implementation Status](docs/IMPLEMENTATION_STATUS.md)
- [Engineering and Research Roadmap](docs/ROADMAP.md)
- [Research Platform](docs/RESEARCH_PLATFORM.md)
- [Optimizer Benchmarks](docs/OPTIMIZER_BENCHMARKS.md)

The immediate priorities are to close the latest full validation run, complete strict frontend contract checks, make preparation imports atomic/concurrency-tested, add the integrated pipeline control to the UI, register the inventory simulator after benchmark review, and implement the forecast-to-inventory closed-loop evaluation.
