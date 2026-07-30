"""Deterministic, safety-first meal-plan generation.

The previous implementation mixed hard constraints with unvalidated medical
lookups, silently fell back to potentially unsafe recipes, and attempted to use
an untrained RL policy. This module now fails explicitly when no compliant plan
can be produced and keeps experimental models opt-in.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.engines.health_engine import HealthEngine
from backend.engines.taste_engine import TasteEngine
from backend.engines.variety_engine import VarietyEngine
from backend.models import DailyPlan, NutrientTarget, PlanResponse, Recipe, UserProfile
from backend.services.sustainablefooddb_service import SustainableFoodDBService


class InfeasiblePlanError(ValueError):
    """Raised when hard user constraints leave no safe recipe set."""


class PlanGenerator:
    """Generate a meal plan from validated recipes and explicit constraints."""

    MEAL_SLOTS: Tuple[Tuple[str, float], ...] = (
        ("Breakfast", 0.25),
        ("Morning Snack", 0.05),
        ("Lunch", 0.35),
        ("Afternoon Snack", 0.05),
        ("Dinner", 0.30),
    )

    RESTRICTION_TERMS: Dict[str, Sequence[str]] = {
        "vegetarian": (
            "chicken", "beef", "pork", "lamb", "turkey", "fish", "salmon",
            "tuna", "shrimp", "prawn", "seafood", "bacon", "ham", "steak",
            "duck", "veal", "gelatin", "lard",
        ),
        "vegan": (
            "chicken", "beef", "pork", "lamb", "turkey", "fish", "salmon",
            "tuna", "shrimp", "prawn", "seafood", "bacon", "ham", "steak",
            "duck", "veal", "milk", "cheese", "yogurt", "butter", "cream",
            "egg", "honey", "mayonnaise", "whey", "casein", "gelatin", "lard",
            "ghee",
        ),
        "pescetarian": (
            "chicken", "beef", "pork", "lamb", "turkey", "bacon", "ham",
            "steak", "duck", "veal", "gelatin", "lard",
        ),
        "gluten-free": (
            "wheat", "barley", "rye", "bread", "pasta", "flour", "couscous",
            "seitan", "semolina", "spelt", "malt",
        ),
        "dairy-free": (
            "milk", "cheese", "yogurt", "butter", "cream", "whey", "casein",
            "ghee",
        ),
    }

    CATEGORY_TERMS: Dict[str, Sequence[str]] = {
        "Produce": ("tomato", "lettuce", "onion", "garlic", "pepper", "carrot", "spinach", "kale", "fruit", "vegetable"),
        "Proteins": ("chicken", "beef", "pork", "fish", "salmon", "tofu", "egg", "lentil", "bean"),
        "Dairy": ("milk", "cheese", "yogurt", "butter", "cream", "ghee"),
        "Grains": ("rice", "pasta", "bread", "quinoa", "oat", "wheat", "barley"),
        "Pantry": ("oil", "salt", "spice", "sauce", "vinegar", "flour", "sugar"),
    }

    def __init__(self, db_session=None):
        self.health_engine = HealthEngine()
        self.taste_engine = TasteEngine()
        self.sustainability_service = SustainableFoodDBService()
        self.recipes = self._load_recipes(db_session)
        self.recipe_id_map = {recipe.id: index for index, recipe in enumerate(self.recipes)}
        self.index_to_recipe = {index: recipe for index, recipe in enumerate(self.recipes)}

        self.rl_planner = None
        self.experimental_rl_enabled = os.getenv("ENABLE_EXPERIMENTAL_RL", "false").lower() == "true"
        if self.experimental_rl_enabled:
            self._initialize_experimental_rl()

    def _load_recipes(self, db_session=None) -> List[Recipe]:
        from backend.database import DBRecipe, SessionLocal

        db = db_session or SessionLocal()
        try:
            rows = db.query(DBRecipe).all()
            recipes: List[Recipe] = []
            for row in rows:
                try:
                    recipes.append(
                        Recipe(
                            id=row.id,
                            name=row.name or "Unnamed recipe",
                            description=row.description or "",
                            image_url=row.image_url,
                            ingredients=list(row.ingredients or []),
                            calories=max(0, int(row.calories or 0)),
                            macros=dict(row.macros or {}),
                            flavor_profile=dict(row.flavor_profile or {}),
                            tags=list(row.tags or []),
                            cuisine=row.cuisine,
                            instructions=list(row.instructions or []),
                            estimated_cost=max(0.0, float(row.estimated_cost or 0.0)),
                        )
                    )
                except (TypeError, ValueError) as exc:
                    print(f"Skipping invalid recipe row {getattr(row, 'id', '<unknown>')}: {exc}")
            return recipes
        finally:
            if db_session is None:
                db.close()

    def _initialize_experimental_rl(self) -> None:
        """Load RL only when explicitly enabled and a checkpoint is available."""

        weights_path = Path(__file__).resolve().parent.parent / "ml" / "weights" / "rl_planner.pth"
        if not weights_path.is_file():
            print("Experimental RL requested but no checkpoint exists; using deterministic ranking")
            self.experimental_rl_enabled = False
            return

        try:
            from backend.ml.meal_planner_rl import RLMealPlanner

            action_dim = min(max(len(self.recipes), 1), 1000)
            planner = RLMealPlanner(action_dim=action_dim)
            planner.load_model(str(weights_path))
            self.rl_planner = planner
        except Exception as exc:
            print(f"Could not load experimental RL planner: {exc}")
            self.experimental_rl_enabled = False
            self.rl_planner = None

    def create_plan(
        self,
        user: UserProfile,
        days: int = 7,
        user_id: Optional[str] = None,
    ) -> PlanResponse:
        if not 1 <= days <= 31:
            raise ValueError("days must be between 1 and 31")
        if not self.recipes:
            raise InfeasiblePlanError("No valid recipes are available in the recipe database")

        targets = self.health_engine.calculate_targets(user)
        genome = self.taste_engine.generate_flavor_genome(user)
        candidates = self._filter_valid_recipes(user)
        variety_engine = VarietyEngine(no_repeat_window=7)

        warnings = [
            "Environmental values are estimates unless a quantity-aware, sourced dataset is configured.",
            "Micronutrient targets are reported but not optimized until quantity-normalized nutrient data is available.",
        ]
        if user.health_conditions or user.medications:
            warnings.append(
                "This plan is not clinically validated for medical conditions or medications; review it with a qualified clinician."
            )
        if self.experimental_rl_enabled:
            warnings.append("An experimental RL ranker influenced recipe ordering.")

        daily_plans: List[DailyPlan] = []
        history: List[Recipe] = []
        all_ingredients: List[str] = []

        for day_num in range(1, days + 1):
            day_plan = self._generate_day_plan(
                day_num=day_num,
                user=user,
                targets=targets,
                genome=genome,
                candidates=candidates,
                history=history,
                variety_engine=variety_engine,
            )
            daily_plans.append(day_plan)
            day_recipes = list(day_plan.meals.values())
            all_ingredients.extend(
                ingredient for recipe in day_recipes for ingredient in recipe.ingredients
            )
            cuisine = next((recipe.cuisine for recipe in day_recipes if recipe.cuisine), "unknown")
            variety_engine.update_history(day_recipes, cuisine)

        return PlanResponse(
            user_id=user_id or "anonymous",
            days=daily_plans,
            shopping_list=self._generate_shopping_list(all_ingredients),
            prep_timeline=self._generate_prep_timeline(daily_plans),
            overall_stats=self._calculate_overall_stats(daily_plans, targets),
            warnings=warnings,
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    @classmethod
    def _contains_term(cls, text: str, term: str) -> bool:
        haystack = cls._normalize_text(text)
        needle = cls._normalize_text(term)
        if not haystack or not needle:
            return False
        escaped = re.escape(needle)
        plural_suffix = "" if needle.endswith("s") else "s?"
        return re.search(rf"(?:^|\s){escaped}{plural_suffix}(?:$|\s)", haystack) is not None

    def _filter_valid_recipes(self, user: UserProfile) -> List[Recipe]:
        restrictions = {self._normalize_text(item) for item in user.dietary_restrictions}
        forbidden_terms = {
            term
            for restriction, terms in self.RESTRICTION_TERMS.items()
            if restriction in restrictions
            for term in terms
        }
        forbidden_terms.update(item for item in user.allergies if item.strip())
        forbidden_terms.update(item for item in user.disliked_ingredients if item.strip())

        valid: List[Recipe] = []
        for recipe in self.recipes:
            if not recipe.ingredients or recipe.calories <= 0:
                continue
            searchable_values = [*recipe.ingredients, *recipe.tags, recipe.name]
            if any(
                self._contains_term(value, term)
                for term in forbidden_terms
                for value in searchable_values
            ):
                continue
            valid.append(recipe)

        if not valid:
            constraints = sorted({term for term in forbidden_terms if term})
            detail = ", ".join(constraints[:12]) or "the selected dietary constraints"
            raise InfeasiblePlanError(
                f"No recipes satisfy {detail}. Add compliant recipes or relax a non-safety preference."
            )
        return valid

    def _generate_day_plan(
        self,
        day_num: int,
        user: UserProfile,
        targets: NutrientTarget,
        genome: Dict[str, Any],
        candidates: List[Recipe],
        history: List[Recipe],
        variety_engine: VarietyEngine,
    ) -> DailyPlan:
        meals_for_day: Dict[str, Recipe] = {}
        day_recipes: List[Recipe] = []
        remaining = {
            "calories": float(targets.calories),
            "protein": float(targets.protein_g),
            "carbs": float(targets.carbs_g),
            "fat": float(targets.fat_g),
        }

        for index, (slot_name, slot_weight) in enumerate(self.MEAL_SLOTS):
            remaining_weight = sum(weight for _, weight in self.MEAL_SLOTS[index:])
            fraction = slot_weight / remaining_weight if remaining_weight > 0 else 1.0
            slot_target = NutrientTarget(
                calories=max(1, round(max(0.0, remaining["calories"]) * fraction)),
                protein_g=max(0, round(max(0.0, remaining["protein"]) * fraction)),
                carbs_g=max(0, round(max(0.0, remaining["carbs"]) * fraction)),
                fat_g=max(0, round(max(0.0, remaining["fat"]) * fraction)),
                micro_nutrients=dict(targets.micro_nutrients),
            )

            best_recipe = self._select_best_recipe(
                candidates=candidates,
                history=history,
                targets=slot_target,
                genome=genome,
                is_snack="Snack" in slot_name,
                user=user,
                variety_engine=variety_engine,
            )
            if best_recipe is None:
                raise InfeasiblePlanError(f"No suitable recipe could be selected for {slot_name}")

            meals_for_day[slot_name] = best_recipe
            day_recipes.append(best_recipe)
            history.append(best_recipe)
            remaining["calories"] -= best_recipe.calories
            remaining["protein"] -= float(best_recipe.macros.get("protein", 0) or 0)
            remaining["carbs"] -= float(best_recipe.macros.get("carbs", 0) or 0)
            remaining["fat"] -= float(best_recipe.macros.get("fat", 0) or 0)

        total_cals = sum(recipe.calories for recipe in day_recipes)
        total_protein = sum(float(recipe.macros.get("protein", 0) or 0) for recipe in day_recipes)
        total_carbs = sum(float(recipe.macros.get("carbs", 0) or 0) for recipe in day_recipes)
        total_fat = sum(float(recipe.macros.get("fat", 0) or 0) for recipe in day_recipes)
        total_cost = sum(float(recipe.estimated_cost or 0.0) for recipe in day_recipes)

        taste_scores = [self.taste_engine.predict_hedonic_score(recipe, genome) for recipe in day_recipes]
        average_taste = sum(taste_scores) / len(taste_scores) if taste_scores else 0.0
        health_match = self._macro_match_score(
            calories=total_cals,
            protein=total_protein,
            carbs=total_carbs,
            fat=total_fat,
            targets=targets,
        )

        carbon_footprint: Optional[float] = None
        carbon_status = "disabled"
        if os.getenv("ENABLE_SUSTAINABILITY_ESTIMATES", "false").lower() == "true":
            ingredients = [ingredient for recipe in day_recipes for ingredient in recipe.ingredients]
            try:
                result = self.sustainability_service.get_sustainability_score(ingredients)
                carbon_footprint = float(result["carbon_footprint_kg"])
                carbon_status = "unverified_estimate"
            except Exception:
                carbon_status = "unavailable"

        return DailyPlan(
            day=day_num,
            meals=meals_for_day,
            total_stats={
                "calories": float(total_cals),
                "protein_g": round(total_protein, 2),
                "carbs_g": round(total_carbs, 2),
                "fat_g": round(total_fat, 2),
                "target_calories": float(targets.calories),
                "carbon_footprint_kg": carbon_footprint,
                "carbon_data_status": carbon_status,
                "total_cost": round(total_cost, 2),
            },
            scores={
                "health_match": float(health_match),
                "taste_match": float(average_taste),
                "variety": float(variety_engine.calculate_variety_score(day_recipes)),
            },
        )

    @staticmethod
    def _closeness(actual: float, target: float) -> float:
        if target <= 0:
            return 1.0 if actual <= 0 else 0.0
        return max(0.0, 1.0 - abs(actual - target) / target)

    def _macro_match_score(
        self,
        *,
        calories: float,
        protein: float,
        carbs: float,
        fat: float,
        targets: NutrientTarget,
    ) -> float:
        return (
            self._closeness(calories, targets.calories) * 0.40
            + self._closeness(protein, targets.protein_g) * 0.25
            + self._closeness(carbs, targets.carbs_g) * 0.20
            + self._closeness(fat, targets.fat_g) * 0.15
        )

    def _select_best_recipe(
        self,
        candidates: List[Recipe],
        history: List[Recipe],
        targets: NutrientTarget,
        genome: Dict[str, Any],
        is_snack: bool,
        user: UserProfile,
        variety_engine: VarietyEngine,
    ) -> Optional[Recipe]:
        slot_candidates = [
            recipe
            for recipe in candidates
            if (recipe.calories <= 450 if is_snack else recipe.calories >= 150)
        ]
        if not slot_candidates:
            return None

        non_repetitive = [
            recipe
            for recipe in slot_candidates
            if not variety_engine.check_repetition(recipe, history[-9:])
        ]
        ranking_pool = non_repetitive or slot_candidates
        rl_suggestion = self._get_rl_suggestion(user, history, ranking_pool, is_snack)

        scored: List[Tuple[float, str, Recipe]] = []
        for recipe in ranking_pool:
            health_score = self._macro_match_score(
                calories=recipe.calories,
                protein=float(recipe.macros.get("protein", 0) or 0),
                carbs=float(recipe.macros.get("carbs", 0) or 0),
                fat=float(recipe.macros.get("fat", 0) or 0),
                targets=targets,
            )
            taste_score = float(self.taste_engine.predict_hedonic_score(recipe, genome))
            variety_score = float(variety_engine.score_variety(recipe, history[-9:]))
            cost = float(recipe.estimated_cost or 0.0)
            budget_score = max(0.0, 1.0 - cost / 15.0)

            score = health_score * 0.45 + taste_score * 0.30 + variety_score * 0.20 + budget_score * 0.05
            if health_score < 0.4:
                score *= 0.25
            if rl_suggestion is not None and recipe.id == rl_suggestion.id:
                score += 0.05
            scored.append((score, recipe.id, recipe))

        return max(scored, key=lambda item: (item[0], item[1]))[2] if scored else None

    def _get_rl_suggestion(
        self,
        user: UserProfile,
        history: List[Recipe],
        candidates: List[Recipe],
        is_snack: bool,
    ) -> Optional[Recipe]:
        if not self.experimental_rl_enabled or self.rl_planner is None:
            return None
        try:
            state = self.rl_planner.encode_state(
                user.model_dump(),
                [recipe.model_dump() for recipe in history[-10:]],
                [],
                {"meal_slot": "snack" if is_snack else "meal"},
            )
            valid_indices = [
                self.recipe_id_map[recipe.id]
                for recipe in candidates
                if recipe.id in self.recipe_id_map
                and self.recipe_id_map[recipe.id] < self.rl_planner.action_dim
            ]
            if not valid_indices:
                return None
            index, _ = self.rl_planner.select_recipe(state, valid_indices)
            return self.index_to_recipe.get(index)
        except Exception as exc:
            print(f"Experimental RL ranking failed; deterministic ranking used: {exc}")
            return None

    def _generate_shopping_list(self, ingredients: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        counts = Counter(item.strip() for item in ingredients if item and item.strip())
        shopping_list: Dict[str, Dict[str, Any]] = {}
        for ingredient, count in sorted(counts.items(), key=lambda item: item[0].lower()):
            category = "Other"
            for candidate_category, terms in self.CATEGORY_TERMS.items():
                if any(self._contains_term(ingredient, term) for term in terms):
                    category = candidate_category
                    break
            shopping_list.setdefault(category, {})[ingredient] = {
                "count": count,
                "quantity": f"{count} recipe occurrence{'s' if count != 1 else ''}",
                "quantity_status": "not_portion_normalized",
            }
        return shopping_list

    @staticmethod
    def _generate_prep_timeline(daily_plans: List[DailyPlan]) -> Dict[int, List[str]]:
        times = {"Breakfast": "8:00 AM", "Lunch": "12:00 PM", "Dinner": "6:00 PM"}
        return {
            plan.day: [
                f"{times[slot]} - Prepare {plan.meals[slot].name}"
                for slot in times
                if slot in plan.meals
            ]
            for plan in daily_plans
        }

    @staticmethod
    def _calculate_overall_stats(
        daily_plans: List[DailyPlan], targets: NutrientTarget
    ) -> Dict[str, Any]:
        if not daily_plans:
            return {}

        count = len(daily_plans)
        carbon_values = [
            float(plan.total_stats["carbon_footprint_kg"])
            for plan in daily_plans
            if isinstance(plan.total_stats.get("carbon_footprint_kg"), (int, float))
        ]
        total_carbon = round(sum(carbon_values), 2) if carbon_values else None

        return {
            "average_health_match": round(sum(plan.scores["health_match"] for plan in daily_plans) / count, 3),
            "average_taste_match": round(sum(plan.scores["taste_match"] for plan in daily_plans) / count, 3),
            "average_variety": round(sum(plan.scores["variety"] for plan in daily_plans) / count, 3),
            "average_calories": round(sum(float(plan.total_stats["calories"]) for plan in daily_plans) / count, 1),
            "target_calories": targets.calories,
            "total_carbon_footprint_kg": total_carbon,
            "carbon_data_status": "unverified_estimate" if carbon_values else "unavailable",
            "total_plan_cost": round(sum(float(plan.total_stats.get("total_cost", 0.0)) for plan in daily_plans), 2),
        }
