from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from backend.services.flavordb_service import FlavorDBService
from backend.api.user_routes import get_user_profile

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# Initialize Services
flavor_service = FlavorDBService()

@router.get("/health/{user_id}")
async def get_health_insights(user_id: str, period: str = "30d"):
    """
    Get health insights based on meal plan data
    """
    from backend.api.meal_routes import get_cached_plan
    from backend.utils.analytics_helpers import calculate_daily_health_score
    
    # Get user's meal plan from cache
    meal_plan = get_cached_plan(user_id)
    if not meal_plan or not meal_plan.days:
        return []
    
    # Calculate health score for each day
    health_data = []
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    for idx, day in enumerate(meal_plan.days):
        # Convert day meals to dict format
        day_meals = {}
        if hasattr(day, 'meals'):
            for meal_type, meal in day.meals.items():
                day_meals[meal_type] = {
                    "calories": meal.calories,
                    "macros": {
                        "protein": meal.macros.protein if hasattr(meal.macros, 'protein') else 0,
                        "carbs": meal.macros.carbs if hasattr(meal.macros, 'carbs') else 0,
                        "fat": meal.macros.fat if hasattr(meal.macros, 'fat') else 0,
                    }
                }
        
        # Calculate score for this day
        score = calculate_daily_health_score(day_meals, user_target_calories=2000)
        
        health_data.append({
            "date": day_names[idx] if idx < len(day_names) else f"Day{idx+1}",
            "score": score
        })
    
    return health_data

@router.get("/taste/{user_id}")
async def get_taste_insights(user_id: str):
    """
    Get taste profile using FlavorDB analysis of user preferences
    """
    try:
        # 1. Fetch user profile to get liked ingredients
        user_profile = await get_user_profile(user_id)
        liked_ingredients = user_profile.get("liked_ingredients", ["Chocolate", "Strawberry", "Vanilla"])
        
        # 2. Analyze flavor profiles of liked ingredients
        flavor_profiles = {}
        for ingredient in liked_ingredients:
            # For each liked ingredient, get its flavor profile from FlavorDB
            # We aggregate counts of flavor descriptors (sweet, spicy, etc.)
            profile = flavor_service.get_flavor_profile(ingredient)
            if profile and "descriptors" in profile:
                for desc in profile["descriptors"]:
                    flavor_profiles[desc] = flavor_profiles.get(desc, 0) + 1
            
        # 3. Normalize data for Radar Chart
        # If DB returns empty (mock mode), use default data
        if not flavor_profiles:
             return [
                {"subject": "Spicy", "A": 120, "fullMark": 150},
                {"subject": "Sweet", "A": 98, "fullMark": 150},
                {"subject": "Salty", "A": 86, "fullMark": 150},
                {"subject": "Bitter", "A": 99, "fullMark": 150},
                {"subject": "Sour", "A": 85, "fullMark": 150},
                {"subject": "Umami", "A": 65, "fullMark": 150},
            ]
            
        # Convert to chart format
        chart_data = []
        max_val = max(flavor_profiles.values()) if flavor_profiles else 1
        for subject, count in flavor_profiles.items():
            normalized = (count / max_val) * 150
            chart_data.append({"subject": subject.capitalize(), "A": normalized, "fullMark": 150})
            
        return chart_data[:6] # Limit to top 6 dimensions
        
    except Exception as e:
        print(f"Error generating taste insights: {e}")
        # Return empty if FlavorDB unavailable
        return []

@router.get("/variety/{user_id}")
async def get_variety_insights(user_id: str):
    """
    Get variety metrics from meal plan
    """
    from backend.api.meal_routes import get_cached_plan
    from backend.utils.analytics_helpers import calculate_variety_distribution
    
    # Get user's meal plan from cache
    meal_plan = get_cached_plan(user_id)
    if not meal_plan or not meal_plan.days:
        return []
    
    # Convert meal plan to dict format for helper function
    days_data = []
    for day in meal_plan.days:
        day_dict = {"meals": {}}
        if hasattr(day, 'meals'):
            for meal_type, meal in day.meals.items():
                day_dict["meals"][meal_type] = {
                    "ingredients": meal.ingredients if hasattr(meal, 'ingredients') else []
                }
        days_data.append(day_dict)
    
    # Calculate variety distribution
    return calculate_variety_distribution(days_data)

@router.post("/predict_health")
async def predict_health(payload: Dict = Body(...)):
    """
    Predict future health score
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
    Generate AI-powered nutritional insights based on user's meal history
    """
    # TODO: Implement real insight generation based on meal history
    # For now, return a simple insight
    return {
        "insight": "Start logging meals to receive personalized AI insights about your nutrition patterns and recommendations.",
        "category": "general",
        "priority": "low"
    }
