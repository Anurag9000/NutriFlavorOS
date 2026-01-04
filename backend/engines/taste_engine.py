from typing import Dict, List
from backend.models import UserProfile, Recipe

class TasteEngine:
    @staticmethod
    def generate_flavor_genome(user: UserProfile) -> Dict[str, float]:
        """
        Creates a 'Flavor Genome' vector based on liked/disliked ingredients.
        For this prototype, we map ingredients to flavor profiles manually or assume
        simple implementation where vector = map of {flavor_key: preference_weight}.
        """
        # Base vector
        flavor_genome = {
            "sweet": 0.5,
            "salty": 0.5,
            "sour": 0.5,
            "bitter": 0.1, # Disliked by default usually
            "umami": 0.6,
            "spicy": 0.5
        }
        
        # Heuristic adjustments
        # In a real app, we'd query FlavorDB to see what compounds are in liked ingredients.
        # Here we do simple word matching for prototype.
        for item in user.liked_ingredients:
            item = item.lower()
            if "berry" in item or "fruit" in item:
                flavor_genome["sweet"] += 0.2
            if "soy" in item or "meat" in item or "cheese" in item:
                flavor_genome["umami"] += 0.2
            if "chili" in item or "pepper" in item:
                flavor_genome["spicy"] += 0.3
                
        for item in user.disliked_ingredients:
            item = item.lower()
            if "chili" in item or "pepper" in item:
                flavor_genome["spicy"] -= 0.5
            if "kale" in item or "coffee" in item:
                flavor_genome["bitter"] -= 0.2
                
        # Clamp values 0 to 1
        for k in flavor_genome:
            flavor_genome[k] = max(0.0, min(1.0, flavor_genome[k]))
            
        return flavor_genome

    @staticmethod
    def predict_hedonic_score(recipe: Recipe, user_genome: Dict[str, float]) -> float:
        """
        Cosine similarity-ish score between user genome and recipe profile.
        """
        if not recipe.flavor_profile:
            return 0.5 # Neutral if no data
            
        dot_product = 0.0
        magnitude_user = 0.0
        magnitude_recipe = 0.0
        
        # We iterate over keys present in recipe to score match
        # (Assuming recipe profile is normalized 0-1)
        for flavor, val in recipe.flavor_profile.items():
            user_pref = user_genome.get(flavor, 0.5)
            dot_product += val * user_pref
            magnitude_recipe += val ** 2
            Magnitude_user_term = user_pref ** 2 # We should probably sum all user genome keys but simpler here
            
        # Simplified similarity: Just dot product weighted by existence
        # Real cosine sim requires full vectors
        
        # Let's do a simpler "Distance" metric
        # Score = 1 - average distance
        total_diff = 0
        count = 0
        for flavor, val in recipe.flavor_profile.items():
            user_pref = user_genome.get(flavor, 0.5)
            total_diff += abs(val - user_pref)
            count += 1
            
        if count == 0: return 0.5
        
        avg_diff = total_diff / count
        return 1.0 - avg_diff
