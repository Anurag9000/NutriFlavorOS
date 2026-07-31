from __future__ import annotations

from backend.domain.ingredients import parse_ingredient_line, parse_ingredient_lines
from backend.engines.plan_generator import PlanGenerator
from backend.engines.weekly_optimizer import PlanSelection, WeeklyPlanOptimizer
from backend.models import IngredientParseStatus, NutrientTarget, Recipe


def _recipe(
    recipe_id: str,
    *,
    name: str,
    calories: int,
    protein: float,
    carbs: float,
    fat: float,
    ingredients: list[str],
    servings: float = 1.0,
    cost: float = 3.0,
    cuisine: str = "test",
) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=name,
        description="",
        ingredients=ingredients,
        ingredient_lines=parse_ingredient_lines(ingredients),
        servings=servings,
        calories=calories,
        macros={"protein": protein, "carbs": carbs, "fat": fat},
        estimated_cost=cost,
        cuisine=cuisine,
    )


def test_parser_preserves_ranges_and_converts_compatible_units():
    line = parse_ingredient_line("1 1/2-2 cups chopped tomatoes")

    assert line.name == "tomato"
    assert line.quantity_min == 1.5
    assert line.quantity_max == 2.0
    assert line.unit == "cup"
    assert line.canonical_unit == "ml"
    assert line.parse_status == IngredientParseStatus.NORMALIZED
    assert line.canonical_quantity_min == 1.5 * 236.5882365
    assert line.canonical_quantity_max == 2.0 * 236.5882365


def test_parser_handles_unicode_fraction_and_unquantified_text():
    measured = parse_ingredient_line("½ kg potatoes")
    unquantified = parse_ingredient_line("salt to taste")

    assert measured.name == "potato"
    assert measured.canonical_quantity_min == 500.0
    assert measured.canonical_quantity_max == 500.0
    assert measured.canonical_unit == "g"
    assert unquantified.name == "salt"
    assert unquantified.quantity_min is None
    assert unquantified.parse_status == IngredientParseStatus.UNQUANTIFIED


def test_optimizer_is_deterministic_and_uses_portion_options():
    recipes = [
        _recipe(
            "a",
            name="Rice bowl",
            calories=420,
            protein=20,
            carbs=68,
            fat=8,
            ingredients=["200 g rice", "100 g tofu"],
            cuisine="asian",
        ),
        _recipe(
            "b",
            name="Lentil plate",
            calories=360,
            protein=24,
            carbs=52,
            fat=7,
            ingredients=["180 g lentils", "100 g tomato"],
            cuisine="indian",
        ),
        _recipe(
            "c",
            name="Oat fruit cup",
            calories=260,
            protein=10,
            carbs=44,
            fat=6,
            ingredients=["80 g oats", "1 banana"],
            cuisine="international",
        ),
        _recipe(
            "d",
            name="Yogurt snack",
            calories=180,
            protein=14,
            carbs=18,
            fat=5,
            ingredients=["200 g yogurt"],
            cuisine="international",
        ),
    ]
    optimizer = WeeklyPlanOptimizer(
        beam_width=20,
        max_options_per_slot=20,
        portion_options=(0.75, 1.0, 1.25),
        repeat_window_slots=2,
        max_recipe_occurrences=2,
    )
    target = NutrientTarget(
        calories=1800,
        protein_g=100,
        carbs_g=220,
        fat_g=55,
    )
    kwargs = {
        "recipes": recipes,
        "days": 2,
        "meal_slots": (("Breakfast", 0.30), ("Lunch", 0.40), ("Dinner", 0.30)),
        "daily_target": target,
        "taste_score": lambda recipe: 0.7 if recipe.id in {"a", "b"} else 0.6,
        "ingredient_keys": lambda recipe: [line.name for line in recipe.ingredient_lines],
    }

    first = optimizer.optimize(**kwargs)
    second = optimizer.optimize(**kwargs)

    first_signature = [
        (selection.day, selection.slot, selection.recipe.id, selection.portion)
        for selection in first.selections
    ]
    second_signature = [
        (selection.day, selection.slot, selection.recipe.id, selection.portion)
        for selection in second.selections
    ]
    assert first_signature == second_signature
    assert len(first_signature) == 6
    assert all(portion in {0.75, 1.0, 1.25} for _, _, _, portion in first_signature)
    assert first.summary.deterministic is True
    assert first.summary.method == "deterministic_beam_search_v1"


def test_shopping_list_aggregates_serving_scaled_quantities():
    recipe = _recipe(
        "rice",
        name="Rice",
        calories=300,
        protein=6,
        carbs=65,
        fat=1,
        ingredients=["200 g rice", "2 cups water", "salt to taste"],
        servings=2,
    )
    selections = [
        PlanSelection(day=1, slot="Lunch", recipe=recipe, portion=1.0),
        PlanSelection(day=2, slot="Lunch", recipe=recipe, portion=1.0),
    ]
    planner = PlanGenerator.__new__(PlanGenerator)

    shopping = planner._generate_shopping_list(selections)

    rice = shopping["Grains"]["rice"]
    water = shopping["Other"]["water"]
    salt = shopping["Pantry"]["salt"]
    assert rice["quantity_status"] == "normalized"
    assert rice["quantities"] == [
        {"quantity_min": 200.0, "quantity_max": 200.0, "unit": "g"}
    ]
    assert water["quantities"] == [
        {
            "quantity_min": round(2 * 236.5882365, 3),
            "quantity_max": round(2 * 236.5882365, 3),
            "unit": "ml",
        }
    ]
    assert salt["quantity_status"] == "unquantified"
    assert salt["unquantified_occurrences"] == 2
