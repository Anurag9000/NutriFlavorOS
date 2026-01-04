# NutriFlavorOS 🥗✨

**NutriFlavorOS** is a sophisticated, AI-driven nutrition and flavor optimization system. It combines physiological health requirements with psychological taste preferences to generate personalized, diverse, and delicious meal plans.

![Project Flow](./NutriFlavorOS_flow.svg)

## 🚀 Overview

The system operates on the frontier of personalized nutrition, ensuring that healthy eating is never boring. By analyzing a user's "Flavor Genome" and calculating precise nutritional targets, NutriFlavorOS crafts a culinary experience tailored specifically to the individual.

## 🧠 Core Engines

### 1. 🏥 Health Engine
Calculates precise macro and micro-nutrient targets based on user physical profiles, activity levels, and health goals. It scores recipes against these targets to ensure nutritional compliance.

### 2. 👅 Taste Engine
Constructs a **Flavor Genome** for the user by analyzing their ingredient preferences and dislikes. It predicts "Hedonic Scores" (pleasure ratings) for recipes, ensuring every meal is a delight.

### 3. 🔄 Variety Engine
Prevents "palate fatigue" by managing meal diversity. it tracks ingredient repetition and ensures a broad spectrum of flavors and textures over the planning period.

### 4. 📅 Plan Generator
The orchestrator that synthesizes inputs from all engines. It performs a weighted utility search to find the optimal balance between health, taste, and variety for multi-day schedules.

## 🛠️ Tech Stack

- **Backend:** Python, FastAPI, Pydantic, Uvicorn
- **Frontend:** React, Vite, Modern CSS
- **Design:** SVG-based Architectures, Responsive Layouts

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
