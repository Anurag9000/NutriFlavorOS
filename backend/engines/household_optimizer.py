"""Deterministic household optimizer with separate pantry and preference terms.

Hard recipe safety filtering occurs before this module. Pantry coverage is
modeled independently from taste and price so the API never mislabels inventory
availability as preference, nutrition, or monetary savings.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence, Tuple
from backend.engines.weekly_optimizer import OptimizationInfeasible, OptimizationResult, PlanSelection
from backend.models import NutrientTarget, OptimizationSummary, Recipe

@dataclass(frozen=True)
class _Option:
    recipe: Recipe; portion: float; calories: float; protein: float; carbs: float; fat: float; cost: float
    ingredients: frozenset[str]; cuisine: str; preference: float; pantry: float; slot_fit: float
@dataclass(frozen=True)
class _State:
    selections: Tuple[PlanSelection, ...]; score: float; recent: Tuple[str, ...]; counts: Tuple[Tuple[str,int], ...]
    day_values: Tuple[float,float,float,float]; ingredients: frozenset[str]; cuisines: frozenset[str]

def _close(actual:float,target:float)->float:
    return 1.0 if target<=0 and actual<=0 else 0.0 if target<=0 else max(0.0,1.0-abs(actual-target)/target)
def _macro(c:float,p:float,carb:float,f:float,t:NutrientTarget)->float:
    return _close(c,t.calories)*.40+_close(p,t.protein_g)*.25+_close(carb,t.carbs_g)*.20+_close(f,t.fat_g)*.15

def optimize_household_horizon(*, recipes:Sequence[Recipe], days:int, meal_slots:Sequence[Tuple[str,float]], daily_target:NutrientTarget,
    preference_score:Callable[[Recipe],float], pantry_score:Callable[[Recipe],float], ingredient_keys:Callable[[Recipe],Iterable[str]],
    beam_width:int=64, max_options_per_slot:int=48, portion_options:Sequence[float]=(0.75,1.0,1.25,1.5), repeat_window_slots:int=8, max_recipe_occurrences:int=3)->OptimizationResult:
    if not recipes or days<1 or not meal_slots: raise OptimizationInfeasible("Household optimizer has no feasible search surface")
    slots=[(day,slot,weight) for day in range(1,days+1) for slot,weight in meal_slots]
    option_sets:List[List[_Option]]=[]; candidate_counts:Dict[str,int]={}
    for day,slot,weight in slots:
        target=NutrientTarget(calories=max(1,round(daily_target.calories*weight)),protein_g=max(0,round(daily_target.protein_g*weight)),carbs_g=max(0,round(daily_target.carbs_g*weight)),fat_g=max(0,round(daily_target.fat_g*weight)),micro_nutrients={})
        snack="snack" in slot.lower(); values=[]
        for recipe in recipes:
            for portion in sorted({float(x) for x in portion_options if x>0}):
                c=recipe.calories*portion; p=float(recipe.macros.get("protein",0) or 0)*portion; carb=float(recipe.macros.get("carbs",0) or 0)*portion; f=float(recipe.macros.get("fat",0) or 0)*portion
                if not ((50<=c<=500) if snack else (150<=c<=1200)): continue
                values.append(_Option(recipe,portion,c,p,carb,f,float(recipe.estimated_cost or 0)*portion,frozenset(x for x in ingredient_keys(recipe) if x),(recipe.cuisine or "unknown").lower(),max(0,min(1,float(preference_score(recipe)))),max(0,min(1,float(pantry_score(recipe)))),_macro(c,p,carb,f,target)))
        values.sort(key=lambda x:(-(x.slot_fit*.58+x.preference*.18+x.pantry*.16+max(0,1-x.cost/20)*.08),x.recipe.id,x.portion))
        values=values[:max_options_per_slot]; candidate_counts[f"day_{day}:{slot}"]=len(values)
        if not values: raise OptimizationInfeasible(f"No portioned household recipe fits {slot}",{"failed_slot":f"day_{day}:{slot}"})
        option_sets.append(values)
    effective_occ=max(max_recipe_occurrences,(len(slots)+len(recipes)-1)//len(recipes)); effective_window=min(repeat_window_slots,max(0,len(recipes)-1)); relax=[]
    if effective_occ!=max_recipe_occurrences: relax.append("Household recipe occurrence cap increased because the compliant recipe pool is too small.")
    if effective_window!=repeat_window_slots: relax.append("Household repeat window shortened because the compliant recipe pool is too small.")
    beam=[_State((),0.0,(),(),(0,0,0,0),frozenset(),frozenset())]
    for index,((day,slot,_),options) in enumerate(zip(slots,option_sets)):
        end=(index+1)%len(meal_slots)==0; expanded=[]
        for state in beam:
            counts=dict(state.counts)
            for option in options:
                rid=option.recipe.id
                if effective_window and rid in state.recent[-effective_window:]: continue
                if counts.get(rid,0)>=effective_occ: continue
                ingredient_novelty=1-len(option.ingredients&state.ingredients)/len(option.ingredients) if option.ingredients else .5
                cuisine_novelty=1 if option.cuisine not in state.cuisines else .2
                dc,dp,dcarb,df=state.day_values; totals=(dc+option.calories,dp+option.protein,dcarb+option.carbs,df+option.fat)
                incremental=option.slot_fit*.50+option.preference*.16+option.pantry*.20+ingredient_novelty*.07+cuisine_novelty*.03+max(0,1-option.cost/20)*.04
                score=state.score+incremental+(_macro(*totals,daily_target)*.90 if end else 0)
                next_counts=dict(counts); next_counts[rid]=next_counts.get(rid,0)+1
                expanded.append(_State(state.selections+(PlanSelection(day=day,slot=slot,recipe=option.recipe,portion=option.portion),),score,(state.recent+(rid,))[-max(1,effective_window):],tuple(sorted(next_counts.items())),(0,0,0,0) if end else totals,state.ingredients|option.ingredients,state.cuisines|{option.cuisine}))
        if not expanded:
            for state in beam:
                counts=dict(state.counts)
                for option in options:
                    dc,dp,dcarb,df=state.day_values; totals=(dc+option.calories,dp+option.protein,dcarb+option.carbs,df+option.fat)
                    score=state.score+option.slot_fit*.50+option.preference*.16+option.pantry*.20+(_macro(*totals,daily_target)*.90 if end else 0)
                    next_counts=dict(counts); next_counts[option.recipe.id]=next_counts.get(option.recipe.id,0)+1
                    expanded.append(_State(state.selections+(PlanSelection(day=day,slot=slot,recipe=option.recipe,portion=option.portion),),score,(state.recent+(option.recipe.id,))[-max(1,effective_window):],tuple(sorted(next_counts.items())),(0,0,0,0) if end else totals,state.ingredients|option.ingredients,state.cuisines|{option.cuisine}))
            message=f"Household variety constraints relaxed at day {day} slot {slot}."
            if message not in relax: relax.append(message)
        expanded.sort(key=lambda s:(-s.score,tuple((x.recipe.id,x.portion) for x in s.selections))); beam=expanded[:beam_width]
    best=beam[0]
    return OptimizationResult(selections=best.selections,summary=OptimizationSummary(method="deterministic_household_pantry_beam_search_v2",deterministic=True,objective_score=round(best.score/max(1,len(slots)),6),beam_width=beam_width,candidate_count=len(recipes),slot_count=len(slots),portion_options=sorted({float(x) for x in portion_options if x>0}),repeat_window_slots=effective_window,max_recipe_occurrences=effective_occ,relaxations=relax,slot_candidate_counts=candidate_counts))
