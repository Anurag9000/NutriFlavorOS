from fastapi import APIRouter, HTTPException, Body
from backend.models import UserProfile, PlanResponse, DailyPlan, Recipe
from backend.engines.plan_generator import PlanGenerator
from typing import Dict

router = APIRouter(prefix="/api/v1/meals", tags=["meals"])

# Initialize generator
generator = PlanGenerator()

@router.post("/generate", response_model=PlanResponse)
async def generate_meal_plan(user: UserProfile):
    """
    Generate a 7-day meal plan
    """
    try:
        plan = generator.create_plan(user, days=7)
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/regenerate_day")
async def regenerate_day(payload: Dict = Body(...)):
    """
    Regenerate a specific day in the plan
    """
    user_id = payload.get("user_id")
    day_index = payload.get("day_index")
    
    # In a real app, we would fetch the user profile from DB using user_id
    # For now, we'll create a dummy profile to generate a single day
    dummy_user = UserProfile(
        age=30, weight_kg=70, height_cm=175, gender="male", 
        activity_level=1.5, goal="maintenance"
    )
    
    try:
        # Generate a single day plan
        # We might need to adjust PlanGenerator to support single day generation or just take one day from a new plan
        full_plan = generator.create_plan(dummy_user, days=1)
        new_day = full_plan.days[0]
        new_day.day = day_index + 1 # Adjust day number
        return new_day
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/swap_meal")
async def swap_meal(payload: Dict = Body(...)):
    """
    Swap a specific meal
    """
    user_id = payload.get("user_id")
    meal_slot = payload.get("meal_slot") # e.g. "breakfast"
    
    # Logic to find a replacement recipe
    # For now, return a random recipe from the generator's DB if accessible, or a mock one.
    # We will instantiate a temporary generator to access its db
    
    try:
        # This is a bit inefficient but works for prototype
        # ideally we expose a 'get_random_recipe' method in PlanGenerator or RecipeDBService
        dummy_user = UserProfile(
            age=30, weight_kg=70, height_cm=175, gender="male", 
            activity_level=1.5, goal="maintenance"
        )
        # Generate a small plan and pick a meal
        plan = generator.create_plan(dummy_user, days=1)
        new_recipe = plan.days[0].meals.get(meal_slot)
        
        if not new_recipe:
             # Fallback if slot doesn't exist in generated plan (unlikely)
             new_recipe = list(plan.days[0].meals.values())[0]
             
        return new_recipe
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
