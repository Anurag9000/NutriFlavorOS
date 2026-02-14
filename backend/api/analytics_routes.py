import json
import os
from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

def load_demo_data(section: str):
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "demo_data.json")
        with open(path, 'r') as f:
            data = json.load(f)
        return data.get(section, {})
    except Exception as e:
        print(f"Error loading demo data: {e}")
        return {}

@router.get("/health/{user_id}")
async def get_health_insights(user_id: str, period: str = "30d"):
    """
    Get health insights based on meal plan data (Demo Mode)
    """
    data = load_demo_data("analytics")
    return data.get("health_history", [])

@router.get("/taste/{user_id}")
async def get_taste_insights(user_id: str):
    """
    Get taste profile (Demo Mode)
    """
    data = load_demo_data("analytics")
    return data.get("taste_profile", [])

@router.get("/variety/{user_id}")
async def get_variety_insights(user_id: str):
    """
    Get variety metrics (Demo Mode)
    """
    # Variety endpoint expects a list of {name, value} usually?
    # Checking frontend: it expects {name: string, value: number}[]
    data = load_demo_data("analytics")
    metrics = data.get("variety_metrics", {})
    return metrics.get("distribution", [])

@router.post("/predict_health")
async def predict_health(payload: Dict = Body(...)):
    """
    Predict future health score (Demo Mode)
    """
    return {
        "current_score": 85,
        "predicted_score": 92,
        "forecast": [
             {"day": 1, "score": 85},
             {"day": 15, "score": 88},
             {"day": 30, "score": 92},
        ]
    }

@router.get("/insights/{user_id}")
async def get_ai_insights(user_id: str):
    """
    Generate AI-powered nutritional insights (Demo Mode)
    """
    return {
        "insight": "Your protein intake has improved by 15% this week! Consider adding more variety to your vegetable selection to boost your micronutrient score.",
        "category": "health",
        "priority": "medium"
    }
