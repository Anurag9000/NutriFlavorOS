"""
Advanced Plan Generator with variety optimization, shopping lists, and snacks
"""
import json
import os
from typing import List, Dict, Set, Tuple
import random
from collections import Counter

from backend.models import UserProfile, PlanResponse, DailyPlan, Recipe, NutrientTarget
from backend.engines.health_engine import HealthEngine
from backend.engines.taste_engine import TasteEngine
from backend.engines.variety_engine import VarietyEngine
from backend.services.recipedb_service import RecipeDBService
from backend.services.sustainablefooddb_service import SustainableFoodDBService

class PlanGenerator:
    """
    Advanced meal plan generator with:
    - Variety weight in optimization (40% health, 40% taste, 20% variety)
    - Shopping list generation with quantities
    - Snack recommendations
    - Prep timeline calculation
    - Carbon footprint tracking
    """
    
    def __init__(self):
        # Initialize engines
        self.health_engine = HealthEngine()
        self.taste_engine = TasteEngine()
        self.variety_engine = VarietyEngine(no_repeat_window=7)
        
        # Initialize services
        self.recipe_service = RecipeDBService()
        self.sustainability_service = SustainableFoodDBService()
        
        # Load recipes via Service (supports both Mock and Live modes)
        # We fetch a broad set of recipes to initialize the generator
        # In production, this might be a more specific query or cached set
        try:
            self.recipes = [Recipe(**r) for r in self.recipe_service.search_by_title("")]
        except Exception as e:
            print(f"Error loading recipes from service: {e}")
            self.recipes = []
    
    def create_plan(self, user: UserProfile, days: int = 7) -> PlanResponse:
        """Generate comprehensive meal plan"""
        # 1. Calculate nutritional targets
        targets = self.health_engine.calculate_targets(user)
        
        # 2. Generate user's flavor genome
        genome = self.taste_engine.generate_flavor_genome(user)
        
        # 3. Filter valid recipes (exclude dislikes, check conditions)
        valid_recipes = self._filter_valid_recipes(user)
        
        # 4. Generate daily plans
        daily_plans = []
        history = []
        all_ingredients = []
        
        for day_num in range(1, days + 1):
            day_plan = self._generate_day_plan(
                day_num, user, targets, genome, valid_recipes, history
            )
            daily_plans.append(day_plan)
            
            # Update history
            for meal in day_plan.meals.values():
                history.append(meal)
                all_ingredients.extend(meal.ingredients)
            
            # Update variety engine history
            day_recipes = list(day_plan.meals.values())
            cuisine = day_recipes[0].cuisine if hasattr(day_recipes[0], 'cuisine') else "unknown"
            self.variety_engine.update_history(day_recipes, cuisine)
        
        # 5. Generate shopping list
        shopping_list = self._generate_shopping_list(all_ingredients)
        
        # 6. Calculate prep timeline
        prep_timeline = self._generate_prep_timeline(daily_plans)
        
        # 7. Calculate overall stats
        overall_stats = self._calculate_overall_stats(daily_plans, targets)
        
        return PlanResponse(
            user_id=user.name or "user",
            days=daily_plans,
            shopping_list=shopping_list,
            prep_timeline=prep_timeline,
            overall_stats=overall_stats
        )
    
    def _filter_valid_recipes(self, user: UserProfile) -> List[Recipe]:
        """Filter recipes based on user preferences and health conditions"""
        valid_recipes = []
        
        for recipe in self.recipes:
            # Check dislikes
            has_disliked = any(
                dislike.lower() in ing.lower() 
                for dislike in user.disliked_ingredients 
                for ing in recipe.ingredients
            )
            if has_disliked:
                continue
            
            # Check health conditions (if using DietRxDB)
            if hasattr(user, 'health_conditions') and user.health_conditions:
                # This would use DietRxDB to check safety
                # For now, we'll add it to valid list
                pass
            
            valid_recipes.append(recipe)
        
        return valid_recipes if valid_recipes else self.recipes
    
    def _generate_day_plan(self, day_num: int, user: UserProfile, 
                          targets: NutrientTarget, genome: Dict,
                          candidates: List[Recipe], history: List[Recipe]) -> DailyPlan:
        """Generate plan for a single day"""
        meals_for_day = {}
        day_recipes = []
        
        # Meal slots: Breakfast, Snack1, Lunch, Snack2, Dinner
        meal_slots = ["Breakfast", "Morning Snack", "Lunch", "Afternoon Snack", "Dinner"]
        
        for slot in meal_slots:
            is_snack = "Snack" in slot
            
            # Find best recipe for this slot
            best_recipe = self._select_best_recipe(
                candidates, history, targets, genome, is_snack
            )
            
            if best_recipe:
                meals_for_day[slot] = best_recipe
                day_recipes.append(best_recipe)
                history.append(best_recipe)
        
        # Calculate day statistics
        total_cals = sum([m.calories for m in day_recipes])
        variety_score = self.variety_engine.calculate_variety_score(day_recipes)
        
        # Calculate average taste score (REAL, not hardcoded!)
        taste_scores = [
            self.taste_engine.predict_hedonic_score(recipe, genome)
            for recipe in day_recipes
        ]
        avg_taste_score = sum(taste_scores) / len(taste_scores) if taste_scores else 0.5
        
        # Calculate health match
        if targets.calories > 0 and total_cals > 0:
            health_match = min(1.0, total_cals / targets.calories if total_cals < targets.calories 
                              else targets.calories / total_cals)
        else:
            health_match = 0.5
        
        # Calculate carbon footprint
        all_ingredients = []
        for recipe in day_recipes:
            all_ingredients.extend(recipe.ingredients)
        
        try:
            sustainability = self.sustainability_service.get_sustainability_score(all_ingredients)
            carbon_footprint = sustainability.get("carbon_footprint_kg", 0)
        except (KeyError, ValueError, TypeError) as e:
            print(f"Warning: Could not calculate sustainability score: {e}")
            carbon_footprint = 0
        except Exception as e:
            print(f"Unexpected error calculating sustainability: {e}")
            carbon_footprint = 0
        
        return DailyPlan(
            day=day_num,
            meals=meals_for_day,
            total_stats={
                "calories": total_cals,
                "target_calories": targets.calories,
                "carbon_footprint_kg": carbon_footprint
            },
            scores={
                "health_match": health_match,
                "taste_match": avg_taste_score,  # REAL SCORE!
                "variety": variety_score
            }
        )
    
    def _select_best_recipe(self, candidates: List[Recipe], history: List[Recipe],
                           targets: NutrientTarget, genome: Dict, is_snack: bool) -> Recipe:
        """
        Select best recipe using multi-objective optimization
        Weights: 40% health, 40% taste, 20% variety
        """
        best_score = -1.0
        best_recipe = None
        
        # Adjust calorie target for snacks (200-300 cal) vs meals (400-600 cal)
        calorie_target = 250 if is_snack else (targets.calories / 3)
        
        random.shuffle(candidates)
        
        for recipe in candidates:
            # Skip if too repetitive
            if self.variety_engine.check_repetition(recipe, history[-9:]):
                continue
            
            # Skip if wrong calorie range for slot
            if is_snack and recipe.calories > 400:
                continue
            if not is_snack and recipe.calories < 300:
                continue
            
            # Calculate component scores
            # 1. Health score (40% weight)
            cal_diff = abs(recipe.calories - calorie_target)
            if calorie_target > 0:
                health_score = max(0, 1.0 - (cal_diff / calorie_target))
            else:
                health_score = 0.5
            
            # 2. Taste score (40% weight) - REAL CALCULATION
            taste_score = self.taste_engine.predict_hedonic_score(recipe, genome)
            
            # 3. Variety score (20% weight)
            variety_score = self.variety_engine.score_variety(recipe, history[-9:])
            
            # Weighted total
            total_score = (health_score * 0.4) + (taste_score * 0.4) + (variety_score * 0.2)
            
            if total_score > best_score:
                best_score = total_score
                best_recipe = recipe
        
        # Fallback
        if not best_recipe and candidates:
            best_recipe = random.choice(candidates)
        elif not best_recipe:
            # No candidates available at all
            print("Warning: No valid recipes available for selection")
            return None
        
        return best_recipe
    
    def _generate_shopping_list(self, all_ingredients: List[str]) -> Dict[str, Dict]:
        """
        Generate shopping list with quantities
        Groups by category and estimates quantities
        """
        # Count ingredient occurrences
        ingredient_counts = Counter(all_ingredients)
        
        # Categorize ingredients
        categories = {
            "Produce": ["tomato", "lettuce", "onion", "garlic", "pepper", "carrot", "spinach", "kale"],
            "Proteins": ["chicken", "beef", "pork", "fish", "salmon", "tofu", "eggs"],
            "Dairy": ["milk", "cheese", "yogurt", "butter", "cream"],
            "Grains": ["rice", "pasta", "bread", "quinoa", "oats"],
            "Pantry": ["oil", "salt", "pepper", "spices", "sauce", "vinegar"]
        }
        
        shopping_list = {}
        
        for ingredient, count in ingredient_counts.items():
            # Determine category
            category = "Other"
            for cat, keywords in categories.items():
                if any(keyword in ingredient.lower() for keyword in keywords):
                    category = cat
                    break
            
            # Estimate quantity (simplified)
            if category == "Produce":
                quantity = f"{count} units"
            elif category == "Proteins":
                quantity = f"{count * 200}g"  # ~200g per serving
            elif category == "Dairy":
                quantity = f"{count * 100}ml"
            else:
                quantity = f"{count} servings"
            
            if category not in shopping_list:
                shopping_list[category] = {}
            
            shopping_list[category][ingredient] = {
                "quantity": quantity,
                "count": count
            }
        
        return shopping_list
    
    def _generate_prep_timeline(self, daily_plans: List[DailyPlan]) -> Dict[int, List[str]]:
        """
        Generate meal prep timeline
        Returns: {day_number: [prep_tasks]}
        """
        timeline = {}
        
        for plan in daily_plans:
            day_tasks = []
            
            # Morning prep
            if "Breakfast" in plan.meals:
                day_tasks.append(f"8:00 AM - Prepare {plan.meals['Breakfast'].name}")
            
            # Lunch prep
            if "Lunch" in plan.meals:
                day_tasks.append(f"12:00 PM - Prepare {plan.meals['Lunch'].name}")
            
            # Dinner prep
            if "Dinner" in plan.meals:
                day_tasks.append(f"6:00 PM - Prepare {plan.meals['Dinner'].name}")
            
            timeline[plan.day] = day_tasks
        
        return timeline
    
    def _calculate_overall_stats(self, daily_plans: List[DailyPlan], 
                                 targets: NutrientTarget) -> Dict:
        """Calculate overall plan statistics"""
        total_days = len(daily_plans)
        
        # Average scores
        avg_health = sum(p.scores["health_match"] for p in daily_plans) / total_days
        avg_taste = sum(p.scores["taste_match"] for p in daily_plans) / total_days
        avg_variety = sum(p.scores["variety"] for p in daily_plans) / total_days
        
        # Total carbon footprint
        total_carbon = sum(
            p.total_stats.get("carbon_footprint_kg", 0) 
            for p in daily_plans
        )
        
        return {
            "average_health_match": round(avg_health, 2),
            "average_taste_match": round(avg_taste, 2),
            "average_variety": round(avg_variety, 2),
            "total_carbon_footprint_kg": round(total_carbon, 2),
            "sustainability_rating": "Excellent" if total_carbon < 20 else "Good" if total_carbon < 35 else "Fair"
        }
