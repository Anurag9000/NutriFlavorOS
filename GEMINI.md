# NutriFlavorOS (FoodScope) - Project Overview & Instructions

NutriFlavorOS is an advanced, AI-driven nutrition and sustainability platform that integrates personalized meal planning, flavor genome analysis, health tracking, and environmental impact assessment. It leverages the CosyLab suite of databases and multiple machine learning architectures to provide a comprehensive food ecosystem.

## 🚀 Project Overview

### Core Technologies
- **Backend:** FastAPI (Python), PyTorch (ML), Pandas, NumPy.
- **Frontend:** React 19, Vite, Tailwind CSS, shadcn/ui, Framer Motion, Recharts.
- **Machine Learning:** 
    - **Taste Predictor:** Transformer-based hedonic score prediction.
    - **Health Outcome Predictor:** LSTM-based trajectory tracking for weight, HbA1c, etc.
    - **Meal Planner:** PPO Reinforcement Learning for optimal meal sequencing.
    - **Grocery Predictor:** LSTM Time-Series for consumption forecasting.
    - **Recipe Generator:** Fine-tuned GPT-2 for novel recipe creation.
    - **Recipe Vision:** CNN (ResNet50) for image-based nutrition estimation.
- **Data Services:** Integrated with RecipeDB, FlavorDB, DietRxDB, and SustainableFoodDB.

### Key Features
- **Smart Meal Planning:** Multi-objective optimization balancing Health (40%), Taste (40%), and Variety (20%).
- **Flavor Genome:** Molecular-level taste profiling and preference mapping.
- **Sustainability Tracking:** Carbon footprint, water, and land usage estimation per meal.
- **Smart Grocery:** Automated shopping lists and stock level predictions.
- **Gamification:** Achievements, leaderboards, and social challenges to drive engagement.

---

## 🛠️ Building and Running

### Prerequisites
- **Python:** 3.10+
- **Node.js:** 18+ (npm or bun)

### 1. Recommended: One-Command Launch
The system includes a master launcher that verifies databases, checks ML models (training them if necessary), and prepares the environment:
```bash
python scripts/launch_system.py
```

### 2. Manual Backend Setup
```bash
cd backend
python -m venv venv
# Linux/macOS
source venv/bin/activate
# Windows
.\venv\Scripts\activate
pip install -r requirements.txt
# Run the server
python -m backend.main
```
The API will be available at `http://localhost:8000`.

### 3. Manual Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The application will be available at `http://localhost:5173`.

### 4. ML Model Training
To train or update the neural networks with early stopping:
```bash
python scripts/train_all_models.py
```

### 5. Verification & Testing
Verify the full API flow (Auth, Meals, Grocery, Analytics):
```bash
python scripts/verify_frontend_api.py
```
Frontend tests: `cd frontend && npm run test`

---

## 📂 Project Structure

- `backend/api/`: FastAPI route definitions (REST endpoints).
- `backend/engines/`: Core business logic (Health, Taste, Variety, Plan Generation).
- `backend/ml/`: Machine learning model definitions, training scripts, and weights.
- `backend/services/`: Data access layers for external/mock databases.
- `backend/data/`: Mock JSON data for offline development.
- `frontend/src/`: React application source code.
- `scripts/`: System-wide orchestration, verification, and data processing scripts.

---

## 🔧 Development Conventions

### Backend
- **Models:** All data structures should be defined as Pydantic models in `backend/models.py`.
- **Config:** External API URLs and keys are managed in `backend/config.py` via `.env`.
- **Mock Mode:** The system defaults to `MOCK_MODE=true` if API keys for CosyLab services are missing, using local JSON files in `backend/data/`.

### Frontend
- **Components:** Uses shadcn/ui components for a consistent design language.
- **Styling:** Vanilla CSS and Tailwind CSS are preferred.
- **State Management:** TanStack Query (React Query) is used for API interactions and caching.

### ML Lifecycle
- Models support **Online Learning** via user feedback (ratings, logs).
- Training logs and weight versioning are handled within the `backend/ml/` directory.
