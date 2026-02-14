
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models import UserProfile, Gender, Goal
from backend.engines.plan_generator import PlanGenerator

def verify_dietary_compliance():
    print("🥗 Verifying Dietary Compliance...\n")
    
    generator = PlanGenerator()
    
    # Test Case 1: Vegetarian + Peanut Allergy
    print("Test 1: Vegetarian + Peanut Allergy")
    user_veg = UserProfile(
        name="Veggie User",
        age=30, weight_kg=70, height_cm=170, gender=Gender.MALE, activity_level=1.4, goal=Goal.MAINTENANCE,
        dietary_restrictions=["Vegetarian"],
        disliked_ingredients=["Allergy: Peanut"]
    )
    
    plan_veg = generator.create_plan(user_veg, days=1)
    
    forbidden_veg = ["chicken", "beef", "pork", "meat", "lamb", "fish", "salmon", "tuna", "shrimp", "peanut"]
    
    violations = []
    for day in plan_veg.days:
        for meal_name, recipe in day.meals.items():
            for ing in recipe.ingredients:
                ing_lower = ing.lower()
                for forbidden in forbidden_veg:
                    if forbidden in ing_lower:
                        violations.append(f"{meal_name}: Found '{ing}' (Violates '{forbidden}')")
    
    if violations:
        print(f"❌ FAILED: Found {len(violations)} violations.")
        for v in violations[:5]: print(f"   - {v}")
    else:
        print("✅ PASSED: No meat or peanuts found in Vegetarian plan.")

    # Test Case 2: Vegan
    print("\nTest 2: Vegan")
    user_vegan = UserProfile(
        name="Vegan User",
        age=30, weight_kg=70, height_cm=170, gender=Gender.MALE, activity_level=1.4, goal=Goal.MAINTENANCE,
        dietary_restrictions=["Vegan"]
    )
    
    plan_vegan = generator.create_plan(user_vegan, days=1)
    
    forbidden_vegan = ["chicken", "beef", "fish", "egg", "milk", "cheese", "yogurt", "butter", "honey"]
    
    violations = []
    for day in plan_vegan.days:
        for meal_name, recipe in day.meals.items():
            for ing in recipe.ingredients:
                ing_lower = ing.lower()
                for forbidden in forbidden_vegan:
                    if forbidden in ing_lower:
                        violations.append(f"{meal_name}: Found '{ing}' (Violates '{forbidden}')")

    if violations:
        print(f"❌ FAILED: Found {len(violations)} violations.")
        for v in violations[:5]: print(f"   - {v}")
    else:
        print("✅ PASSED: No animal products found in Vegan plan.")

    print("\n--------------------------------------------------")
    print("DIETARY VERIFICATION COMPLETE")

if __name__ == "__main__":
    verify_dietary_compliance()
