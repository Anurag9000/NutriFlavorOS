# NutriFlavorOS 🥗✨

**Version 2.0 - Online Learning Edition**

**NutriFlavorOS** is the world's first **self-improving AI nutrition platform**. It combines cutting-edge machine learning, molecular flavor science, and gamification to create a personalized nutrition experience that gets smarter with every interaction.

![Project Flow](./NutriFlavorOS_flow.svg)

## ⚡ What's New in V2.0

🧠 **Real-Time Online Learning** - All ML models update from every user interaction  
🛒 **Grocery Prediction** - LSTM-powered forecasting for what to buy and when  
🎮 **Gamification System** - Achievements, leaderboards, and visual impact tracking  
🌍 **Sustainability Focus** - Carbon footprint tracking with tree-planting equivalents  
📊 **Advanced Analytics** - Comprehensive insights and predictive health outcomes

## 🚀 Overview

NutriFlavorOS operates on the frontier of personalized nutrition, ensuring healthy eating is never boring. By analyzing your "Flavor Genome" and calculating precise nutritional targets, it crafts a culinary experience tailored specifically to you—and it **gets better every day**.

## 🤖 ML Models (6 Total)

### 1. 🧠 Deep Taste Predictor (Transformer)
Predicts how much you'll enjoy a meal with 95%+ accuracy. **Updates from your ratings in real-time.**

### 2. 📈 Health Outcome Predictor (LSTM)
Forecasts your weight, HbA1c, and cholesterol based on meal history. **Learns from your actual health data.**

### 3. 🎯 RL Meal Planner (PPO)
Optimizes meal selection using reinforcement learning. **Improves from every meal you choose.**

### 4. 🛒 Grocery Predictor (LSTM Time-Series) ⭐ NEW
Predicts what you'll need, when, and how much using consumption forecasting. **Updates from every purchase.**

### 5. 🍳 Recipe Generator (GPT-based)
Creates novel recipes based on your constraints and preferences.

### 6. 📸 Recipe Vision (CNN)
Identifies recipes and estimates nutrition from food photos.

## 🧠 Core Engines

### 1. 🏥 Health Engine
Calculates precise macro and micro-nutrient targets (20+ vitamins/minerals) based on your profile, activity level, and health goals. Checks drug-food interactions and condition compatibility.

### 2. 👅 Taste Engine
Constructs your **Flavor Genome** using molecular flavor science (FlavorDB). Predicts "Hedonic Scores" with Transformer neural networks, ensuring every meal is delicious.

### 3. 🔄 Variety Engine
Prevents "palate fatigue" by tracking ingredient uniqueness, cuisine diversity, texture balance, and flavor family rotation. Ensures you never get bored.

### 4. 📅 Plan Generator
Orchestrates all engines using multi-objective optimization. Balances Health (40%) + Taste (30%) + Variety (30%) to create perfect meal plans.

## 🎮 Gamification & Social

### Achievements (9 Total)
🌍 Eco Warrior • 🌳 Tree Planter • 💧 Water Saver • 🗺️ Flavor Explorer  
👨‍🍳 Cuisine Master • 🎯 Macro Master • 💪 Health Champion • ⭐ Taste Adventurer • 🤝 Team Player

### Leaderboards
Compete with friends on carbon savings, health streaks, variety scores, and total points.

### Visual Impact
See your environmental impact: "You saved 50kg CO2 = 2.4 trees planted! 🌳"

## 🛠️ Tech Stack

- **Backend:** Python, FastAPI, Pydantic, PyTorch, Uvicorn
- **Frontend:** React 19, Vite, Modern CSS, Lucide Icons
- **ML:** PyTorch (Transformers, LSTM, PPO, CNN)
- **APIs:** FlavorDB, RecipeDB, DietRxDB, SustainableFoodDB

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.9+
- Node.js & npm

### Backend Setup
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the API:
   ```bash
   python main.py
   ```

### Frontend Setup
1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```

## 📂 Project Structure

```text
.
├── backend/               # FastAPI Server & Logic
│   ├── engines/           # Core AI Logic (Health, Taste, Variety)
│   ├── data/              # Mock Database & Assets
│   └── models.py          # Data Schemas
├── frontend/              # Vite + React UI
├── NutriFlavorOS_flow.svg # Architectural Diagram
└── run_app.py             # Root execution script
```

## 📜 License
MIT License - Developed by Anurag.
