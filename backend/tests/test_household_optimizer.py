from backend.engines.household_optimizer import optimize_household_horizon
from backend.models import NutrientTarget, Recipe


def recipe(identifier, calories, pantry):
    value=Recipe(id=identifier,name=identifier,description="",ingredients=[identifier],calories=calories,macros={"protein":20,"carbs":40,"fat":10},estimated_cost=5)
    return value, pantry


def test_household_optimizer_keeps_pantry_separate_and_deterministic():
    a,ap=recipe("pantry",400,1.0); b,bp=recipe("outside",400,0.0); scores={a.id:ap,b.id:bp}
    kwargs=dict(recipes=[a,b],days=1,meal_slots=[("Breakfast",1.0)],daily_target=NutrientTarget(calories=400,protein_g=20,carbs_g=40,fat_g=10,micro_nutrients={}),preference_score=lambda _r:0.5,pantry_score=lambda r:scores[r.id],ingredient_keys=lambda r:r.ingredients,portion_options=(1.0,),repeat_window_slots=0)
    first=optimize_household_horizon(**kwargs); second=optimize_household_horizon(**kwargs)
    assert first.selections[0].recipe.id=="pantry"
    assert first.selections==second.selections
    assert first.summary.method=="deterministic_household_pantry_beam_search_v2"
