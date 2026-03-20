"""
API Endpoints for Online Learning and Gamification
Integrates all new ML features with the backend
"""
import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np

from backend.ml.online_learning_manager import online_learning_manager

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


# ==================== ONLINE LEARNING ENDPOINTS (Activated) ====================

@router.post("/feedback/taste")
async def log_taste_feedback(feedback: TasteFeedback):
    """
    Log user's taste rating and update taste predictor model
    """
    try:
        online_learning_manager.log_taste_feedback(
            user_id=feedback.user_id,
            recipe_id=feedback.recipe_id,
            user_genome=np.array(feedback.user_genome),
            recipe_profile=np.array(feedback.recipe_profile),
            rating=feedback.rating
        )
        return {
            "status": "success", 
            "message": "Taste feedback logged and model updated in background",
            "buffer_info": f"Updates trigger every {online_learning_manager.buffer_size} samples"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback/health")
async def log_health_outcome(outcome: HealthOutcome):
    """
    Log actual health outcomes and update trajectory models
    """
    try:
        online_learning_manager.log_health_outcome(
            user_id=outcome.user_id,
            meal_history=outcome.meal_history,
            actual_weight=outcome.actual_weight,
            actual_hba1c=outcome.actual_hba1c,
            actual_cholesterol=outcome.actual_cholesterol
        )
        return {
            "status": "success", 
            "message": "Health outcome logged",
            "buffer_info": f"Updates trigger every {online_learning_manager.buffer_size} samples"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback/meal_selection")
async def log_meal_selection(selection: MealSelection):
    """
    Update RL policy based on user selection
    """
    try:
        online_learning_manager.log_meal_selection(
            user_id=selection.user_id,
            state=np.array(selection.state),
            selected_recipe_id=selection.selected_recipe_id,
            reward=selection.reward
        )
        return {"status": "success", "message": "Meal selection reward logged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/stats/{model_name}")
async def get_model_stats(model_name: str):
    """
    Retrieve training statistics for a specific model
    """
    stats = online_learning_manager.get_model_stats(model_name)
    return stats

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
    
    key = f"leaderboard_{leaderboard_type}"
    leaderboard = data.get(key, [])
    
    for entry in leaderboard:
        if entry.get("user_id") == "usr_1" or entry.get("username") == "You":
            return {
                "rank": entry.get("rank"),
                "total_users": len(leaderboard) + 20,
                "percentile": 100 - (entry.get("rank", 4) * 5)
            }
            
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
