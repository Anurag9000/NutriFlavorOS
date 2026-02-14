# 🚀 NutriFlavorOS - Run Instructions & Developer Guide

**Objective:** Get the fully integrated Nutrition Operating System (Full Stack + ML) up and running.

---

## 🛠️ Prerequisites

Ensure you have the following installed:
- **Python 3.10+**
- **Node.js 18+**
- **Git**

---

## 📥 1. Installation

### Backend Setup
```bash
# Clone the repository
git clone https://github.com/Anurag9000/NutriFlavorOS.git
cd NutriFlavorOS

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies (Core + ML)
pip install -r requirements.txt
```

### Frontend Setup
```bash
cd frontend
npm install
cd ..
```

---

## 🧠 2. ML Model Training & Data

Before running the system, you must have trained model weights. 

### Data Harvesting (Optional)
To pull the latest real recipes from RecipeDB:
```bash
python scripts/harvest_data.py
```

### Full Model Training
Train the 4 primary neural networks (Taste, RL, Grocery, Health) to convergence:
```bash
python scripts/train_all_models.py
```
- **Max Epochs**: 10,000
- **Early Stopping**: Patience 10
- **Device**: Automatic (CUDA if available)

---

## 🚀 3. Master Launch Script (Recommended)

The easiest way to start the entire system is using the orchestrator:
```bash
python scripts/launch_system.py
```
This script will:
1.  **Verify DBs**: Check for `recipes.json`, `flavor_db.json`, etc.
2.  **Verify ML**: Ensure `.pth` weights exist in `backend/ml/weights`.
3.  **Start Backend**: Launch the FastAPI server.
4.  **Launch Frontend**: Provide instructions to open the React UI.

---

## 🏃‍♂️ 4. Manual Execution

### Start Backend
```bash
python -m backend.main
```

### Start Frontend
```bash
cd frontend
npm run dev
```

---

## 🧪 5. Verification

Verify that the Frontend-Backend integration is healthy:
```bash
python scripts/verify_frontend_api.py
```

---

## 📺 6. Presentation Flow

1.  **Auth**: Log in with any credentials (Mock Auth enabled).
2.  **Dashboard**: Show real-time progress rings.
3.  **Meal Planner**: Generate a 7-day plan.
4.  **Analytics**: View the LSTM-based health forecasts.
5.  **Grocery**: Show the predicted shopping lists.

---

*NutriFlavorOS is ready for pitching!* 🚀
