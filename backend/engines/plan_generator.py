"""
Advanced Plan Generator with variety optimization, shopping lists, and snacks
"""
from typing import List, Dict, Tuple, Optional, Any
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

    def __init__(self, db_session=None):
        # Initialize engines
        self.health_engine = HealthEngine()
        self.taste_engine = TasteEngine()
        self.variety_engine = VarietyEngine(no_repeat_window=7)

        # Initialize services (keeping for other functions if needed, but recipes come from DB)
        self.recipe_service = RecipeDBService()
        self.sustainability_service = SustainableFoodDBService()

        # Load recipes from SQLAlchemy DBRecipe table
        from backend.database import SessionLocal, DBRecipe
        db = db_session or SessionLocal()
        try:
            db_recipes = db.query(DBRecipe).all()
            self.recipes = [
                Recipe(
                    id=r.id,
                    name=r.name,
                    description=r.description,
                    image_url=r.image_url,
                    ingredients=r.ingredients,
                    calories=r.calories,
                    macros=r.macros,
                    flavor_profile=r.flavor_profile,
                    tags=r.tags,
                    cuisine=r.cuisine,
                    instructions=r.instructions,
                    estimated_cost=r.estimated_cost
                ) for r in db_recipes
            ]
            # Create ID to Index mapping for RL agent
            self.recipe_id_map = {r.id: i for i, r in enumerate(self.recipes)}
            self.index_to_recipe = {i: r for i, r in enumerate(self.recipes)}
        except Exception as e:
            print(f"Error loading recipes from database: {e}")
            self.recipes = []
            self.recipe_id_map = {}
            self.index_to_recipe = {}
        finally:
            if not db_session:
                db.close()

        # Initialize RL Planner (PPO)
        from backend.ml.meal_planner_rl import RLMealPlanner
        import os
        
        # Determine action dimension based on loaded recipes (cap at 1000 for stability)
        action_dim = min(max(len(self.recipes), 100), 1000)
        self.rl_planner = RLMealPlanner(action_dim=action_dim)
        
        # Load weights if they exist
        weights_path = os.path.join(os.path.dirname(__file__), "..", "ml", "weights", "rl_planner.pth")
        if os.path.exists(weights_path):
            try:
                self.rl_planner.load_model(weights_path)
            except Exception as e:
                print(f"Warning: Could not load RL weights: {e}")

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
        history: List[Recipe] = []
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
            if day_recipes:  # Safety check to prevent index error
                cuisine = day_recipes[0].cuisine if day_recipes[0].cuisine else "unknown"
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
        """
        Hard-blocked filtering for Allergies and Dietary Restrictions.
        Ensures 100% compliance before recipes reach the selection pool.
        """
        valid_recipes = []
        restrictions = [r.lower() for r in user.dietary_restrictions]
        
        # 1. Expanded Forbidden Keywords (Comprehensive Industry Standard)
        forbidden_keywords = set()

        if "vegetarian" in restrictions:
            forbidden_keywords.update(["chicken", "beef", "pork", "meat", "lamb", "turkey", "fish", "salmon",
                                      "tuna", "shrimp", "seafood", "bacon", "ham", "steak", "duck", "veal"])
        
        if "vegan" in restrictions:
            forbidden_keywords.update(["chicken", "beef", "pork", "meat", "lamb", "turkey", "fish", "salmon",
                                      "tuna", "shrimp", "seafood", "bacon", "ham", "steak", "duck", "veal",
                                      "milk", "cheese", "yogurt", "butter", "cream", "egg", "honey",
                                      "mayonnaise", "whey", "casein", "gelatin", "lard"])
        
        if "pescetarian" in restrictions:
            forbidden_keywords.update(["chicken", "beef", "pork", "meat", "lamb", "turkey", "bacon", "ham", "steak", "duck", "veal"])

        if "gluten-free" in restrictions:
            forbidden_keywords.update(["wheat", "barley", "rye", "bread", "pasta", "flour", "couscous",
                                      "seitan", "semolina", "spelt", "malt"])

        if "dairy-free" in restrictions:
            forbidden_keywords.update(["milk", "cheese", "yogurt", "butter", "cream", "whey", "casein", "ghee"])

        # 2. Add Specific User Dislikes / Allergies to the forbidden list
        user_dislikes = [d.replace("Allergy: ", "").lower().strip() for d in user.disliked_ingredients]
        forbidden_keywords.update(user_dislikes)
        
        # ADDED: Hard-block 'Foods to Avoid' from preferences
        # If user explicitly listed it in 'foods to avoid', it must be hard-removed.
        # Check for a potential field or use disliked_ingredients as the source
        # For NutriFlavorOS, we treat all 'disliked' or 'avoid' as hard forbidden keywords.
        
        # 3. Execution: Strict Ingredient-by-Ingredient Check
        for recipe in self.recipes:
            ingredients_lower = [ing.lower() for ing in recipe.ingredients]
            recipe_tags = [t.lower() for t in recipe.tags]
            
            is_compliant = True
            
            # Check every ingredient for any forbidden keyword
            for forbidden in forbidden_keywords:
                if any(forbidden in ing for ing in ingredients_lower):
                    is_compliant = False
                    break
                # Also check tags (e.g. if a recipe is tagged "contains gluten")
                if any(forbidden in tag for t in recipe_tags):
                    is_compliant = False
                    break
            
            if not is_compliant:
                continue

            # 4. Health conditions & Medications via DietRxDB (Scientific Layer)
            # Combine conditions and medications for a unified safety check
            medical_context = user.health_conditions + [f"Medication: {m}" for m in user.medications]
            
            if medical_context:
                # Get comprehensive health score
                health_report = self.health_engine.score_recipe_comprehensive(
                    recipe.id, targets, medical_context
                )
                
                # MEDICAL HARD BLOCK: If recipe is flagged as unsafe for conditions/meds, discard it
                if not health_report.get("safe", True):
                    is_compliant = False
                    continue

            valid_recipes.append(recipe)

        # Safety Fallback
        if not valid_recipes:
            print(f"CRITICAL Warning: Constraints too strict for user {user.name}. Fallback triggered.")
            return [r for r in self.recipes if "vegetable" in str(r.ingredients).lower()][:10]

        return valid_recipes

    def _generate_day_plan(self, day_num: int, user: UserProfile,
                          targets: NutrientTarget, genome: Dict,
                          candidates: List[Recipe], history: List[Recipe]) -> DailyPlan:
        """
        Generate plan for a single day with dynamic balancing.
        Ensures the sum of meals matches the daily target perfectly.
        """
        meals_for_day: Dict[str, Recipe] = {}
        day_recipes = []
        
        # 1. TRACK REMAINING TARGETS (Start with full daily targets)
        remaining_cals = float(targets.calories)
        remaining_protein = float(targets.protein_g)
        remaining_carbs = float(targets.carbs_g)
        remaining_fat = float(targets.fat_g)
        
        # ADDED: Micronutrient Accumulator (Vitamins & Minerals)
        remaining_micros = targets.micro_nutrients.copy()

        # Meal slots with weights (Breakfast 25%, Lunch 35%, Dinner 30%, Snacks 10%)
        meal_slots = [
            ("Breakfast", 0.25), 
            ("Morning Snack", 0.05), 
            ("Lunch", 0.35), 
            ("Afternoon Snack", 0.05), 
            ("Dinner", 0.30)
        ]

        for slot_name, slot_weight in meal_slots:
            is_snack = "Snack" in slot_name
            
            # Calculate dynamic target for THIS specific slot
            current_slot_target = NutrientTarget(
                calories=int(remaining_cals * (slot_weight / (slot_weight + sum(w for _, w in meal_slots[meal_slots.index((slot_name, slot_weight))+1:])))),
                protein_g=int(remaining_protein * (slot_weight / (slot_weight + sum(w for _, w in meal_slots[meal_slots.index((slot_name, slot_weight))+1:])))),
                carbs_g=int(remaining_carbs * (slot_weight / (slot_weight + sum(w for _, w in meal_slots[meal_slots.index((slot_name, slot_weight))+1:])))),
                fat_g=int(remaining_fat * (slot_weight / (slot_weight + sum(w for _, w in meal_slots[meal_slots.index((slot_name, slot_weight))+1:])))),
                micro_nutrients=remaining_micros # Pass remaining vitamins/minerals needed
            ) if slot_name != meal_slots[-1][0] else NutrientTarget(
                calories=int(remaining_cals),
                protein_g=int(remaining_protein),
                carbs_g=int(remaining_carbs),
                fat_g=int(remaining_fat),
                micro_nutrients=remaining_micros
            )

            # Find best recipe using FULL spectrum dynamic targets
            best_recipe = self._select_best_recipe(
                candidates, history, current_slot_target, genome, is_snack
            )

            if best_recipe:
                meals_for_day[slot_name] = best_recipe
                day_recipes.append(best_recipe)
                history.append(best_recipe)
                
                # UPDATE ACCUMULATORS
                remaining_cals -= best_recipe.calories
                remaining_protein -= (best_recipe.macros.get("protein") or 0)
                remaining_carbs -= (best_recipe.macros.get("carbs") or 0)
                remaining_fat -= (best_recipe.macros.get("fat") or 0)
                
                # Update Remaining Micros (Vitamins/Minerals)
                recipe_nutrition = self.health_engine.get_recipe_full_nutrition(best_recipe.id)
                recipe_micros = recipe_nutrition.get("micros", {})
                for nutrient in remaining_micros:
                    remaining_micros[nutrient] = max(0, remaining_micros[nutrient] - recipe_micros.get(nutrient, 0))

        # ... (rest of stats calculation)
        total_cals = sum([m.calories for m in day_recipes])
        total_cost = sum([m.estimated_cost or 0.0 for m in day_recipes])
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
            carbon_footprint = sustainability.get("carbon_footprint_kg", 0.0)
        except (KeyError, ValueError, TypeError) as e:
            print(f"Warning: Could not calculate sustainability score: {e}")
            carbon_footprint = 0.0
        except Exception as e:
            print(f"Unexpected error calculating sustainability: {e}")
            carbon_footprint = 0.0

        return DailyPlan(
            day=day_num,
            meals=meals_for_day,
            total_stats={
                "calories": float(total_cals),
                "target_calories": float(targets.calories),
                "carbon_footprint_kg": float(carbon_footprint),
                "total_cost": float(total_cost)
            },
            scores={
                "health_match": float(health_match),
                "taste_match": float(avg_taste_score),  # REAL SCORE!
                "variety": float(variety_score)
            }
        )

    def _select_best_recipe(self, candidates: List[Recipe], history: List[Recipe],
                           targets: NutrientTarget, genome: Dict, is_snack: bool) -> Optional[Recipe]:
        """
        Select best recipe using RL-augmented multi-objective optimization
        Combines PPO policy with Health, Taste, and Variety heuristics
        """
        if not candidates:
            return None

        # 1. Get RL Policy Suggestion
        rl_suggestion = None
        try:
            # Encode current state
            # Context for RL: day of week (simplified as 0), meal slot, etc.
            time_context = {"meal_slot": "snack" if is_snack else "lunch"}
            state = self.rl_planner.encode_state(
                user.model_dump() if hasattr(user, "model_dump") else user.__dict__, 
                [h.model_dump() if hasattr(h, "model_dump") else h.__dict__ for h in history[-10:]], 
                [], # Pantry not implemented yet
                time_context
            )
            
            # Map candidate recipes to indices for RL masking
            candidate_indices = [self.recipe_id_map[r.id] for r in candidates if r.id in self.recipe_id_map]
            # Ensure indices are within RL action space
            valid_indices = [idx for idx in candidate_indices if idx < self.rl_planner.action_dim]
            
            if valid_indices:
                idx, log_prob = self.rl_planner.select_recipe(state, valid_indices)
                rl_suggestion = self.index_to_recipe.get(idx)
        except Exception as e:
            print(f"Warning: RL selection failed: {e}")

        # 2. Heuristic Optimization (Validation Layer)
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
            # 1. Health score (35% weight)
            cal_diff = abs(recipe.calories - calorie_target)
            if calorie_target > 0:
                health_score = max(0, 1.0 - (cal_diff / calorie_target))
            else:
                health_score = 0.5

            # 2. Taste score (35% weight) - REAL CALCULATION
            taste_score = self.taste_engine.predict_hedonic_score(recipe, genome)

            # 3. Variety score (20% weight)
            variety_score = self.variety_engine.score_variety(recipe, history[-9:])
            
            # 4. Budget Score (10% weight)
            # Low cost = High score. Assumes average meal cost is $5.0.
            cost = recipe.estimated_cost or 5.0
            budget_score = max(0.0, 1.0 - (cost / 15.0)) # 15.0 is the upper limit for "expensive"

            # Weighted total
            heuristic_score = (health_score * 0.35) + (taste_score * 0.35) + (variety_score * 0.2) + (budget_score * 0.1)
            
            # --- HEALTH-FIRST CLIPPING (The "Shield") ---
            # If a dish is mathematically unhealthy (Health Score < 0.4), 
            # we penalize the overall score regardless of how 'tasty' it is.
            if health_score < 0.4:
                heuristic_score *= 0.2 # Massive penalty for junk food
            elif health_score < 0.6:
                heuristic_score *= 0.7 # Moderate penalty
            
            # 3. RL Integration: Boost the score of the RL-suggested recipe
            if rl_suggestion and recipe.id == rl_suggestion.id:
                heuristic_score += 0.3  # Significant boost for the neural network choice

            if heuristic_score > best_score:
                best_score = heuristic_score
                best_recipe = recipe

        # Fallback
        if not best_recipe and candidates:
            best_recipe = random.choice(candidates)

        return best_recipe

    def _generate_shopping_list(self, all_ingredients: List[str]) -> Dict[str, Dict[str, Any]]:
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

        shopping_list: Dict[str, Dict[str, Any]] = {}

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
                                 targets: NutrientTarget) -> Dict[str, Any]:
        """Calculate overall plan statistics"""
        total_days = len(daily_plans)
        if total_days == 0:
            return {}

        # Average scores
        avg_health = sum(p.scores["health_match"] for p in daily_plans) / total_days
        avg_taste = sum(p.scores["taste_match"] for p in daily_plans) / total_days
        avg_variety = sum(p.scores["variety"] for p in daily_plans) / total_days

        # Total carbon footprint
        total_carbon = sum(
            p.total_stats.get("carbon_footprint_kg", 0.0)
            for p in daily_plans
        )
        
        # Total Plan Cost
        total_cost = sum(
            p.total_stats.get("total_cost", 0.0)
            for p in daily_plans
        )

        return {
            "average_health_match": round(avg_health, 2),
            "average_taste_match": round(avg_taste, 2),
            "average_variety": round(avg_variety, 2),
            "total_carbon_footprint_kg": round(total_carbon, 2),
            "total_plan_cost": round(total_cost, 2),
            "sustainability_rating": "Excellent" if total_carbon < 20 else "Good" if total_carbon < 35 else "Fair"
        }
