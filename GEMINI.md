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

## 🗺️ Master Roadmap & Remaining Implementation

Based on an exhaustive gap analysis between the "Dream Specs" and the current codebase, the following phases are required for 100% completion:

### **Phase 1: The "Great Wiring" (Integration)**
*Goal: Connect existing ML brains to the system's body.*
- [ ] **Activate Vision:** Update `vision_routes.py` to use `RecipeVisionAnalyzer`. Connect frontend `ARMealScanner` to this real endpoint.
- [ ] **Activate Taste Transformer:** Replace heuristic cosine similarity in `TasteEngine.py` with the `DeepTastePredictor` model.
- [ ] **Activate RL Planner:** Integrate `RLMealPlanner` (PPO) into the `PlanGenerator` for optimal 7-day sequencing.
- [ ] **Engage Online Learning:** Wire `OnlineLearningManager` into `/feedback` routes so user ratings update `.pth` weights.

### **Phase 2: Building "Dream" Features (Expansion)**
*Goal: Implement high-value features from the Innovation Roadmap.*
- [ ] **AI Meal Buddy:** Create `backend/ml/conversational_agent.py` for personalized nutrition chat.
- [ ] **Wearable Sync:** Implement `backend/integrations/wearables.py` for real-time biometric adjustment.
- [ ] **Budget Optimizer:** Add cost-minimization constraints to `PlanGenerator`.
- [ ] **Family Mode:** Develop `FamilyPlanner` for multi-profile unified meal plans.

### **Phase 3: Production Hardening (Infrastructure)**
*Goal: Prepare for real-world scale and security.*
- [ ] **Database Migration:** Migrate JSON storage to **PostgreSQL** using SQLAlchemy.
- [ ] **Real Authentication:** Replace Mock Auth with **JWT-based security**.
- [ ] **Frontend Realignment:** Replace all `MOCK_DATA` constants with real API hooks.
- [ ] **Cloud Deployment:** Containerize with Docker and set up CI/CD pipelines.

---

## 🛠️ Building and Running

### Prerequisites
- **Python:** 3.10+
- **Node.js:** 18+ (npm or bun)

### 1. Recommended: One-Command Launch
```bash
python scripts/launch_system.py
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

### Backend
- **Models:** Defined as Pydantic models in `backend/models.py`.
- **Mock Mode:** Defaults to `MOCK_MODE=true` if API keys are missing.

### Frontend
- **State Management:** TanStack Query (React Query) for all API interactions.
- **Styling:** Tailwind CSS + shadcn/ui.
