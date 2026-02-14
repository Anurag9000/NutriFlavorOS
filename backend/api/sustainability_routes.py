from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/sustainability", tags=["sustainability"])

@router.get("/{user_id}")
async def get_sustainability_data(user_id: str, period: str = "monthly"):
    """
    Get sustainability metrics from meal plan
    """
    from backend.api.meal_routes import get_cached_plan
    from backend.utils.sustainability_helpers import calculate_sustainability_metrics
    
    # Get user's meal plan from cache
    meal_plan = get_cached_plan(user_id)
    if not meal_plan or not meal_plan.days:
        return {
            "carbon_saved_kg": 0,
            "water_saved_l": 0,
            "trees_planted_equivalent": 0,
            "sustainable_meals_count": 0
        }
    
    # Convert meal plan to dict format
    days_data = []
    for day in meal_plan.days:
        day_dict = {"meals": {}}
        if hasattr(day, 'meals'):
            for meal_type, meal in day.meals.items():
                day_dict["meals"][meal_type] = {
                    "ingredients": meal.ingredients if hasattr(meal, 'ingredients') else []
                }
        days_data.append(day_dict)
    
    # Calculate sustainability metrics
    metrics = calculate_sustainability_metrics(days_data)
    
    return {
        "carbon_saved_kg": metrics["carbon_saved_kg"],
        "water_saved_l": metrics["water_saved_l"],
        "trees_planted_equivalent": metrics["trees_planted_equivalent"],
        "sustainable_meals_count": metrics["sustainable_meals_count"]
    }

@router.get("/carbon-footprint/{user_id}")
async def get_carbon_footprint(user_id: str):
    """
    Get detailed carbon footprint breakdown from meal plan
    """
    from backend.api.meal_routes import get_cached_plan
    from backend.utils.sustainability_helpers import calculate_sustainability_metrics, calculate_carbon_breakdown
    
    # Get user's meal plan from cache
    meal_plan = get_cached_plan(user_id)
    if not meal_plan or not meal_plan.days:
        return {
            "total_footprint": 0,
            "average_meal_footprint": 0,
            "breakdown": []
        }
    
    # Convert meal plan to dict format
    days_data = []
    for day in meal_plan.days:
        day_dict = {"meals": {}}
        if hasattr(day, 'meals'):
            for meal_type, meal in day.meals.items():
                day_dict["meals"][meal_type] = {
                    "ingredients": meal.ingredients if hasattr(meal, 'ingredients') else []
                }
        days_data.append(day_dict)
    
    # Calculate metrics
    metrics = calculate_sustainability_metrics(days_data)
    breakdown = calculate_carbon_breakdown(days_data)
    
    total_meals = sum(len(day.get("meals", {})) for day in days_data)
    avg_footprint = metrics["total_carbon_kg"] / total_meals if total_meals > 0 else 0
    
    return {
        "total_footprint": metrics["total_carbon_kg"],
        "average_meal_footprint": round(avg_footprint, 1),
        "breakdown": breakdown
    }
