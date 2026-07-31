from backend.domain.ingredients import parse_ingredient_lines
from backend.domain.nutrition_validation import validate_recipe_nutrition
from backend.models import Recipe


def test_energy_mismatch_is_reported_without_mutating_source_values():
    recipe = Recipe(
        id="mismatch",
        name="Mismatch recipe",
        description="",
        ingredients=["100 g rice"],
        ingredient_lines=parse_ingredient_lines(["100 g rice"]),
        calories=100,
        macros={"protein": 20, "carbs": 50, "fat": 20},
        servings=1,
        nutrition_basis="per_serving",
    )

    report = validate_recipe_nutrition(recipe)

    assert report["valid"] is True
    assert report["declared_calories"] == 100.0
    assert report["macro_derived_calories"] == 460.0
    assert report["energy_difference_ratio"] == 3.6
    assert any("differs materially" in warning for warning in report["warnings"])
    assert recipe.calories == 100
    assert recipe.macros == {"protein": 20, "carbs": 50, "fat": 20}


def test_missing_ingredients_are_structural_errors():
    recipe = Recipe(
        id="empty",
        name="Empty recipe",
        description="",
        calories=0,
        macros={},
        servings=1,
        nutrition_basis="unknown",
    )

    report = validate_recipe_nutrition(recipe)

    assert report["valid"] is False
    assert "ingredient list is empty" in report["errors"]
    assert "nutrition basis is unknown" in report["warnings"]
