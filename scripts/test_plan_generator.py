import os
import sys
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force Mock Mode
os.environ["MOCK_MODE"] = "true"

from backend.models import UserProfile
from backend.engines.plan_generator import PlanGenerator

def test_plan_generation():
    print("🍱 Testing Plan Generator with New Mock Data...\n")
    
    # 1. Create Generator (should load recipes from recipes.json via Service)
    generator = PlanGenerator()
    print(f"✅ Generator initialized. Loaded {len(generator.recipes)} recipes.")
    
    if len(generator.recipes) == 0:
        print("❌ Failed to load recipes! Check mock data integration.")
        return

    # 2. Create Dummy User
    user = UserProfile(
        name="Test User",
        age=30,
        weight_kg=70,
        height_cm=175,
        gender="male",
        activity_level=1.4,
        goal="maintenance",
        liked_ingredients=["chicken", "avocado"],
        disliked_ingredients=["kale"],
        health_conditions=["Hypertension"] 
    )
    
    # 3. Generate Plan
    print("\ngenerating 1-day plan...")
    try:
        plan = generator.create_plan(user, days=1)
        
        print(f"✅ Plan generated for user: {plan.user_id}")
        print(f"   Daily Plans: {len(plan.days)}")
        print(f"   Shopping List Items: {len(plan.shopping_list)}")
        print(f"   Overall Stats: {plan.overall_stats}")
        
        # Check specific day
        day1 = plan.days[0]
        print(f"\n   Day 1 Meals:")
        for slot, recipe in day1.meals.items():
            print(f"    - {slot}: {recipe.name} ({recipe.calories} kcal)")
            
    except Exception as e:
        print(f"❌ Plan generation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_plan_generation()
