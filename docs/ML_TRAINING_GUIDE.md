# ML Model Training Guide

## Overview
This guide explains how to train all ML models in the FoodScope system using the comprehensive training script.

## Prerequisites
- ✅ All mock databases generated (`recipes.json`, `flavor_db.json`, etc.)
- ✅ PyTorch installed with CUDA support (if available)
- ✅ Backend dependencies installed (`pip install -r requirements.txt`)

## Quick Start

### 1. Train All Models (Recommended)
```bash
python scripts/train_all_models.py
```

This single command trains all 4 ML models:
- **Taste Predictor** (Transformer): Predicts user hedonic scores
- **Health Predictor** (LSTM): Forecasts weight/health outcomes
- **RL Meal Planner** (PPO): Learns optimal meal sequencing
- **Grocery Predictor** (LSTM): Predicts shopping needs

**Expected Duration**: 5-10 minutes on GPU, 15-30 minutes on CPU

### 2. Verify Training Success
```bash
ls backend/ml/models/
```

You should see:
- `taste_predictor.pth`
- `health_predictor.pth`
- `meal_planner_rl.pth`
- `grocery_predictor.pth`

## Model Details

### 1. Taste Predictor
- **Architecture**: Transformer with cross-attention
- **Input**: User flavor genome (512-dim) + Recipe profile (512-dim)
- **Output**: Hedonic score (0-1) + confidence interval
- **Training Data**: 5,000 synthetic user-recipe pairs
- **Epochs**: 20

### 2. Health Predictor
- **Architecture**: 2-layer LSTM
- **Input**: 30-day meal history (10 features/day)
- **Output**: Weight change, HbA1c, Cholesterol
- **Training Data**: 3,000 synthetic health sequences
- **Epochs**: 30

### 3. RL Meal Planner
- **Architecture**: PPO (Actor-Critic)
- **State**: User profile + meal history + pantry (256-dim)
- **Action**: Recipe selection (100 recipes)
- **Reward**: User rating + adherence + variety + health
- **Training Data**: 500 episodes (10 steps each)

### 4. Grocery Predictor
- **Architecture**: LSTM with item embeddings
- **Input**: Purchase history (item IDs + temporal features)
- **Output**: Quantity, days until purchase, probability
- **Training Data**: 2,000 synthetic purchase sequences
- **Epochs**: 25

## Advanced Usage

### Train Individual Models

```python
from backend.ml.taste_predictor import DeepTastePredictor
import torch

# Initialize
model = DeepTastePredictor()

# Your custom training loop here
# ...

# Save
torch.save(model.state_dict(), "backend/ml/models/taste_predictor.pth")
```

### Online Learning (Production)

Models automatically update from user interactions via `OnlineLearningManager`:

```python
from backend.ml.online_learning_manager import online_learning_manager

# Log user feedback
online_learning_manager.log_taste_feedback(
    user_id="user123",
    recipe_id="recipe456",
    user_genome=genome_vector,
    recipe_profile=profile_vector,
    rating=0.85
)

# Model updates automatically after 5 interactions
```

## GPU Acceleration

The training script automatically detects and uses CUDA if available:

```python
# Check GPU availability
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

## Troubleshooting

### Out of Memory
Reduce batch sizes in `train_all_models.py`:
```python
batch_size = 32  # Try 16 or 8
```

### Slow Training
- Ensure CUDA is enabled
- Reduce number of epochs
- Use smaller models (reduce `hidden_dim`)

### Import Errors
```bash
pip install -r requirements.txt
```

## Next Steps

After training:
1. **Start Backend**: `uvicorn backend.main:app --reload`
2. **Test API**: Visit `http://localhost:8000/docs`
3. **Generate Plans**: POST to `/api/v1/plan/generate`

## Model Performance

Expected performance on validation data:
- **Taste Predictor**: ~85% accuracy
- **Health Predictor**: ±5% weight prediction error
- **RL Planner**: 0.7+ average reward
- **Grocery Predictor**: 75% purchase prediction accuracy

*Note: These are synthetic training results. Real-world performance improves with actual user data.*
