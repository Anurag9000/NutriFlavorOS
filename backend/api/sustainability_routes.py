from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/sustainability", tags=["sustainability"])

@router.get("/{user_id}")
async def get_sustainability_data(user_id: str, period: str = "monthly"):
    """
    Get sustainability metrics
    """
    return {
        "carbon_saved_kg": 12.5,
        "water_saved_l": 450,
        "trees_planted_equivalent": 2,
        "sustainable_meals_count": 15
    }

@router.get("/carbon/{user_id}")
async def get_carbon_footprint(user_id: str):
    """
    Get details carbon footprint breakdown
    """
    return {
        "total_footprint": 120.5,
        "average_meal_footprint": 1.5,
        "breakdown": [
            {"category": "Meat", "value": 60},
            {"category": "Dairy", "value": 30},
            {"category": "Produce", "value": 10},
            {"category": "Grains", "value": 20.5}
        ]
    }
