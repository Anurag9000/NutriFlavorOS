"""Transparent structural validation for recipe nutrition records."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.models import Recipe


def validate_recipe_nutrition(
    recipe: Recipe,
    *,
    energy_tolerance_ratio: float = 0.25,
) -> Dict[str, Any]:
    """Return non-destructive data-quality findings for one recipe.

    The Atwater-style 4/4/9 calculation is used only as a consistency screen;
    it is not treated as a source of truth because fiber, alcohol, rounding,
    serving basis, and source methodology can legitimately create differences.
    """

    if not 0 <= energy_tolerance_ratio <= 1:
        raise ValueError("energy_tolerance_ratio must be between 0 and 1")

    errors: List[str] = []
    warnings: List[str] = []
    protein = float(recipe.macros.get("protein", 0) or 0)
    carbs = float(recipe.macros.get("carbs", 0) or 0)
    fat = float(recipe.macros.get("fat", 0) or 0)

    for label, value in (
        ("calories", float(recipe.calories)),
        ("protein", protein),
        ("carbs", carbs),
        ("fat", fat),
        ("servings", float(recipe.servings)),
    ):
        if value < 0:
            errors.append(f"{label} is negative")

    if not recipe.ingredients:
        errors.append("ingredient list is empty")
    if not recipe.ingredient_lines:
        warnings.append("canonical ingredient data is missing")
    if recipe.nutrition_basis == "unknown":
        warnings.append("nutrition basis is unknown")
    if not recipe.source_name:
        warnings.append("source name is missing")

    macro_energy = protein * 4.0 + carbs * 4.0 + fat * 9.0
    declared_energy = float(recipe.calories)
    energy_difference_ratio = None
    if declared_energy > 0:
        energy_difference_ratio = abs(macro_energy - declared_energy) / declared_energy
        if energy_difference_ratio > energy_tolerance_ratio:
            warnings.append(
                "macro-derived energy differs materially from declared calories; verify serving basis and source data"
            )
    elif macro_energy > 0:
        errors.append("declared calories are zero while macros imply positive energy")

    return {
        "recipe_id": recipe.id,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "declared_calories": declared_energy,
        "macro_derived_calories": round(macro_energy, 3),
        "energy_difference_ratio": (
            round(energy_difference_ratio, 6) if energy_difference_ratio is not None else None
        ),
        "nutrition_basis": recipe.nutrition_basis,
    }
