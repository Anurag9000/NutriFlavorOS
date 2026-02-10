"""
Validate Trained ML Models
Tests inference and output correctness for all 4 trained models
"""
import os
import sys
import torch
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force Mock Mode
os.environ["MOCK_MODE"] = "true"

from backend.ml.taste_predictor import DeepTastePredictor
from backend.ml.health_predictor import HealthOutcomePredictor
from backend.ml.meal_planner_rl import RLMealPlanner
from backend.ml.grocery_predictor import GroceryPredictor
from backend.ml.device_config import get_device

print("🔍 ML MODEL VALIDATION SUITE")
print("=" * 70)

MODELS_DIR = Path("backend/ml/models")
device = get_device()
print(f"✅ Using device: {device}\n")

# ============================================================
# 1. TASTE PREDICTOR VALIDATION
# ============================================================
def validate_taste_predictor():
    print("\n[1/4] Validating Taste Predictor...")
    print("-" * 70)
    
    try:
        # Load model
        model = DeepTastePredictor(input_dim=512, hidden_dim=256, device=device)
        model_path = MODELS_DIR / "taste_predictor.pth"
        
        if not model_path.exists():
            print(f"  ❌ Model file not found: {model_path}")
            return False
        
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()
        print(f"  ✅ Model loaded from {model_path}")
        
        # Test inference
        user_genome = torch.randn(1, 1, 512).to(device)
        recipe_profile = torch.randn(1, 1, 512).to(device)
        
        with torch.no_grad():
            score, confidence = model(user_genome, recipe_profile)
        
        # Validate outputs
        assert score.shape == (1, 1), f"Expected shape (1, 1), got {score.shape}"
        assert 0 <= score.item() <= 1, f"Score {score.item()} not in [0, 1]"
        assert confidence.shape == (1, 2), f"Expected confidence shape (1, 2), got {confidence.shape}"
        
        print(f"  ✅ Inference successful")
        print(f"     - Hedonic Score: {score.item():.4f}")
        print(f"     - Confidence Interval: [{confidence[0, 0].item():.4f}, {confidence[0, 1].item():.4f}]")
        return True
        
    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================
# 2. HEALTH PREDICTOR VALIDATION
# ============================================================
def validate_health_predictor():
    print("\n[2/4] Validating Health Predictor...")
    print("-" * 70)
    
    try:
        # Load model
        predictor = HealthOutcomePredictor(input_dim=10, hidden_dim=128, device=device)
        model_path = MODELS_DIR / "health_predictor.pth"
        
        if not model_path.exists():
            print(f"  ❌ Model file not found: {model_path}")
            return False
        
        predictor.model.load_state_dict(torch.load(model_path, map_location=device))
        predictor.model.eval()
        print(f"  ✅ Model loaded from {model_path}")
        
        # Test inference with synthetic history
        user_history = [
            {
                'calories': 2000 + i * 10,
                'protein_g': 100,
                'carbs_g': 200,
                'fat_g': 70,
                'exercise_minutes': 30,
                'sleep_hours': 7,
                'stress_level': 5,
                'adherence': 0.8,
                'weight_kg': 70 - i * 0.1,
                'age': 30
            }
            for i in range(30)
        ]
        
        predictions = predictor.predict_outcomes(user_history)
        
        # Validate outputs
        assert 'weight_prediction_30d' in predictions
        assert 'hba1c_prediction' in predictions
        assert 'cholesterol_prediction' in predictions
        assert 'adherence_probability' in predictions
        assert 'trajectory' in predictions
        
        print(f"  ✅ Inference successful")
        print(f"     - Weight Prediction (30d): {predictions['weight_prediction_30d']} kg")
        print(f"     - HbA1c: {predictions['hba1c_prediction']}%")
        print(f"     - Cholesterol: {predictions['cholesterol_prediction']} mg/dL")
        print(f"     - Adherence Probability: {predictions['adherence_probability']}")
        return True
        
    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================
# 3. RL MEAL PLANNER VALIDATION
# ============================================================
def validate_rl_planner():
    print("\n[3/4] Validating RL Meal Planner...")
    print("-" * 70)
    
    try:
        # Load model
        planner = RLMealPlanner(state_dim=256, action_dim=100, lr=3e-4, device=device)
        model_path = MODELS_DIR / "meal_planner_rl.pth"
        
        if not model_path.exists():
            print(f"  ❌ Model file not found: {model_path}")
            return False
        
        planner.load_model(str(model_path))
        print(f"  ✅ Model loaded from {model_path}")
        
        # Test inference
        state = torch.randn(256).to(device)
        available_recipes = list(range(100))
        
        action, log_prob = planner.select_recipe(state, available_recipes)
        
        # Validate outputs
        assert isinstance(action, int), f"Expected int action, got {type(action)}"
        assert 0 <= action < 100, f"Action {action} not in [0, 100)"
        assert isinstance(log_prob, float), f"Expected float log_prob, got {type(log_prob)}"
        
        print(f"  ✅ Inference successful")
        print(f"     - Selected Recipe: {action}")
        print(f"     - Log Probability: {log_prob:.4f}")
        return True
        
    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================
# 4. GROCERY PREDICTOR VALIDATION
# ============================================================
def validate_grocery_predictor():
    print("\n[4/4] Validating Grocery Predictor...")
    print("-" * 70)
    
    try:
        # Load model
        predictor = GroceryPredictor(user_id="test_user", device=device)
        model_path = MODELS_DIR / "grocery_predictor.pth"
        
        if not model_path.exists():
            print(f"  ❌ Model file not found: {model_path}")
            return False
        
        predictor.model.load_state_dict(torch.load(model_path, map_location=device))
        predictor.model.eval()
        print(f"  ✅ Model loaded from {model_path}")
        
        # Test inference
        # Add some purchase history
        predictor.log_purchase([
            {"item": "chicken breast", "quantity": 2.0, "price": 10.0},
            {"item": "broccoli", "quantity": 1.0, "price": 3.0}
        ])
        
        # Predict next purchase
        prediction = predictor.predict_next_purchase("chicken breast")
        
        # Validate outputs
        assert 'days_until_purchase' in prediction
        assert 'quantity_needed' in prediction
        assert 'probability' in prediction
        assert 'current_stock' in prediction
        assert 'consumption_rate' in prediction
        
        print(f"  ✅ Inference successful")
        print(f"     - Days Until Purchase: {prediction['days_until_purchase']:.1f}")
        print(f"     - Quantity Needed: {prediction['quantity_needed']:.2f}")
        print(f"     - Purchase Probability: {prediction['probability']:.2f}")
        return True
        
    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================
# MAIN EXECUTION
# ============================================================
if __name__ == "__main__":
    print("Starting model validation...\n")
    
    results = {
        "Taste Predictor": validate_taste_predictor(),
        "Health Predictor": validate_health_predictor(),
        "RL Meal Planner": validate_rl_planner(),
        "Grocery Predictor": validate_grocery_predictor()
    }
    
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for model_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {model_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n✨ ALL MODELS VALIDATED SUCCESSFULLY! ✨")
        print("\nModels are ready for production use.")
        sys.exit(0)
    else:
        print("\n❌ SOME MODELS FAILED VALIDATION")
        print("\nPlease review the errors above.")
        sys.exit(1)
