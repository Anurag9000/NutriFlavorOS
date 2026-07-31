# NutriFlavorOS

NutriFlavorOS is an **experimental meal-planning, household-food-state, and governed food-research platform**. It combines deterministic quantity-aware planning, transactional pantry and leftover workflows, household collaboration, explicit food-evidence records, and reproducible offline research infrastructure.

> **Safety status:** this repository is not clinically validated, is not a medical device, and must not be used to diagnose, treat, or autonomously manage allergies, diseases, medication interactions, food safety, or health outcomes. Experimental ML components remain disabled until validated data, evaluations, versioned artifacts, and the declared promotion gates exist.

## Implemented platform

### Identity, persistence, and safety

- Argon2 password hashing and signed bearer tokens with issuer, audience, expiry, not-before, issued-at, and token IDs.
- Authenticated self-only access for user-owned resources and role-aware household access.
- Explicit profile-completion state; signup and legacy reads never invent age, weight, height, activity, sex/gender, or goal values.
- SQLAlchemy persistence and versioned Alembic migrations for SQLite and PostgreSQL.
- Append-only feedback and inventory events.
- Explicit `404`, `409`, `422`, and `501` states instead of silent demo values or unsafe model fallbacks.
- Request-time online model mutation is disabled; feedback is retained only for offline review.

### Quantity-aware personal planning

- Deterministic horizon-level beam search instead of independent greedy slot selection.
- Joint portion, calorie, protein, carbohydrate, fat, taste, cost, cuisine, ingredient-variety, and repeat objectives.
- Hard allergy and dietary filtering before optimization.
- Structured infeasibility diagnostics and disclosed relaxation of non-safety variety preferences.
- Conservative ingredient parsing that preserves ranges, raw text, source units, canonical units, and parse status.
- Automatic conversion only across dimensionally compatible units.
- Serving-scaled shopping aggregation with normalized, mixed-unit, partial, and unquantified states.
- Persisted plan provenance, optimizer diagnostics, portion multipliers, warnings, recipe yield, and nutrition basis.

### Household collaboration and planning

- User-owned households with `owner`, `editor`, and `viewer` roles.
- Email-bound, expiring, single-use invitations stored as hashes rather than plaintext tokens.
- Active-member serving multipliers, restrictions, allergies, dislikes, explicit target overrides, and linked complete profiles.
- Household planning that unions hard restrictions and separately reports pantry coverage.
- Stock reservations allocated from earliest-expiring compatible lots.
- Explicit reservation release and commit; pantry stock is not consumed merely because a plan was generated.
- Optimistic versions and idempotency keys for retry-safe writes.

See [Household Access and Evidence](docs/HOUSEHOLD_ACCESS_AND_EVIDENCE.md).

### Pantry, leftovers, shopping, and batch preparation

- Transactional pantry lots with quantity intervals, canonical units, expiry/open timestamps, source metadata, and optimistic versions.
- Idempotent purchase, consume, adjust, discard, reservation-commit, leftover-create, and leftover-consume events.
- Cross-dimensional subtraction rejection and prevention of negative stock.
- Expired-stock exclusion and near-expiry use-first annotations.
- Conservative shopping reconciliation that propagates pantry uncertainty.
- Leftovers tied to real recipes and optional owner-visible source plans.
- Reviewed storage-policy provenance retained on leftover batches.
- Deterministic batch-preparation grouping for repeated planned recipes.

See [Household Inventory, Leftovers and Batch Preparation](docs/HOUSEHOLD_INVENTORY.md).

### Food evidence

- Ingredient-specific conversion records with multiplier intervals, source URL/version, evidence state, review time, and notes.
- FoodData Central portion gram weights can create conversions only for the exact imported food and measure.
- No generic density, package-size, or household-measure guessing when evidence is absent.
- Reviewed storage policies retain food category, storage state, duration interval, temperature assumptions, source, review date, scope, and limitations.
- Unknown foods remain without a reviewed policy rather than receiving fabricated shelf lives.

### Research and experimentation

The versioned catalog defines:

- 28 task contracts;
- 24 dataset families;
- 57 model and algorithm families;
- 21 experiment contracts;
- 26 product and research feature contracts.

Executable offline baselines include:

- TF-IDF and BM25 retrieval;
- popularity, content, and matrix-factorization recommendation;
- moving-average, Croston, ridge-regression, and survival baselines;
- LinUCB and Thompson-sampling policies;
- Bradley–Terry pairwise preferences;
- Mahalanobis OOD scoring and split conformal intervals;
- rule-based ingredient and instruction dependency parsing;
- deterministic beam, Pareto, optional CP-SAT, and optional MILP planners.

Governed infrastructure includes:

- retrieval, forecasting, regression, calibration, segmentation, uncertainty, and offline-policy metrics;
- deterministic group-aware and temporal dataset splits with leakage checks;
- versioned dataset and model cards;
- SHA-256 artifact integrity checks;
- registered, candidate, champion, archived, and rejected stages;
- risk-dependent promotion gates for OOD, calibration, subgroup evaluation, human review, and clinical validation;
- numerical and categorical drift reports that never retrain or promote automatically;
- reproducible offline manifests, fingerprints, seeds, metrics, warnings, artifacts, and environment snapshots;
- an offline runner with a strict baseline whitelist and user-data path guard;
- an explicit USDA FoodData Central adapter with no zero-filled or mock fallback.

