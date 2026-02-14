import sys
import os
import json
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models import PlanResponse, DailyPlan, Recipe
from backend.utils.meal_persistence import save_meal_plans, load_meal_plans, meal_plan_cache, cache_plan

def create_dummy_plan():
    """Create a dummy plan for testing"""
    dummy_meal = Recipe(
        id="test_recipe_1",
        name="Test Recipe",
        description="A delicious test recipe",
        ingredients=["Ingredient 1", "Ingredient 2"],
        calories=500,
        macros={"protein": 30, "carbs": 50, "fat": 20}
    )
    
    day_plan = DailyPlan(
        day=1,
        meals={"breakfast": dummy_meal},
        scores={},
        total_stats={"calories": 500}
    )
    
    return PlanResponse(
        user_id="test_user_persistence",
        days=[day_plan],
        shopping_list={},
        prep_timeline={}
    )

def test_persistence():
    print("🧪 Testing Meal Plan Persistence...")
    
    # 1. Create and cache a plan
    user_id = "test_user_persistence"
    plan = create_dummy_plan()
    
    print("   1. Caching plan in memory...")
    cache_plan(user_id, plan)
    
    # Verify it's in cache
    if user_id not in meal_plan_cache:
        print("   ❌ Failed: Plan not in in-memory cache")
        return False
    
    # 2. Verify file was created
    if not os.path.exists("meal_plans.json"):
        print("   ❌ Failed: meal_plans.json not created")
        return False
    
    print("   ✅ meal_plans.json created")
    
    # 3. Clear in-memory cache to simulate server restart
    print("   2. Clearing in-memory cache (simulating restart)...")
    meal_plan_cache.clear()
    
    if user_id in meal_plan_cache:
        print("   ❌ Failed: Cache not cleared")
        return False
        
    # 4. Load from file
    print("   3. Loading from file...")
    loaded_cache = load_meal_plans()
    
    if user_id not in loaded_cache:
        print("   ❌ Failed: User not found in loaded cache")
        return False
    
    loaded_plan = loaded_cache[user_id]["plan"]
    
    # 5. Verify data integrity
    if loaded_plan.days[0].meals["breakfast"].name != "Test Recipe":
        print("   ❌ Failed: Data mismatch in loaded plan")
        return False
        
    print("   ✅ Data persisted and reloaded successfully!")
    
    # Cleanup
    if os.path.exists("meal_plans.json"):
        os.remove("meal_plans.json")
    
    return True

if __name__ == "__main__":
    try:
        success = test_persistence()
        sys.exit(0 if success else 1)
    except Exception as e:
        import traceback
        with open("full_error.txt", "w") as f:
            f.write(f"Sys Path: {sys.path}\n")
            traceback.print_exc(file=f)
        print(f"❌ Script crashed! detailed error in full_error.txt")
        sys.exit(1)
