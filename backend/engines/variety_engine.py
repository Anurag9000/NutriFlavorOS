from typing import List
from backend.models import Recipe, DailyPlan

class VarietyEngine:
    @staticmethod
    def calculate_variety_score(plan: List[Recipe]) -> float:
        """
        Calculate entropy/variety based on ingredients in the selected recipes.
        """
        if not plan:
            return 0.0
            
        all_ingredients = []
        for r in plan:
            all_ingredients.extend(r.ingredients)
            
        # Check for duplicates
        unique_ingredients = set(all_ingredients)
        total_ingredients = len(all_ingredients)
        
        if total_ingredients == 0:
            return 1.0
            
        # Ratio of unique to total (Higher is better variety)
        # If we have [chicken, rice] and [chicken, broccoli], total=4, unique=3. Score=0.75
        score = len(unique_ingredients) / total_ingredients
        
        return score
    
    @staticmethod
    def check_repetition(candidate: Recipe, history: List[Recipe]) -> bool:
        """
        Returns True if candidate is too similar to history (e.g. same main protein).
        """
        # Simple name check
        for old in history:
            if candidate.id == old.id:
                return True
            # Very naive main ingredient check
            main_ing_cand = candidate.ingredients[0] if candidate.ingredients else ""
            main_ing_old = old.ingredients[0] if old.ingredients else ""
            if main_ing_cand == main_ing_old:
                return True # Too repetitive
                
        return False
