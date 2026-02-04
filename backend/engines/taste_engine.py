"""
Taste Engine - Molecular flavor analysis and hedonic prediction
"""
from typing import Dict, List
from backend.models import UserProfile, Recipe
from backend.services.flavordb_service import FlavorDBService
import numpy as np

class TasteEngine:
    """
    Advanced Taste Engine with:
    - Molecular flavor fingerprinting
    - Chemical compound analysis
    - Scientific flavor pairing
    - Real hedonic score prediction (NO HARDCODING!)
    """
    
    def __init__(self):
        self.flavor_service = FlavorDBService()
        self._ingredient_cache = {}
    
    def generate_flavor_genome(self, user: UserProfile) -> Dict[str, float]:
        """
        Creates a 'Flavor Genome' vector using REAL molecular flavor data from FlavorDB
        Returns: Comprehensive flavor profile with chemical compound preferences
        """
        flavor_genome = {}
        
        # Build genome from liked ingredients
        for ingredient in user.liked_ingredients:
            try:
                # Get real flavor profile from FlavorDB
                profile = self.flavor_service.get_flavor_profile(ingredient)
                flavor_vector = profile.get("flavor_vector", {})
                
                # Get functional groups (chemical fingerprint)
                functional_groups = self.flavor_service.get_functional_groups(ingredient)
                
                # Get aroma intensity
                aroma_threshold = self.flavor_service.get_aroma_threshold(ingredient)
                
                # Merge into genome with positive weight
                for compound, intensity in flavor_vector.items():
                    if compound not in flavor_genome:
                        flavor_genome[compound] = 0.0
                    # Weight by aroma threshold (lower threshold = stronger preference)
                    weight = 1.0 / (aroma_threshold + 0.1)
                    flavor_genome[compound] += intensity * weight
                
                # Add functional group preferences
                for group in functional_groups:
                    group_key = f"functional_{group}"
                    if group_key not in flavor_genome:
                        flavor_genome[group_key] = 0.0
                    flavor_genome[group_key] += 1.0
                    
            except (KeyError, ValueError, TypeError) as e:
                print(f"Warning: Could not fetch flavor data for {ingredient}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected error fetching flavor data for {ingredient}: {e}")
                continue
        
        # Subtract disliked ingredients
        for ingredient in user.disliked_ingredients:
            try:
                profile = self.flavor_service.get_flavor_profile(ingredient)
                flavor_vector = profile.get("flavor_vector", {})
                
                for compound, intensity in flavor_vector.items():
                    if compound not in flavor_genome:
                        flavor_genome[compound] = 0.0
                    flavor_genome[compound] -= intensity * 0.5  # Negative weight
                    
            except (KeyError, ValueError, TypeError) as e:
                print(f"Warning: Could not fetch disliked ingredient data for {ingredient}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected error processing disliked ingredient {ingredient}: {e}")
                continue
        
        # Normalize genome values to 0-1 range
        if flavor_genome:
            max_val = max(abs(v) for v in flavor_genome.values())
            if max_val > 0:
                flavor_genome = {k: max(0, min(1, (v / max_val + 1) / 2)) 
                                for k, v in flavor_genome.items()}
        
        return flavor_genome
    
    def get_recipe_flavor_profile(self, recipe: Recipe) -> Dict[str, float]:
        """
        Build comprehensive flavor profile for a recipe using FlavorDB
        """
        recipe_profile = {}
        
        for ingredient in recipe.ingredients:
            try:
                # Get molecular flavor data
                profile = self.flavor_service.get_flavor_profile(ingredient)
                flavor_vector = profile.get("flavor_vector", {})
                
                # Get aroma intensity for weighting
                aroma_threshold = self.flavor_service.get_aroma_threshold(ingredient)
                weight = 1.0 / (aroma_threshold + 0.1)
                
                # Merge into recipe profile
                for compound, intensity in flavor_vector.items():
                    if compound not in recipe_profile:
                        recipe_profile[compound] = 0.0
                    recipe_profile[compound] += intensity * weight
                    
            except (KeyError, ValueError, TypeError) as e:
                print(f"Warning: Could not fetch flavor profile for ingredient {ingredient}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected error processing ingredient {ingredient}: {e}")
                continue
        
        # Normalize
        if recipe_profile:
            total = sum(recipe_profile.values())
            if total > 0:
                recipe_profile = {k: v / total for k, v in recipe_profile.items()}
        
        return recipe_profile
    
    def predict_hedonic_score(self, recipe: Recipe, user_genome: Dict[str, float]) -> float:
        """
        Predict hedonic (pleasure) score using REAL molecular similarity
        NO HARDCODING - uses actual FlavorDB data
        Returns: Score 0.0-1.0
        """
        if not user_genome:
            return 0.5
        
        # Get recipe's molecular flavor profile
        recipe_profile = self.get_recipe_flavor_profile(recipe)
        
        if not recipe_profile:
            return 0.5
        
        # Calculate cosine similarity between user genome and recipe profile
        similarity = self._calculate_cosine_similarity(user_genome, recipe_profile)
        
        # Adjust for aroma intensity (stronger aromas = more impact on hedonic score)
        aroma_boost = 0.0
        for ingredient in recipe.ingredients:
            try:
                threshold = self.flavor_service.get_aroma_threshold(ingredient)
                # Lower threshold = stronger aroma = higher boost
                if threshold < 1.0:
                    aroma_boost += (1.0 - threshold) * 0.1
            except (KeyError, ValueError, TypeError) as e:
                print(f"Warning: Could not get aroma threshold for {ingredient}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected error processing aroma for {ingredient}: {e}")
                continue
        
        # Final hedonic score
        hedonic_score = similarity + min(0.2, aroma_boost)
        hedonic_score = max(0.0, min(1.0, hedonic_score))
        
        return hedonic_score
    
    def analyze_flavor_pairing(self, ing1: str, ing2: str) -> Dict[str, any]:
        """
        Analyze molecular compatibility between two ingredients
        Uses FlavorDB synthesis endpoint
        """
        try:
            pairing_data = self.flavor_service.synthesize_flavor_pairing(ing1, ing2)
            similarity = self.flavor_service.calculate_flavor_similarity(ing1, ing2)
            
            return {
                "compatible": similarity > 0.6,
                "similarity_score": similarity,
                "pairing_data": pairing_data,
                "recommendation": "Excellent" if similarity > 0.8 else 
                                "Good" if similarity > 0.6 else
                                "Fair" if similarity > 0.4 else "Poor"
            }
        except Exception as e:
            return {
                "compatible": False,
                "similarity_score": 0.0,
                "error": str(e)
            }
    
    def _calculate_cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """
        Calculate cosine similarity between two flavor vectors
        """
        # Get all unique compounds
        all_compounds = set(vec1.keys()) | set(vec2.keys())
        
        if not all_compounds:
            return 0.0
        
        # Build vectors
        v1 = np.array([vec1.get(c, 0.0) for c in all_compounds])
        v2 = np.array([vec2.get(c, 0.0) for c in all_compounds])
        
        # Calculate cosine similarity
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