See [Research Platform](docs/RESEARCH_PLATFORM.md) and [Optimizer Benchmarks](docs/OPTIMIZER_BENCHMARKS.md).

### Active frontend

The routed React/TypeScript application provides:

- verified authentication bootstrap and explicit incomplete-profile routing;
- persisted-plan dashboard and descriptive analytics;
- deterministic meal planning with optimizer and source provenance;
- household, members, invitations, pantry, leftovers, reservations, shopping reconciliation, and audit events;
- research catalog, runtime capability, conversion evidence, and storage-policy views;
- keyboard-accessible navigation, a skip link, lazy routes, reduced-motion handling, and one React Query cache.

The obsolete parallel JSX application, fake grocery/gamification providers, duplicate pages, and duplicate API service have been removed.

## Experimental or incomplete

- Medical-condition, medication, allergy, storage-duration, and health guidance are not clinically validated.
- Micronutrients are not hard optimization constraints until quantity-normalized nutrient provenance is sufficiently complete.
- Sustainability estimation remains disabled by default because geography, production method, source provenance, functional units, and uncertainty remain incomplete.
- Appliance-capacity and preparation-resource scheduling are not yet represented.
- Vision, multimodal nutrition estimation, constrained recipe generation, graph substitution, continual personalization, causal analyses, and privacy attacks remain research contracts until licensed data, training, evaluation, calibration, and promotion evidence exist.
- Social, leaderboard, achievement, and predictive-purchase surfaces remain disabled until backed by real transactional state and validated methods.
- A catalog entry or source file is not evidence that a model has been trained, benchmarked, promoted, or enabled.

## Architecture

![NutriFlavorOS Architecture](docs/images/architecture.png)

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Framer Motion, Recharts, TanStack Query.
- **Backend:** FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Optimization:** deterministic bounded beam search, household pantry-aware search, Pareto enumeration, optional CP-SAT, and optional MILP.
- **Household domain:** roles, invitations, transactional lots, leftovers, audit events, reservations, and versioned writes.
- **Research:** catalog, baselines, metrics, splits, cards, registry, drift, manifests, and whitelisted offline execution.
- **Persistence:** SQLite for local development and PostgreSQL for hosted or multi-replica deployment.

## Local setup

```bash
cp .env.example .env
# Replace SECRET_KEY with an unpredictable value of at least 32 characters.
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows PowerShell
pip install -r backend/requirements.txt
alembic upgrade head
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

In a separate terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`.

## Validation

The main-only workflow validates direct commits with:

```bash
python -m compileall -q backend scripts
pytest -q backend/tests
DATABASE_URL=sqlite:///ci-fresh.db alembic upgrade head

cd frontend
npm ci
npm run lint
npm test
npm run build   # includes TypeScript project compilation

# A separate CI job performs a fresh PostgreSQL migration.
docker build -t nutriflavos .
```

A successful import, synthetic run, shape check, or catalog entry is not evidence of accuracy or safety. New model claims require dataset provenance, leakage-safe splits, reproducibility, calibrated uncertainty, appropriate subgroup and OOD evaluation, a versioned integrity-checked artifact, explicit promotion approval, and a rollback path.

## Data-quality and ingredient backfill

Dry-run first:

```bash
python scripts/backfill_recipe_ingredients.py
```

After reviewing `reports/recipe_data_quality.json`:

```bash
python scripts/backfill_recipe_ingredients.py --apply
```

This populates canonical ingredient structures. It does not automatically rewrite calories or macros because serving basis and source provenance must be reviewed.

## Offline experiments

```bash
python scripts/run_offline_experiment.py --config experiment.json
python scripts/benchmark_planners.py --input benchmark.json --output reports/experiments/planner-benchmark.json
```

Manage versioned artifacts:

```bash
python scripts/manage_artifact_registry.py register-dataset usda_fdc_foundation 2026-04
python scripts/manage_artifact_registry.py register-model tfidf_retriever 1.0 reports/model.bin
python scripts/manage_artifact_registry.py verify model tfidf_retriever 1.0
```

The API validates experiment configurations and exposes catalog, cards, capabilities, and drift diagnostics. It deliberately does not accept arbitrary experiment code over HTTP.

## USDA FoodData Central

Set both:

```bash
ENABLE_FOODDATA_CENTRAL=true
FOODDATA_CENTRAL_API_KEY=your-key
```

The adapter preserves FDC identifiers, portion measures, missing nutrient values, source/license metadata, retrieval time, and external-unverified state.

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

The migration and application containers must share the same volume. PostgreSQL is recommended for hosted or multi-replica deployments.

## Next engineering priorities

1. Complete property-based and concurrent-write testing against PostgreSQL, including stale versions, duplicate idempotency keys, and competing reservations.
2. Add browser-level accessibility and authenticated household end-to-end tests.
3. Expand ingredient-specific conversion coverage only from reviewed portion/density/package evidence.
4. Add appliance, preparation-time, capacity, and task-scheduling constraints to household planning.
5. Run controlled planner benchmarks across beam, Pareto, CP-SAT, and MILP methods on versioned canonical fixtures.
6. Implement additional catalogued datasets and models only through the card, split, evaluation, integrity, and promotion-gate pipeline.
