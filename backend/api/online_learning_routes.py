"""
API Endpoints for Online Learning and Gamification
Integrates all new ML features with the backend
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np

import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np

# from backend.ml.online_learning_manager import online_learning_manager
# from backend.ml.grocery_predictor import GroceryPredictor
# from backend.gamification.gamification_engine import gamification_engine

router = APIRouter(prefix="/api/v1", tags=["online_learning"])

def load_demo_data(section: str):
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "demo_data.json")
        with open(path, 'r') as f:
            data = json.load(f)
        return data.get(section, {})
    except Exception as e:
        print(f"Error loading demo data: {e}")
        return {}

# ==================== MODELS ====================

class TasteFeedback(BaseModel):
    user_id: str
    recipe_id: str
    rating: float  # 0-1 scale
    user_genome: List[float]
    recipe_profile: List[float]

class HealthOutcome(BaseModel):
    user_id: str
    actual_weight: float
    actual_hba1c: Optional[float] = None
    actual_cholesterol: Optional[float] = None
    meal_history: List[Dict]

class MealSelection(BaseModel):
    user_id: str
    state: List[float]
    selected_recipe_id: int
    reward: float

class GroceryPurchase(BaseModel):
    user_id: str
    items: List[Dict]  # [{item: str, quantity: float, price: float}]

class GroceryConsumption(BaseModel):
    user_id: str
    item: str
    quantity: float

class MealImpact(BaseModel):
    user_id: str
    carbon_footprint: float
    health_score: float
    variety_score: float
    taste_rating: Optional[float] = None

# ==================== ONLINE LEARNING ENDPOINTS (Stubbed) ====================

@router.post("/feedback/taste")
async def log_taste_feedback(feedback: TasteFeedback):
    return {"status": "success", "message": "Taste feedback logged (Demo)", "current_buffer_size": 5}

@router.post("/feedback/health")
async def log_health_outcome(outcome: HealthOutcome):
    return {"status": "success", "message": "Health outcome logged (Demo)", "current_buffer_size": 5}

@router.post("/feedback/meal_selection")
async def log_meal_selection(selection: MealSelection):
    return {"status": "success", "message": "Meal selection logged (Demo)"}

@router.get("/models/stats/{model_name}")
async def get_model_stats(model_name: str):
    return {"updates": 10, "avg_loss": 0.05, "last_update": datetime.now().isoformat()}

# ==================== GROCERY PREDICTION ENDPOINTS (Demo Data) ====================

@router.post("/grocery/purchase")
async def log_grocery_purchase(purchase: GroceryPurchase):
    return {"status": "success", "message": f"Logged {len(purchase.items)} items (Demo)", "total_items_tracked": 50}

@router.post("/grocery/consume")
async def log_grocery_consumption(consumption: GroceryConsumption):
    return {"status": "success", "message": f"Logged consumption (Demo)", "current_stock": 0, "consumption_rate": 0}

@router.get("/grocery/predict/{user_id}/{item}")
async def predict_next_purchase(user_id: str, item: str):
    data = load_demo_data("grocery")
    preds = data.get("predictions", {})
    item_pred = preds.get(item, {"days_until_purchase": 7, "current_stock": 0.5})
    
    return {
        "item": item,
        "prediction": item_pred,
        "recommendation": "✅ Sufficient stock" if item_pred["current_stock"] > 0 else "⚠️ Buy soon"
    }

@router.get("/grocery/shopping_list/{user_id}")
async def generate_shopping_list(user_id: str, days_ahead: int = 7):
    """
    Generate ML-optimized shopping list (Demo Mode)
    """
    data = load_demo_data("grocery")
    
    # Simple logic for Demo: 
    # If days_ahead > 7, assume "Next Week" tab is clicked or requested
    # The frontend likely toggles between current week (e.g. 7 days) and next week (e.g. 14 days or offset)
    # Let's assume > 7 means "Next Week" for this demo context.
    
    if days_ahead > 7:
        shopping_list = data.get("shopping_list_next_week", [])
        # If next week list is missing, fallback to standard but maybe shuffle or modify?
        if not shopping_list:
             shopping_list = data.get("shopping_list", [])
    else:
        shopping_list = data.get("shopping_list", [])
        
    total_cost = sum(item["estimated_cost"] for item in shopping_list)
    
    return {
        "shopping_list": shopping_list,
        "summary": {
            "total_items": len(shopping_list),
            "estimated_total_cost": round(total_cost, 2),
            "days_covered": days_ahead,
            "urgent_items": len([i for i in shopping_list if i.get("urgency", 0) > 0.7])
        }
    }

# ==================== GAMIFICATION ENDPOINTS (Demo Data) ====================

@router.post("/gamification/log_meal")
async def log_meal_impact(impact: MealImpact):
    return {
        "status": "success",
        "visual_impact": {"trees": 1, "car_miles": 5},
        "new_achievements": [],
        "total_points": 1250
    }

@router.get("/gamification/leaderboard")
async def get_leaderboard(leaderboard_type: str = "carbon_saved", period: str = "month", limit: int = 100):
    data = load_demo_data("gamification")
    
    # Map frontend types to JSON keys
    # specific keys: leaderboard_carbon_saved, leaderboard_health_score, leaderboard_variety_score
    # frontend sends: "carbon_saved", "health_score", "variety_score"
    
    key = f"leaderboard_{leaderboard_type}"
    leaderboard = data.get(key, data.get("leaderboard", []))
    
    return {
        "leaderboard": leaderboard,
        "type": leaderboard_type,
        "period": period
    }

@router.get("/gamification/rank/{user_id}")
async def get_user_rank(user_id: str, leaderboard_type: str = "carbon_saved"):
    data = load_demo_data("gamification")
    leaderboard = data.get("leaderboard", [])
    # Find user in leaderboard, else return default
    for user in leaderboard:
        if user["user_id"] == "usr_1": # Assuming usr_1 is current user for demo
            return {"rank": user["rank"], "total_users": 100, "percentile": 95}
    return {"rank": 4, "total_users": 100, "percentile": 96}

@router.get("/gamification/achievements/{user_id}")
async def get_user_achievements(user_id: str):
    data = load_demo_data("gamification")
    achievements = data.get("achievements", [])
    return {
        "achievements": achievements,
        "total_earned": len(achievements)
    }

@router.get("/gamification/impact_summary/{user_id}")
async def get_monthly_impact_summary(user_id: str):
    data = load_demo_data("gamification")
    return data.get("impact_summary", {})
