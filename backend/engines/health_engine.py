"""General adult nutrition target estimation and transparent recipe scoring.

This module provides planning heuristics, not diagnosis or treatment. Clinical
conditions, pregnancy/lactation, pediatric nutrition, eating disorders, renal
or hepatic impairment, and medication management require specialist review.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.models import Gender, Goal, NutrientTarget, UserProfile
from backend.services.dietrxdb_service import DietRxDBService
from backend.services.recipedb_service import RecipeDBService


class HealthEngine:
    """Adult macro targets plus advisory nutrient/condition scoring."""

    MICRONUTRIENT_RDA = {
        "Vitamin A": {"male": 900, "female": 700, "unit": "mcg"},
        "Vitamin C": {"male": 90, "female": 75, "unit": "mg"},
        "Vitamin D": {"male": 15, "female": 15, "unit": "mcg"},
        "Vitamin E": {"male": 15, "female": 15, "unit": "mg"},
        "Vitamin K": {"male": 120, "female": 90, "unit": "mcg"},
        "Vitamin B1 (Thiamin)": {"male": 1.2, "female": 1.1, "unit": "mg"},
        "Vitamin B2 (Riboflavin)": {"male": 1.3, "female": 1.1, "unit": "mg"},
        "Vitamin B3 (Niacin)": {"male": 16, "female": 14, "unit": "mg"},
        "Vitamin B6": {"male": 1.3, "female": 1.3, "unit": "mg"},
        "Vitamin B12": {"male": 2.4, "female": 2.4, "unit": "mcg"},
        "Folate": {"male": 400, "female": 400, "unit": "mcg"},
        "Calcium": {"male": 1000, "female": 1000, "unit": "mg"},
        "Iron": {"male": 8, "female": 18, "unit": "mg"},
        "Magnesium": {"male": 400, "female": 310, "unit": "mg"},
        "Phosphorus": {"male": 700, "female": 700, "unit": "mg"},
        "Potassium": {"male": 3400, "female": 2600, "unit": "mg"},
        "Sodium": {"male": 1500, "female": 1500, "unit": "mg"},
        "Zinc": {"male": 11, "female": 8, "unit": "mg"},
        "Copper": {"male": 900, "female": 900, "unit": "mcg"},
        "Selenium": {"male": 55, "female": 55, "unit": "mcg"},
        "Manganese": {"male": 2.3, "female": 1.8, "unit": "mg"},
    }

    def __init__(self):
        self.recipe_service = RecipeDBService()
        self.diet_rx_service = DietRxDBService()

    @staticmethod
    def calculate_bmr(user: UserProfile) -> float:
        """Estimate adult BMR with Mifflin-St Jeor."""

        if user.age < 18:
            raise ValueError("Automatic calorie targets are supported only for adults aged 18 or older")

        base = (10 * user.weight_kg) + (6.25 * user.height_cm) - (5 * user.age)
        if user.gender == Gender.MALE:
            return base + 5
        if user.gender == Gender.FEMALE:
            return base - 161
        return base - 78

    def calculate_targets(self, user: UserProfile) -> NutrientTarget:
        if user.target_calories is not None:
            target_calories = float(user.target_calories)
        else:
            bmr = self.calculate_bmr(user)
            tdee = bmr * user.activity_level
            if user.goal == Goal.WEIGHT_LOSS:
                target_calories = tdee * 0.85
            elif user.goal == Goal.MUSCLE_GAIN:
                target_calories = tdee * 1.10
            else:
                target_calories = tdee
            target_calories = max(1200.0, target_calories)

        if user.goal == Goal.MUSCLE_GAIN:
            p_ratio, c_ratio, f_ratio = 0.30, 0.45, 0.25
        elif user.goal == Goal.WEIGHT_LOSS:
            p_ratio, c_ratio, f_ratio = 0.35, 0.35, 0.30
        else:
            p_ratio, c_ratio, f_ratio = 0.25, 0.45, 0.30

        calculated_protein = target_calories * p_ratio / 4
        calculated_carbs = target_calories * c_ratio / 4
        calculated_fat = target_calories * f_ratio / 9
        protein_g = user.target_protein_g if user.target_protein_g is not None else calculated_protein
        carbs_g = user.target_carbs_g if user.target_carbs_g is not None else calculated_carbs
        fat_g = user.target_fat_g if user.target_fat_g is not None else calculated_fat

        if user.gender == Gender.MALE:
            micro_targets = {
                nutrient: float(values["male"])
                for nutrient, values in self.MICRONUTRIENT_RDA.items()
            }
        elif user.gender == Gender.FEMALE:
            micro_targets = {
                nutrient: float(values["female"])
                for nutrient, values in self.MICRONUTRIENT_RDA.items()
            }
        else:
            micro_targets = {
                nutrient: (float(values["male"]) + float(values["female"])) / 2
                for nutrient, values in self.MICRONUTRIENT_RDA.items()
            }

        return NutrientTarget(
            calories=round(target_calories),
            protein_g=round(float(protein_g)),
            carbs_g=round(float(carbs_g)),
            fat_g=round(float(fat_g)),
            micro_nutrients=micro_targets,
        )

    def get_recipe_full_nutrition(self, recipe_id: str) -> Dict[str, Any]:
        try:
            macros = self.recipe_service.get_nutrition_info(recipe_id) or {}
            micros = self.recipe_service.get_micronutrition_info(recipe_id) or {}
            return {"macros": macros, "micros": micros, "status": "available"}
        except Exception as exc:
            print(f"Nutrition lookup failed for recipe {recipe_id}: {exc}")
            return {"macros": {}, "micros": {}, "status": "unavailable"}

    @staticmethod
    def _match(actual: float, target: float) -> float:
        if target <= 0:
            return 1.0 if actual <= 0 else 0.0
        return max(0.0, 1.0 - abs(actual - target) / target)

    def score_recipe_comprehensive(
        self,
        recipe_id: str,
        target: NutrientTarget,
        user_conditions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Return an advisory score with explicit unknown-safety handling."""

        nutrition = self.get_recipe_full_nutrition(recipe_id)
        macros = nutrition.get("macros", {})
        micros = nutrition.get("micros", {})

        macro_values = {
            "calories": float(macros.get("calories", 0) or 0),
            "protein": float(macros.get("protein", 0) or 0),
            "carbs": float(macros.get("carbs", 0) or 0),
            "fat": float(macros.get("fat", 0) or 0),
        }
        macro_score = sum(
            (
                self._match(macro_values["calories"], target.calories) * 0.4,
                self._match(macro_values["protein"], target.protein_g) * 0.25,
                self._match(macro_values["carbs"], target.carbs_g) * 0.2,
                self._match(macro_values["fat"], target.fat_g) * 0.15,
            )
        )

        coverage: Dict[str, float] = {}
        for nutrient, target_value in target.micro_nutrients.items():
            actual = float(micros.get(nutrient, 0) or 0)
            coverage[nutrient] = min(1.0, actual / target_value) if target_value > 0 else 0.0
        micro_score = sum(coverage.values()) / len(coverage) if coverage else 0.0

        warnings: List[str] = []
        verification_errors: List[str] = []
        condition_score = 1.0
        if user_conditions:
            try:
                recipe_info = self.recipe_service.get_recipe_info(recipe_id) or {}
                ingredients = recipe_info.get("ingredients", []) or []
            except Exception as exc:
                ingredients = []
                verification_errors.append(f"Recipe ingredient lookup failed: {exc}")

            if not ingredients:
                verification_errors.append("No ingredient data was available for condition checks")

            for ingredient in ingredients:
                try:
                    compatibility = self.diet_rx_service.check_condition_compatibility(
                        ingredient, user_conditions
                    )
                    if not compatibility.get("safe_to_consume", False):
                        condition_score = 0.0
                        warnings.extend(compatibility.get("warnings", []))
                    elif float(compatibility.get("score", 0)) < 50:
                        condition_score *= 0.7
                except Exception as exc:
                    verification_errors.append(f"Could not verify {ingredient}: {exc}")

        if verification_errors:
            condition_score = min(condition_score, 0.5)
        final_score = macro_score * 0.45 + micro_score * 0.25 + condition_score * 0.30
        safety_status = "unsafe" if warnings else "unknown" if verification_errors else "no_flags_found"

        return {
            "total_score": final_score,
            "macro_score": macro_score,
            "micro_score": micro_score,
            "condition_score": condition_score,
            "warnings": warnings,
            "verification_errors": verification_errors,
            "safe": safety_status == "no_flags_found",
            "safety_status": safety_status,
            "micronutrient_coverage": coverage,
            "clinical_validation": False,
        }
