import sys
import os

# Add backend to sys path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.models import UserProfile, Gender, Goal
from backend.engines.plan_generator import PlanGenerator

def test_generation():
    print("Testing Backend Logic...")
    
    # Create Dummy User
    user = UserProfile(
        age=30,
        weight_kg=75,
        height_cm=180,
        gender=Gender.MALE,
        activity_level=1.55,
        goal=Goal.MUSCLE_GAIN,
        liked_ingredients=["chicken", "spicy"],
        disliked_ingredients=["kale"],
        dietary_restrictions=[]
    )
    
    print(f"User Created: Target Goal {user.goal}")
    
    # Init Generator
    try:
        gen = PlanGenerator()
        print("PlanGenerator Initialized (DB Loaded)")
        
        # Run Generation
        plan = gen.create_plan(user, days=1)
        
        print("\n--- Generated Plan ---")
        day1 = plan.days[0]
        print(f"Calorie Target: {day1.total_stats['target_calories']}")
        print(f"Total Calories: {day1.total_stats['calories']}")
        print(f"Scores: {day1.scores}")
        print("Meals:")
        for slot, meal in day1.meals.items():
            print(f"  {slot}: {meal.name} ({meal.calories} kcal)")
            
        print("\nTest Passed Successfully")
        
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_generation()
