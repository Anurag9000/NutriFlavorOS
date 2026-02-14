import json
import os
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/sustainability", tags=["sustainability"])

def load_demo_data(section: str):
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "demo_data.json")
        with open(path, 'r') as f:
            data = json.load(f)
        return data.get(section, {})
    except Exception as e:
        print(f"Error loading demo data: {e}")
        return {}

@router.get("/{user_id}")
async def get_sustainability_data(user_id: str, period: str = "monthly"):
    """
    Get sustainability metrics (Demo Mode)
    """
    data = load_demo_data("sustainability")
    return data.get("current_period", {
        "carbon_saved_kg": 0,
        "water_saved_l": 0,
        "trees_planted_equivalent": 0,
        "sustainable_meals_count": 0
    })

@router.get("/carbon-footprint/{user_id}")
async def get_carbon_footprint(user_id: str):
    """
    Get detailed carbon footprint breakdown (Demo Mode)
    """
    data = load_demo_data("sustainability")
    return data.get("footprint", {
        "total_footprint": 0,
        "average_meal_footprint": 0,
        "breakdown": []
    })
