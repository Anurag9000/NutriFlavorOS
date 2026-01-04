import unittest
from backend.models import Recipe
from backend.engines.variety_engine import VarietyEngine

class TestVarietyEngine(unittest.TestCase):
    def test_entropy_high_variety(self):
        # 3 completely different recipes
        plan = [
            Recipe(id="1", name="A", description="", ingredients=["a", "b"], calories=0, macros={}, tags=[]),
            Recipe(id="2", name="B", description="", ingredients=["c", "d"], calories=0, macros={}, tags=[]),
            Recipe(id="3", name="C", description="", ingredients=["e", "f"], calories=0, macros={}, tags=[])
        ]
        
        # Total ingredients = 6. Unique = 6. Score = 1.0
        score = VarietyEngine.calculate_variety_score(plan)
        self.assertEqual(score, 1.0)

    def test_entropy_low_variety(self):
        # 3 identical recipes
        plan = [
            Recipe(id="1", name="A", description="", ingredients=["a", "b"], calories=0, macros={}, tags=[]),
            Recipe(id="1", name="A", description="", ingredients=["a", "b"], calories=0, macros={}, tags=[]),
            Recipe(id="1", name="A", description="", ingredients=["a", "b"], calories=0, macros={}, tags=[])
        ]
        
        # Total = 6. Unique = 2. Score = 2/6 = 0.33
        score = VarietyEngine.calculate_variety_score(plan)
        self.assertAlmostEqual(score, 1.0/3.0)

    def test_check_repetition(self):
        r1 = Recipe(id="1", name="A", description="", ingredients=["chicken"], calories=0, macros={}, tags=[])
        r2 = Recipe(id="2", name="B", description="", ingredients=["beef"], calories=0, macros={}, tags=[])
        
        history = [r1]
        
        # Same ID
        self.assertTrue(VarietyEngine.check_repetition(r1, history))
        
        # Different
        self.assertFalse(VarietyEngine.check_repetition(r2, history))
        
        # Same Main Ingredient (first item in list)
        r3 = Recipe(id="3", name="C", description="", ingredients=["chicken", "rice"], calories=0, macros={}, tags=[])
        self.assertTrue(VarietyEngine.check_repetition(r3, history))

if __name__ == '__main__':
    unittest.main()
