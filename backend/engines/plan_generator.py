"""Safety-first, quantity-aware meal-plan generation."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.domain.ingredients import (
    canonicalize_ingredient_name,
    parse_ingredient_line,
    parse_ingredient_lines,
    scale_quantity_range,
)
from backend.engines.health_engine import HealthEngine
from backend.engines.taste_engine import TasteEngine
from backend.engines.variety_engine import VarietyEngine
from backend.engines.weekly_optimizer import OptimizationInfeasible, PlanSelection, WeeklyPlanOptimizer
from backend.models import (
    DailyPlan,
    IngredientLine,
    NutrientTarget,
    PlanResponse,
    Recipe,
    UserProfile,
)
from backend.services.sustainablefooddb_service import SustainableFoodDBService


class InfeasiblePlanError(ValueError):
    """Raised when hard constraints or the horizon optimizer cannot form a plan."""

    def __init__(self, message: str, diagnostics: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}

    def to_detail(self) -> Dict[str, Any]:
        return {
            "code": "meal_plan_infeasible",
            "message": str(self),
            "diagnostics": self.diagnostics,
        }


class PlanGenerator:
    """Generate a complete plan from validated recipes and explicit constraints."""

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
        "Produce": (
            "tomato", "lettuce", "onion", "garlic", "pepper", "carrot", "spinach",
            "kale", "fruit", "vegetable", "apple", "banana", "lemon", "lime",
        ),
        "Proteins": (
            "chicken", "beef", "pork", "fish", "salmon", "tofu", "egg", "lentil",
            "bean", "chickpea", "tempeh",
        ),
        "Dairy": ("milk", "cheese", "yogurt", "butter", "cream", "ghee"),
        "Grains": ("rice", "pasta", "bread", "quinoa", "oat", "wheat", "barley"),
        "Pantry": ("oil", "salt", "spice", "sauce", "vinegar", "flour", "sugar"),
    }

    def __init__(self, db_session=None):
        self.health_engine = HealthEngine()
        self.taste_engine = TasteEngine()
        self.sustainability_service = SustainableFoodDBService()
        self.recipes = self._load_recipes(db_session)
        self.optimizer = WeeklyPlanOptimizer(
            beam_width=int(os.getenv("MEAL_OPTIMIZER_BEAM_WIDTH", "48")),
            max_options_per_slot=int(os.getenv("MEAL_OPTIMIZER_OPTIONS_PER_SLOT", "36")),
        )

    @staticmethod
    def _coerce_ingredient_lines(raw_values: Iterable[Any]) -> List[IngredientLine]:
        lines: List[IngredientLine] = []
        for value in raw_values:
            try:
                if isinstance(value, IngredientLine):
                    lines.append(value)
                elif isinstance(value, dict):
                    lines.append(IngredientLine.model_validate(value))
                else:
                    lines.append(parse_ingredient_line(str(value)))
            except (TypeError, ValueError):
                lines.append(parse_ingredient_line(str(value)))
        return lines

    def _load_recipes(self, db_session=None) -> List[Recipe]:
        from backend.database import DBRecipe, SessionLocal

        db = db_session or SessionLocal()
        try:
            rows = db.query(DBRecipe).all()
            recipes: List[Recipe] = []
            for row in rows:
                try:
                    raw_ingredients = [str(value) for value in list(row.ingredients or [])]
                    stored_lines = list(getattr(row, "ingredient_data", None) or [])
                    ingredient_lines = self._coerce_ingredient_lines(stored_lines or raw_ingredients)
                    recipes.append(
                        Recipe(
                            id=row.id,
                            name=row.name or "Unnamed recipe",
                            description=row.description or "",
                            image_url=row.image_url,
                            ingredients=raw_ingredients,
                            ingredient_lines=ingredient_lines,
                            servings=max(0.01, float(getattr(row, "servings", 1.0) or 1.0)),
                            calories=max(0, int(row.calories or 0)),
                            macros=dict(row.macros or {}),
                            flavor_profile=dict(row.flavor_profile or {}),
                            tags=list(row.tags or []),
                            cuisine=row.cuisine,
                            instructions=list(row.instructions or []),
                            estimated_cost=max(0.0, float(row.estimated_cost or 0.0)),
                            source_name=getattr(row, "source_name", None),
                            source_url=getattr(row, "source_url", None),
                            source_version=getattr(row, "source_version", None),
                            nutrition_basis=getattr(row, "nutrition_basis", None) or "per_serving",
                        )
                    )
                except (TypeError, ValueError) as exc:
                    print(f"Skipping invalid recipe row {getattr(row, 'id', '<unknown>')}: {exc}")
            return recipes
        finally:
            if db_session is None:
                db.close()

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

        try:
            optimized = self.optimizer.optimize(
                recipes=candidates,
                days=days,
                meal_slots=self.MEAL_SLOTS,
                daily_target=targets,
                taste_score=lambda recipe: self.taste_engine.predict_hedonic_score(recipe, genome),
                ingredient_keys=self._recipe_ingredient_keys,
            )
        except OptimizationInfeasible as exc:
            raise InfeasiblePlanError(str(exc), diagnostics=exc.diagnostics) from exc

        selections_by_day: Dict[int, List[PlanSelection]] = defaultdict(list)
        for selection in optimized.selections:
            selections_by_day[selection.day].append(selection)

        daily_plans: List[DailyPlan] = []
        variety_engine = VarietyEngine(no_repeat_window=7)
        for day in range(1, days + 1):
            daily_plans.append(
                self._build_daily_plan(
                    day=day,
                    selections=selections_by_day[day],
                    target=targets,
                    genome=genome,
                    variety_engine=variety_engine,
                )
            )

        shopping_list = self._generate_shopping_list(optimized.selections)
        warnings = [
            "Hard dietary and allergy filters are enforced before optimization; medical-condition compatibility is not clinically validated.",
            "Micronutrients are reported only when quantity-normalized source data exists and are not yet hard optimization constraints.",
            "Environmental values remain disabled unless an explicitly configured quantity-aware source is enabled.",
        ]
        if user.health_conditions or user.medications:
            warnings.append(
                "Review this plan with a qualified clinician before using it for a health condition or medication interaction."
            )
        if optimized.summary.relaxations:
            warnings.extend(optimized.summary.relaxations)
        if any(
            item.get("quantity_status") != "normalized"
            for category in shopping_list.values()
            for item in category.values()
        ):
            warnings.append(
                "Some shopping-list entries could not be converted to a single normalized unit; their original units or occurrences are preserved."
            )

        return PlanResponse(
            user_id=user_id or "anonymous",
            days=daily_plans,
            shopping_list=shopping_list,
            prep_timeline=self._generate_prep_timeline(daily_plans),
            overall_stats=self._calculate_overall_stats(daily_plans, targets),
            optimization=optimized.summary,
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

        excluded_counts: Dict[str, int] = defaultdict(int)
        valid: List[Recipe] = []
        for recipe in self.recipes:
            if not recipe.ingredients or recipe.calories <= 0:
                excluded_counts["missing_required_recipe_data"] += 1
                continue
            searchable_values = [
                *recipe.ingredients,
                *(line.name for line in recipe.ingredient_lines),
                *recipe.tags,
                recipe.name,
            ]
            matched = next(
                (
                    term
                    for term in forbidden_terms
                    if any(self._contains_term(value, term) for value in searchable_values)
                ),
                None,
            )
            if matched is not None:
                excluded_counts[f"forbidden:{self._normalize_text(matched)}"] += 1
                continue
            valid.append(recipe)

        if not valid:
            constraints = sorted({term for term in forbidden_terms if term})
            detail = ", ".join(constraints[:12]) or "the selected dietary constraints"
            raise InfeasiblePlanError(
                f"No recipes satisfy {detail}. Add compliant recipes or relax a non-safety preference.",
                diagnostics={
                    "total_recipes": len(self.recipes),
                    "excluded_counts": dict(sorted(excluded_counts.items())),
                    "active_forbidden_terms": constraints,
                },
            )
        return valid

    @staticmethod
    def _recipe_ingredient_keys(recipe: Recipe) -> Iterable[str]:
        if recipe.ingredient_lines:
            return [line.name for line in recipe.ingredient_lines if line.name]
        return [canonicalize_ingredient_name(value) for value in recipe.ingredients]

    def _build_daily_plan(
        self,
        *,
        day: int,
        selections: List[PlanSelection],
        target: NutrientTarget,
        genome: Dict[str, Any],
        variety_engine: VarietyEngine,
    ) -> DailyPlan:
        order = {slot: index for index, (slot, _) in enumerate(self.MEAL_SLOTS)}
        selections = sorted(selections, key=lambda item: order[item.slot])
        meals = {item.slot: item.recipe for item in selections}
        portions = {item.slot: item.portion for item in selections}

        calories = sum(item.recipe.calories * item.portion for item in selections)
        protein = sum(float(item.recipe.macros.get("protein", 0) or 0) * item.portion for item in selections)
        carbs = sum(float(item.recipe.macros.get("carbs", 0) or 0) * item.portion for item in selections)
        fat = sum(float(item.recipe.macros.get("fat", 0) or 0) * item.portion for item in selections)
        cost = sum(float(item.recipe.estimated_cost or 0.0) * item.portion for item in selections)

        taste_scores = [
            self.taste_engine.predict_hedonic_score(item.recipe, genome)
            for item in selections
        ]
        taste = sum(taste_scores) / len(taste_scores) if taste_scores else 0.0
        recipes = [item.recipe for item in selections]
        health = self._macro_match_score(
            calories=calories,
            protein=protein,
            carbs=carbs,
            fat=fat,
            targets=target,
        )

        carbon_footprint: Optional[float] = None
        carbon_status = "disabled"
        if os.getenv("ENABLE_SUSTAINABILITY_ESTIMATES", "false").lower() == "true":
            try:
                raw_ingredients = [value for recipe in recipes for value in recipe.ingredients]
                result = self.sustainability_service.get_sustainability_score(raw_ingredients)
                carbon_footprint = float(result["carbon_footprint_kg"])
                carbon_status = "unverified_estimate"
            except Exception:
                carbon_status = "unavailable"

        cuisine = next((recipe.cuisine for recipe in recipes if recipe.cuisine), "unknown")
        variety = variety_engine.calculate_variety_score(recipes)
        variety_engine.update_history(recipes, cuisine)

        return DailyPlan(
            day=day,
            meals=meals,
            portions=portions,
            total_stats={
                "calories": round(calories, 2),
                "protein_g": round(protein, 2),
                "carbs_g": round(carbs, 2),
                "fat_g": round(fat, 2),
                "target_calories": float(target.calories),
                "target_protein_g": float(target.protein_g),
                "target_carbs_g": float(target.carbs_g),
                "target_fat_g": float(target.fat_g),
                "carbon_footprint_kg": carbon_footprint,
                "carbon_data_status": carbon_status,
                "total_cost": round(cost, 2),
            },
            scores={
                "health_match": round(float(health), 6),
                "taste_match": round(float(taste), 6),
                "variety": round(float(variety), 6),
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

    @staticmethod
    def _format_number(value: float) -> str:
        rounded = round(value, 2)
        return str(int(rounded)) if rounded.is_integer() else f"{rounded:.2f}".rstrip("0").rstrip(".")

    def _category_for_ingredient(self, ingredient: str) -> str:
        for category, terms in self.CATEGORY_TERMS.items():
            if any(self._contains_term(ingredient, term) for term in terms):
                return category
        return "Other"

    def _generate_shopping_list(
        self,
        selections: Iterable[PlanSelection],
    ) -> Dict[str, Dict[str, Any]]:
        aggregates: Dict[str, Dict[str, Any]] = {}
        for selection in selections:
            recipe = selection.recipe
            lines = recipe.ingredient_lines or parse_ingredient_lines(recipe.ingredients)
            scale = selection.portion / max(recipe.servings, 0.01)
            for line in lines:
                name = line.name or canonicalize_ingredient_name(line.raw)
                if not name:
                    continue
                record = aggregates.setdefault(
                    name,
                    {
                        "unit_ranges": defaultdict(lambda: [0.0, 0.0]),
                        "unquantified_occurrences": 0,
                        "occurrences": 0,
                        "source_recipe_ids": set(),
                        "raw_examples": set(),
                    },
                )
                record["occurrences"] += 1
                record["source_recipe_ids"].add(recipe.id)
                if line.raw:
                    record["raw_examples"].add(line.raw)
                minimum, maximum, unit = scale_quantity_range(line, scale)
                if minimum is None or maximum is None or not unit:
                    record["unquantified_occurrences"] += 1
                else:
                    record["unit_ranges"][unit][0] += minimum
                    record["unit_ranges"][unit][1] += maximum

        shopping_list: Dict[str, Dict[str, Any]] = {}
        for name in sorted(aggregates):
            record = aggregates[name]
            components: List[Dict[str, Any]] = []
            labels: List[str] = []
            for unit in sorted(record["unit_ranges"]):
                minimum, maximum = record["unit_ranges"][unit]
                component = {
                    "quantity_min": round(minimum, 3),
                    "quantity_max": round(maximum, 3),
                    "unit": unit,
                }
                components.append(component)
                if abs(minimum - maximum) < 1e-9:
                    labels.append(f"{self._format_number(minimum)} {unit}")
                else:
                    labels.append(
                        f"{self._format_number(minimum)}–{self._format_number(maximum)} {unit}"
                    )
            if record["unquantified_occurrences"]:
                count = record["unquantified_occurrences"]
                labels.append(f"{count} unquantified occurrence{'s' if count != 1 else ''}")

            if components and not record["unquantified_occurrences"] and len(components) == 1:
                quantity_status = "normalized"
            elif components:
                quantity_status = "mixed_or_partial"
            else:
                quantity_status = "unquantified"

            category = self._category_for_ingredient(name)
            shopping_list.setdefault(category, {})[name] = {
                "display_name": name,
                "quantity": " + ".join(labels),
                "quantity_status": quantity_status,
                "quantities": components,
                "occurrences": record["occurrences"],
                "unquantified_occurrences": record["unquantified_occurrences"],
                "source_recipe_ids": sorted(record["source_recipe_ids"]),
                "raw_examples": sorted(record["raw_examples"])[:5],
            }
        return shopping_list

    @staticmethod
    def _generate_prep_timeline(daily_plans: List[DailyPlan]) -> Dict[int, List[str]]:
        times = {"Breakfast": "8:00 AM", "Lunch": "12:00 PM", "Dinner": "6:00 PM"}
        timeline: Dict[int, List[str]] = {}
        for plan in daily_plans:
            tasks: List[str] = []
            for slot, time in times.items():
                if slot not in plan.meals:
                    continue
                portion = plan.portions.get(slot, 1.0)
                tasks.append(
                    f"{time} - Prepare {plan.meals[slot].name} ({portion:g} serving multiplier)"
                )
            timeline[plan.day] = tasks
        return timeline

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
            "average_protein_g": round(sum(float(plan.total_stats["protein_g"]) for plan in daily_plans) / count, 1),
            "average_carbs_g": round(sum(float(plan.total_stats["carbs_g"]) for plan in daily_plans) / count, 1),
            "average_fat_g": round(sum(float(plan.total_stats["fat_g"]) for plan in daily_plans) / count, 1),
            "target_calories": targets.calories,
            "target_protein_g": targets.protein_g,
            "target_carbs_g": targets.carbs_g,
            "target_fat_g": targets.fat_g,
            "total_carbon_footprint_kg": total_carbon,
            "carbon_data_status": "unverified_estimate" if carbon_values else "unavailable",
            "total_plan_cost": round(sum(float(plan.total_stats.get("total_cost", 0.0)) for plan in daily_plans), 2),
        }
