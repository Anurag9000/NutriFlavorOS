import json
import os
import sys

# Mocking the environment to test the loader
# Add the project root to sys.path to import models
sys.path.append(r"d:\Finished Projects\Resume\FoodScope")

from backend.models import PlanResponse

def load_demo_data(section: str):
    try:
        path = r"d:\Finished Projects\Resume\FoodScope\backend\data\demo_data.json"
        with open(path, 'r') as f:
            data = json.load(f)
        return data.get(section, {})
    except Exception as e:
        print(f"Error loading demo data: {e}")
        return {}

def verify():
    print("Verifying Demo Data Loading...")
    demo_plan_data = load_demo_data("meal_plan")
    if not demo_plan_data:
        print("❌ Failed: 'meal_plan' section not found in demo_data.json")
        return

    # Mock the user_id injection done in routes
    demo_plan_data["user_id"] = "usr_1"
    
    try:
        # Validate against Pydantic model
        plan = PlanResponse(**demo_plan_data)
        print("✅ Success: Demo Meal Plan matches Pydantic PlanResponse schema!")
        print(f"   Days: {len(plan.days)}")
        print(f"   Day 1 Metrics: {plan.days[0].total_stats}")
        
        # Check a recipe
        first_meal = list(plan.days[0].meals.values())[0]
        print(f"   Recipe 1: {first_meal.name} (ID: {first_meal.id})")
        
    except Exception as e:
        print(f"❌ Validation Error: {e}")

if __name__ == "__main__":
    verify()
