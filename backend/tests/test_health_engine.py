import unittest
from backend.models import UserProfile, Gender, Goal, NutrientTarget
from backend.engines.health_engine import HealthEngine

class TestHealthEngine(unittest.TestCase):
    def setUp(self):
        self.base_user = UserProfile(
            age=25,
            weight_kg=70,
            height_cm=175,
            gender=Gender.MALE,
            activity_level=1.2,
            goal=Goal.MAINTENANCE,
            liked_ingredients=[],
            disliked_ingredients=[]
        )

    def test_bmr_calculation_male(self):
        # Male: (10 * 70) + (6.25 * 175) - (5 * 25) + 5
        # 700 + 1093.75 - 125 + 5 = 1673.75
        bmr = HealthEngine.calculate_bmr(self.base_user)
        self.assertAlmostEqual(bmr, 1673.75)

    def test_bmr_calculation_female(self):
        user_f = self.base_user.model_copy()
        user_f.gender = Gender.FEMALE
        # Female: (10 * 70) + (6.25 * 175) - (5 * 25) - 161
        # 1673.75 - 5 - 161 = 1507.75
        bmr = HealthEngine.calculate_bmr(user_f)
        self.assertAlmostEqual(bmr, 1507.75)

    def test_target_calories_weight_loss(self):
        user = self.base_user.model_copy()
        user.goal = Goal.WEIGHT_LOSS
        user.activity_level = 1.2
        
        bmr = HealthEngine.calculate_bmr(user)
        expected_tdee = bmr * 1.2
        expected_target = expected_tdee - 500
        
        target = HealthEngine.calculate_targets(user)
        self.assertEqual(target.calories, int(expected_target))

    def test_macro_split_muscle_gain(self):
        user = self.base_user.model_copy()
        user.goal = Goal.MUSCLE_GAIN
        
        targets = HealthEngine.calculate_targets(user)
        
        # Check ratios roughly (rounded to int in engine)
        total_cals = targets.calories
        protein_cals = targets.protein_g * 4
        
        # Muscle gain protein ratio is 0.35
        self.assertAlmostEqual(protein_cals / total_cals, 0.35, delta=0.01)

    def test_score_recipe_perfect_match(self):
        targets = NutrientTarget(calories=2100, protein_g=150, carbs_g=200, fat_g=70)
        # Perfect meal is 700 cals
        recipe_macros = {"calories": 700}
        
        score = HealthEngine.score_recipe(recipe_macros, targets)
        self.assertEqual(score, 1.0)

    def test_score_recipe_bad_match(self):
        targets = NutrientTarget(calories=2100, protein_g=150, carbs_g=200, fat_g=70)
        # Bad meal is 1400 cals (double)
        recipe_macros = {"calories": 1400}
        
        # Diff is 700. % diff is 1.0. Score = 1.0 - 1.0 = 0
        score = HealthEngine.score_recipe(recipe_macros, targets)
        self.assertEqual(score, 0.0)

if __name__ == '__main__':
    unittest.main()
