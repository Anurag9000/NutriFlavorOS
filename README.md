# NutriFlavorOS

NutriFlavorOS is an **experimental meal-planning and food-preference research prototype**. It explores personalized meal planning, recipe discovery, grocery support, variety, and sustainability-oriented interfaces.

> **Safety status:** this repository is not clinically validated, is not a medical device, and must not be used to diagnose, treat, or manage allergies, diseases, or medication interactions. Experimental ML components are disabled by default unless an explicit checkpoint and feature flag are present.

## Current implementation status

### Implemented foundations

- React/Vite user interface and FastAPI backend.
- Password-hashed accounts and signed bearer-token authentication.
- User-owned profile and meal-plan persistence through SQLAlchemy.
- Deterministic seven-day planning from the repository recipe database.
- Hard dietary/allergen keyword filtering that fails explicitly when no compliant recipe exists.
- Macro-aware recipe ranking, preference scoring, variety scoring, grocery occurrence aggregation, and prep timelines.
- Optional external service adapters for recipe, flavor, diet-reference, and sustainability data.

### Experimental or incomplete

- Medical-condition and medication guidance is **not clinically validated**.
- Sustainability values are disabled by default because ingredient quantities, geography, production method, and source provenance are not yet normalized.
- RL, vision, NLP recipe generation, health-outcome prediction, and online learning require real training data, validated checkpoints, calibration, and model governance before product use.
- Grocery quantities are recipe-occurrence counts, not normalized purchase quantities.
- Social, achievement, and analytics surfaces still contain prototype behavior that requires further replacement with transactional data.

## Architecture

![NutriFlavorOS Architecture](docs/images/architecture.png)

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Framer Motion, Recharts.
- **Backend:** FastAPI, Pydantic, SQLAlchemy.
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

### 2. Start the API

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Start the frontend

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
docker run --rm -p 8000:8000 \
  -e SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  nutriflavos
```

The container serves the built frontend and API from port 8000.

## Validation

```bash
pytest backend/tests
cd frontend && npm test && npm run lint && npm run build
```

Do not interpret shape checks, synthetic-data training, or a successful import as evidence of model accuracy or clinical safety. New model claims must include dataset provenance, train/validation/test splits, calibration, subgroup analysis, reproducibility settings, and a versioned artifact.

## Development priorities

1. Replace remaining JSON/pickle runtime stores with transactional persistence and migrations.
2. Normalize ingredients, quantities, units, servings, allergens, nutrients, and provenance.
3. Implement a global constrained weekly optimizer with explicit infeasibility explanations.
4. Remove obsolete duplicate frontend code and generated demo analytics.
5. Add authorization tests to every user-owned endpoint.
6. Build real evaluation pipelines before enabling any ML-assisted decision path.
