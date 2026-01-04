import json
import os
from typing import List, Dict
import random

from backend.models import UserProfile, PlanResponse, DailyPlan, Recipe, NutrientTarget
from backend.engines.health_engine import HealthEngine
from backend.engines.taste_engine import TasteEngine
from backend.engines.variety_engine import VarietyEngine

class PlanGenerator:
    def __init__(self):
        # Load mock DB
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'mock_db.json')
        with open(self.db_path, 'r') as f:
            data = json.load(f)
            self.recipes = [Recipe(**item) for item in data]

    def create_plan(self, user: UserProfile, days: int = 3) -> PlanResponse:
        # 1. Calculate Targets
        targets = HealthEngine.calculate_targets(user)
        
        # 2. Get Flavor Genome
        genome = TasteEngine.generate_flavor_genome(user)
        
        daily_plans = []
        
        # Helper to filter recipes by dislikes
        valid_recipes = []
        for r in self.recipes:
            is_valid = True
            for dislike in user.disliked_ingredients:
                if any(dislike.lower() in ing.lower() for ing in r.ingredients):
                    is_valid = False
                    break
            if is_valid:
                valid_recipes.append(r)
        
        # If no valid recipes, fallback to all
        candidates = valid_recipes if valid_recipes else self.recipes
        
        # 3. Generate Day by Day
        history = []
        
        for day_num in range(1, days + 1):
            meals_for_day = {}
            day_recipes = []
            
            # Simple Breakfast/Lunch/Dinner slots
            for slot in ["Breakfast", "Lunch", "Dinner"]:
                # Scoring Loop
                best_score = -1.0
                best_recipe = None
                
                # Shuffle candidates to minimize determinism if scores are equal
                random.shuffle(candidates)
                
                for r in candidates:
                    # Skip if repeated recently
                    if VarietyEngine.check_repetition(r, history[-3:]): # Check last 3 meals
                        continue
                        
                    # Calculate sub-scores
                    # Note: Recipe calories in mock DB are total meal calories
                    health_score = HealthEngine.score_recipe({"calories": r.calories}, targets)
                    taste_score = TasteEngine.predict_hedonic_score(r, genome)
                    
                    # Weighted Utility
                    total_score = (health_score * 0.5) + (taste_score * 0.5)
                    
                    if total_score > best_score:
                        best_score = total_score
                        best_recipe = r
                
                if best_recipe:
                    meals_for_day[slot] = best_recipe
                    day_recipes.append(best_recipe)
                    history.append(best_recipe)
                else:
                    # Fallback if everything filtered out
                    fallback = random.choice(candidates)
                    meals_for_day[slot] = fallback
                    day_recipes.append(fallback)
                    history.append(fallback)

            # Calculate Day Totals
            total_cals = sum([m.calories for m in day_recipes])
            variety_val = VarietyEngine.calculate_variety_score(day_recipes)
            
            daily_plans.append(DailyPlan(
                day=day_num,
                meals=meals_for_day,
                total_stats={"calories": total_cals, "target_calories": targets.calories},
                scores={
                    "health_match": min(1.0, total_cals / targets.calories if total_cals < targets.calories else targets.calories/total_cals),
                    "taste_match": 0.8, # Placeholder average
                    "variety": variety_val
                }
            ))
            
        return PlanResponse(user_id="user_123", days=daily_plans)
