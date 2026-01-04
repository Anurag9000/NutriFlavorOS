import unittest
from backend.models import UserProfile, Gender, Goal, Recipe
from backend.engines.taste_engine import TasteEngine

class TestTasteEngine(unittest.TestCase):
    def test_flavor_genome_generation(self):
        user = UserProfile(
            age=25, weight_kg=70, height_cm=175, gender=Gender.MALE, activity_level=1.2, goal=Goal.MAINTENANCE,
            liked_ingredients=["Strawberry", "Chili"],
            disliked_ingredients=["Kale"]
        )
        
        genome = TasteEngine.generate_flavor_genome(user)
        
        # Strawberry -> Sweet +0.2
        self.assertGreater(genome["sweet"], 0.5)
        # Chili -> Spicy +0.3
        self.assertGreater(genome["spicy"], 0.5)
        # Kale -> Bitter -0.2
        self.assertLess(genome["bitter"], 0.1)

    def test_hedonic_score(self):
        genome = {"sweet": 0.8, "salty": 0.2}
        
        # Recipe matches sweet preference
        r1 = Recipe(
            id="1", name="Sweet Cake", description="d", ingredients=[], calories=100, macros={}, tags=[],
            flavor_profile={"sweet": 0.8, "salty": 0.2}
        )
        
        # Recipe opposes preference
        r2 = Recipe(
            id="2", name="Salty Soup", description="d", ingredients=[], calories=100, macros={}, tags=[],
            flavor_profile={"sweet": 0.2, "salty": 0.8}
        )
        
        score1 = TasteEngine.predict_hedonic_score(r1, genome)
        score2 = TasteEngine.predict_hedonic_score(r2, genome)
        
        self.assertGreater(score1, score2)

if __name__ == '__main__':
    unittest.main()
