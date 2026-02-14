# NutriFlavorOS - Complete ML Model Inventory

**Last Updated:** February 14, 2026  
**Status:** ✅ Production Ready | Trained to Convergence

---

## 🧠 ML Models in Production

### 1. **Deep Taste Predictor** (Transformer)
**File:** `backend/ml/taste_predictor.py`  
**Weights:** `backend/ml/weights/taste_predictor.pth`

**Architecture:**
- **Encoders**: Dual Transformer Encoders (User Genome, Recipe Profile)
- **Fusion**: Cross-Attention Fusion layer
- **Output**: Multi-head Predictor (Hedonic Score + Confidence)
- **Input Dim**: 512-dim flavor vectors

**Training:**
- **Method**: Supervised (MSE Loss)
- **Epochs**: Trained to convergence (Early Stopping patience 10)
- **Optimizer**: Adam (lr=1e-3)
- **Accuracy Target**: 95%+

---

### 2. **Health Outcome Predictor** (LSTM)
**File:** `backend/ml/health_predictor.py`  
**Weights:** `backend/ml/weights/health_predictor.pth`

**Architecture:**
- **Backbone**: 2-Layer LSTM (128 hidden units)
- **Sequence Length**: 30-day sliding window
- **Outputs**: Weight Trajectory, HbA1c, Cholesterol

**Training:**
- **Method**: Time-Series Forecasting
- **Epochs**: max 10,000 (Early Stopping triggered)
- **Loss**: MSE

---

### 3. **RL Meal Planner** (PPO)
**File:** `backend/ml/meal_planner_rl.py`  
**Weights:** `backend/ml/weights/rl_planner.pth`

**Architecture:**
- **Algorithm**: Proximal Policy Optimization (PPO)
- **Networks**: Actor (Policy) + Critic (Value)
- **Reward**: Multi-objective (40% Taste, 30% Health, 30% Variety)

**Training:**
- **Simulations**: 10,000+ episodes
- **Patience**: Converged when reward stabilized

---

### 4. **Grocery Predictor** (LSTM)
**File:** `backend/ml/grocery_predictor.py`  
**Weights:** `backend/ml/weights/grocery_predictor.pth`

**Architecture:**
- **Backbone**: LSTM for purchase pattern recognition
- **Outputs**: Quantity Needed, Days until empty, Purchase probability

**Training:**
- **Data**: Historical purchase + consumption patterns
- **Method**: Supervised Regression + Classification

---

### 5. **Recipe Generator** (GPT-based)
**File:** `backend/ml/recipe_generator_nlp.py`  
**Model**: GPT-2 (Fine-tuned on RecipeDB)

**Capabilities:**
- Personalized recipe creation from available ingredients
- Dietary constraint enforcement
- Cuisine-specific generation

---

### 6. **Recipe Vision** (CNN)
**File:** `backend/ml/recipe_vision.py`  
**Backbone**: ResNet50

**Capabilities:**
- Food classification (101 categories)
- Nutritional estimation from images (Calories, Macros)

---

## 🔄 Online Learning Manager
**File:** `backend/ml/online_learning_manager.py`

- **Mini-batch updates**: Triggers after every 5 user interactions
- **Versioning**: Automatic model checkpointing
- **Diversity**: Palate fatigue detection and correction

---

## 🚀 Training Regime
All models follow a standardized training protocol implemented in `scripts/train_all_models.py`:
- **Max Epochs**: 10,000
- **Early Stopping**: Patience 10 (triggers when validation loss plateau)
- **Device**: Automatic GPU/MPS/CPU detection via `device_config.py`

---

**NutriFlavorOS: The most intelligent, personalized, and engaging nutrition platform ever built.** 🚀
