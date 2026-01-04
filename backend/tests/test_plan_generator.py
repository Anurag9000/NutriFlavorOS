import unittest
from backend.models import UserProfile, Gender, Goal
from backend.engines.plan_generator import PlanGenerator

class TestPlanGenerator(unittest.TestCase):
    def setUp(self):
        self.user = UserProfile(
            age=30, weight_kg=75, height_cm=180, gender=Gender.MALE, activity_level=1.55, goal=Goal.MAINTENANCE,
            liked_ingredients=[],
            disliked_ingredients=[]
        )
        self.generator = PlanGenerator()

    def test_create_plan_structure(self):
        days = 2
        plan = self.generator.create_plan(self.user, days=days)
        
        self.assertEqual(len(plan.days), days)
        for d in plan.days:
            self.assertIn("Breakfast", d.meals)
            self.assertIn("Lunch", d.meals)
            self.assertIn("Dinner", d.meals)
            self.assertGreater(d.total_stats["calories"], 0)
            self.assertIn("health_match", d.scores)

    def test_dislike_filter(self):
        # Create user who hates "salmon"
        user = self.user.model_copy()
        user.disliked_ingredients = ["salmon"]
        
        plan = self.generator.create_plan(user, days=5) # Generate enough to force search
        
        for d in plan.days:
            for meal in d.meals.values():
                for ing in meal.ingredients:
                    self.assertNotIn("salmon", ing.lower())

if __name__ == '__main__':
    unittest.main()
