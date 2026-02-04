"""
API Endpoints for Online Learning and Gamification
Integrates all new ML features with the backend
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np

from backend.ml.online_learning_manager import online_learning_manager
from backend.ml.grocery_predictor import GroceryPredictor
from backend.gamification.gamification_engine import gamification_engine

router = APIRouter(prefix="/api/v1", tags=["online_learning"])

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

# ==================== ONLINE LEARNING ENDPOINTS ====================

@router.post("/feedback/taste")
async def log_taste_feedback(feedback: TasteFeedback):
    """
    Log user's taste rating - triggers real-time model update
    """
    try:
        user_genome = np.array(feedback.user_genome)
        recipe_profile = np.array(feedback.recipe_profile)
        
        online_learning_manager.log_taste_feedback(
            user_id=feedback.user_id,
            recipe_id=feedback.recipe_id,
            user_genome=user_genome,
            recipe_profile=recipe_profile,
            rating=feedback.rating
        )
        
        return {
            "status": "success",
            "message": "Taste feedback logged. Model will update after 5 interactions.",
            "current_buffer_size": len(online_learning_manager.interaction_buffer["taste"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback/health")
async def log_health_outcome(outcome: HealthOutcome):
    """
    Log actual health outcomes - triggers health predictor update
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
            "message": "Health outcome logged. Model learning from your data.",
            "current_buffer_size": len(online_learning_manager.interaction_buffer["health"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback/meal_selection")
async def log_meal_selection(selection: MealSelection):
    """
    Log meal selection - triggers RL planner update
    """
    try:
        state = np.array(selection.state)
        
        online_learning_manager.log_meal_selection(
            user_id=selection.user_id,
            state=state,
            selected_recipe_id=selection.selected_recipe_id,
            reward=selection.reward
        )
        
        return {
            "status": "success",
            "message": "Meal selection logged. RL agent is learning your preferences."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/stats/{model_name}")
async def get_model_stats(model_name: str):
    """
    Get statistics about model updates
    """
    try:
        stats = online_learning_manager.get_model_stats(model_name)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== GROCERY PREDICTION ENDPOINTS ====================

@router.post("/grocery/purchase")
async def log_grocery_purchase(purchase: GroceryPurchase):
    """
    Log grocery purchase - triggers grocery predictor update
    """
    try:
        predictor = GroceryPredictor(purchase.user_id)
        predictor.log_purchase(purchase.items)
        
        return {
            "status": "success",
            "message": f"Logged {len(purchase.items)} items. Grocery predictor updated.",
            "total_items_tracked": len(predictor.item_to_id)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/grocery/consume")
async def log_grocery_consumption(consumption: GroceryConsumption):
    """
    Log item consumption - updates inventory and consumption rate
    """
    try:
        predictor = GroceryPredictor(consumption.user_id)
        predictor.update_inventory(
            item=consumption.item,
            quantity=consumption.quantity,
            action="consume"
        )
        
        return {
            "status": "success",
            "message": f"Logged consumption of {consumption.quantity} {consumption.item}",
            "current_stock": predictor.current_inventory.get(consumption.item, 0),
            "consumption_rate": predictor.consumption_rates.get(consumption.item, 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/grocery/predict/{user_id}/{item}")
async def predict_next_purchase(user_id: str, item: str):
    """
    Predict when user will need to buy an item
    """
    try:
        predictor = GroceryPredictor(user_id)
        prediction = predictor.predict_next_purchase(item)
        
        return {
            "item": item,
            "prediction": prediction,
            "recommendation": _get_purchase_recommendation(prediction)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/grocery/shopping_list/{user_id}")
async def generate_shopping_list(user_id: str, days_ahead: int = 7):
    """
    Generate ML-optimized shopping list
    """
    try:
        predictor = GroceryPredictor(user_id)
        shopping_list = predictor.generate_shopping_list(days_ahead)
        
        total_cost = sum(item["estimated_cost"] for item in shopping_list)
        
        return {
            "shopping_list": shopping_list,
            "summary": {
                "total_items": len(shopping_list),
                "estimated_total_cost": round(total_cost, 2),
                "days_covered": days_ahead,
                "urgent_items": len([i for i in shopping_list if i["urgency"] > 0.7])
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== GAMIFICATION ENDPOINTS ====================

@router.post("/gamification/log_meal")
async def log_meal_impact(impact: MealImpact):
    """
    Log meal impact - updates gamification stats and checks achievements
    """
    try:
        result = gamification_engine.log_meal_impact(
            user_id=impact.user_id,
            meal_data={
                "carbon_footprint": impact.carbon_footprint,
                "health_score": impact.health_score,
                "variety_score": impact.variety_score,
                "taste_rating": impact.taste_rating
            }
        )
        
        return {
            "status": "success",
            "visual_impact": result["visual_impact"],
            "new_achievements": result.get("new_achievements", []),
            "total_points": result["updated_stats"].get("total_points", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gamification/leaderboard")
async def get_leaderboard(
    leaderboard_type: str = "carbon_saved",
    period: str = "month",
    limit: int = 100
):
    """
    Get leaderboard rankings
    """
    try:
        leaderboard = gamification_engine.get_leaderboard(
            leaderboard_type=leaderboard_type,
            period=period,
            limit=limit
        )
        
        return {
            "leaderboard": leaderboard,
            "type": leaderboard_type,
            "period": period
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gamification/rank/{user_id}")
async def get_user_rank(user_id: str, leaderboard_type: str = "carbon_saved"):
    """
    Get user's current rank
    """
    try:
        rank_info = gamification_engine.get_user_rank(user_id, leaderboard_type)
        return rank_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gamification/achievements/{user_id}")
async def get_user_achievements(user_id: str):
    """
    Get all achievements earned by user
    """
    try:
        achievements = gamification_engine.get_user_achievements(user_id)
        return {
            "achievements": achievements,
            "total_earned": len(achievements)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gamification/impact_summary/{user_id}")
async def get_monthly_impact_summary(user_id: str):
    """
    Get monthly impact summary with visual comparisons
    """
    try:
        summary = gamification_engine.get_monthly_impact_summary(user_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== HELPER FUNCTIONS ====================

def _get_purchase_recommendation(prediction: Dict) -> str:
    """Generate purchase recommendation based on prediction"""
    days_until = prediction["days_until_purchase"]
    current_stock = prediction["current_stock"]
    
    if days_until <= 2:
        return "🚨 Buy soon! Running low."
    elif days_until <= 5:
        return "⚠️ Add to shopping list"
    elif current_stock > 0:
        return "✅ Sufficient stock"
    else:
        return "📝 Consider buying"
