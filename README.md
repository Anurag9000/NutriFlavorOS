# NutriFlavorOS

NutriFlavorOS is an **experimental meal-planning and food-preference research prototype**. It explores personalized meal planning, recipe discovery, quantity-aware grocery support, variety, and sustainability-oriented interfaces.

> **Safety status:** this repository is not clinically validated, is not a medical device, and must not be used to diagnose, treat, or manage allergies, diseases, or medication interactions. Experimental ML components remain disabled until validated data, evaluations, and versioned artifacts exist.

## Current implementation status

### Implemented foundations

- React/Vite user interface and FastAPI backend.
- Password-hashed accounts, signed bearer-token authentication, and self-only authorization for user-owned resources.
- SQLAlchemy persistence with versioned Alembic migrations for fresh and legacy databases.
- Deterministic horizon-level planning across the complete requested period rather than independent greedy meal selection.
- Portion multipliers evaluated jointly with daily calorie, protein, carbohydrate, fat, taste, cost, cuisine, ingredient-variety, and repeat objectives.
- Hard dietary/allergen keyword filtering that fails explicitly when no compliant recipe exists.
- Structured infeasibility diagnostics and disclosed relaxation of non-safety variety preferences when the recipe pool is too small.
- Conservative ingredient parsing that preserves quantity ranges and converts only dimensionally compatible units.
- Serving-scaled shopping aggregation with normalized, mixed-unit, and unquantified status labels.
- Recipe provenance fields, nutrition-basis metadata, plan schema versions, and a dry-run data-quality/backfill command.
- Optional external service adapters for recipe, flavor, diet-reference, and sustainability data.

### Experimental or incomplete

- Medical-condition and medication guidance is **not clinically validated**.
- Micronutrients are not yet hard optimization constraints because much of the repository data lacks verified quantity-normalized nutrient provenance.
- Sustainability values are disabled by default because geography, production method, source provenance, and uncertainty are not fully modeled.
- Vision, NLP recipe generation, health-outcome prediction, RL, and online learning require real training data, validated checkpoints, calibration, and controlled deployment before product use.
- Package, bunch, slice, clove, and other non-convertible culinary units are preserved rather than converted using fabricated density assumptions.
- Pantry, expiry, leftovers, batch-prep, family portions, transactional purchasing, and consumption logging remain incomplete.
- Social and achievement surfaces remain disabled until backed by transactional data.

## Architecture

![NutriFlavorOS Architecture](docs/images/architecture.png)

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Framer Motion, Recharts.
- **Backend:** FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Optimization:** deterministic bounded beam search over the complete planning horizon.
- **Optional research stack:** PyTorch and Transformers modules under `backend/ml/`.
- **Persistence:** SQLite for local development; PostgreSQL is recommended for deployment.

## Local setup

### 1. Configure the backend

```bash
cp .env.example .env
# Replace SECRET_KEY with a securely generated random value.
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows PowerShell
pip install -r backend/requirements.txt
```

### 2. Upgrade the database

```bash
alembic upgrade head
```

The first migration creates a fresh schema or upgrades the earlier prototype schema by adding authenticated profiles, canonical ingredient metadata, plan schema versions, and feedback-event storage.

### 3. Audit and optionally backfill recipe ingredients

Dry-run and review the report first:

```bash
python scripts/backfill_recipe_ingredients.py
```

After reviewing `reports/recipe_data_quality.json`:

```bash
python scripts/backfill_recipe_ingredients.py --apply
```

This command populates canonical ingredient structures. It does **not** automatically rewrite calories or macros; suspicious energy relationships are reported because serving basis and source provenance must be resolved first.

### 4. Start the API

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Start the frontend

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`.

Development defaults to `http://localhost:8000/api/v1`; set `VITE_API_BASE_URL` to override it. Production defaults to same-origin `/api/v1`.

## Container build

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
  nutriflavos
```

The migration and application containers must share the same named volume. PostgreSQL is recommended for hosted or multi-replica deployments. Run migrations as a separate deployment step before starting application replicas.

## Validation

```bash
pytest backend/tests
cd frontend && npm test && npm run lint && npm run build
```

Do not interpret shape checks, synthetic-data training, or a successful import as evidence of model accuracy or clinical safety. New model claims must include dataset provenance, train/validation/test splits, calibration, subgroup analysis, reproducibility settings, and a versioned artifact.

## Development priorities

1. Replace the remaining JSON/pickle stores and purge historical committed runtime/user artifacts.
2. Add verified ingredient densities, package-size catalogs, serving provenance, allergens, and quantity-normalized micronutrients.
3. Add pantry, expiry, leftovers, batch-prep, family planning, and transactional grocery state.
4. Remove obsolete duplicate frontend code, unsafe rich-text rendering, hardcoded dashboards, and accessibility defects.
5. Extend authorization, migration, concurrency, property, contract, and end-to-end tests.
6. Build real ingestion, evaluation, model-registry, drift, and rollback pipelines before enabling ML-assisted decisions.
7. Evaluate a CP-SAT/MILP optimizer against the deterministic beam-search baseline when the canonical dataset is sufficiently complete.
