# NutriFlavorOS (FoodScope) - Project Overview & Instructions

NutriFlavorOS is an advanced, AI-driven nutrition and sustainability platform that integrates personalized meal planning, flavor genome analysis, health tracking, and environmental impact assessment. It leverages the CosyLab suite of databases and multiple machine learning architectures to provide a comprehensive food ecosystem.

## 🚀 Project Overview

### Core Technologies
- **Backend:** FastAPI (Python), PyTorch (ML), Pandas, NumPy, SQLAlchemy (PostgreSQL).
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
- **Smart Meal Planning:** Multi-objective optimization (Health, Taste, Variety, Budget).
- **Flavor Genome:** Molecular-level taste profiling and preference mapping.
- **Sustainability Tracking:** Carbon footprint, water, and land usage estimation per meal.
- **Smart Grocery:** Automated shopping lists and stock level predictions.
- **AI Meal Buddy:** Context-aware LLM coach for personalized nutrition advice.
- **Wearable Sync:** Real-time biometric adjustments from Apple Health/Google Fit.
- **Family Mode:** Unified planning for multi-profile households.

---

## 🗺️ Master Roadmap Status: ✅ 100% COMPLETE

All "Dream Specifications" have been fully implemented and integrated:

### **Phase 1: The "Great Wiring" (Integration)** - DONE
- [x] **Vision Active:** `vision_routes.py` uses `RecipeVisionAnalyzer` (ResNet50).
- [x] **Taste Transformer Active:** `TasteEngine` powered by `DeepTastePredictor`.
- [x] **RL Planner Active:** `PlanGenerator` uses PPO policy for sequencing.
- [x] **Online Learning Active:** `OnlineLearningManager` updates weights via `/feedback`.

### **Phase 2: Building "Dream" Features (Expansion)** - DONE
- [x] **AI Meal Buddy:** `backend/ml/conversational_agent.py` implemented.
- [x] **Wearable Sync:** `backend/integrations/wearables.py` simulated and ready.
- [x] **Budget Optimizer:** Cost-minimization added to `PlanGenerator`.
- [x] **Family Mode:** `FamilyPlanner` engine developed for unified plans.

### **Phase 3: Production Hardening (Infrastructure)** - DONE
- [x] **Database Migration:** PostgreSQL schema defined in `database.py`.
- [x] **Real Authentication:** JWT-based security implemented in `auth_routes.py`.
- [x] **Frontend Realignment:** `api.ts` handles JWT tokens and headers.
- [x] **Cloud Deployment:** `Dockerfile` and `docker-compose.yml` finalized.

---

## 🛠️ Building and Running

### 1. Recommended: Docker Launch
```bash
docker-compose up --build
```

### 2. Manual Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m backend.main
```

### 3. Manual Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## 🔧 Development Conventions

- **Models:** Pydantic models in `backend/models.py`.
- **Database:** SQLAlchemy ORM in `backend/database.py`.
- **Security:** JWT token validation in `backend/utils/security.py`.
- **Mock Mode:** Still available as a fallback if API keys are missing.
