# FoodScope - Intelligent Nutrition & Sustainability Platform

FoodScope is a next-generation food tracking and meal planning application that integrates Personalization, Sustainability, and Health into a unified experience.

## 🚀 Key Features

### 🥗 Smart Meal Planning
- **AI-Powered Generation**: Generates 7-day meal plans based on your taste profile and health goals.
- **RecipeDB Integration**: Access to 118,000+ recipes with detailed macro/micronutrient data.
- **Dynamic Swapping**: Instantly swap meals while maintaining nutritional balance.

### 🎮 Gamification & Social
- **Leaderboards**: Compete with friends on Carbon Saved, Health Score, and Variety.
- **Achievements**: Unlock badges for milestones (e.g., "Green Eater", "Streak Master").
- **Taste Profiling**: Visualize your flavor preferences with the interactive Radar Chart.

### 🌍 Sustainability Tracking
- **Carbon Footprint**: Real-time tracking of your diet's environmental impact.
- **Eco-Recommendations**: Smart suggestions to reduce your footprint (e.g., "Try a meatless Monday").

### 🛒 Smart Grocery
- **Auto-Generated Lists**: Shopping lists created automatically from your meal plan.
- **Inventory Tracking**: Track what you have at home to reduce waste.

## 🛠️ Technology Stack

- **Frontend**: React, Vite, Tailwind CSS, Framer Motion, Recharts
- **Backend**: FastAPI (Python), Pandas, NumPy, Scikit-learn
- **Data Services**: RecipeDB, FlavorDB, DietRxDB, SustainableFoodDB

## 📦 Installation & Setup

### Prerequisites
- Node.js (v16+)
- Python (v3.9+)

### 1. Backend Setup
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env with your API keys
```

### 2. Frontend Setup
```bash
cd frontend
npm install
```

## 🏃‍♂️ Running the App

### Option A: Quick Start (Windows)
Double-click the batch files in the root directory:
1. `start_backend.bat`
2. `start_frontend.bat`

### Option B: Manual Start
**Backend:**
```bash
cd backend
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm run dev
```

Visit `http://localhost:5174` to use the app!

## 🤝 APIs & Credits
This project leverages the CosyLab suite of databases:
- **RecipeDB**: Recipe data and nutrition.
- **FlavorDB**: Molecular flavor analysis.
- **DietRxDB**: Health condition and nutrition interactions.
