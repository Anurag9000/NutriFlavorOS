"""Deterministic horizon-level meal-plan optimization.

This module uses bounded beam search so the core planner remains deployable
without a native solver dependency. It evaluates the whole requested horizon,
portion choices, daily macro fit, cost, taste, and variety together rather than
making independent greedy choices. Hard food-safety filtering happens before
this optimizer is called.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

from backend.models import NutrientTarget, OptimizationSummary, Recipe


class OptimizationInfeasible(ValueError):
    def __init__(self, message: str, diagnostics: Dict[str, object] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


@dataclass(frozen=True)
class PlanSelection:
    day: int
    slot: str
    recipe: Recipe
    portion: float


@dataclass(frozen=True)
class OptimizationResult:
    selections: Tuple[PlanSelection, ...]
    summary: OptimizationSummary


@dataclass(frozen=True)
class _CandidateOption:
    recipe: Recipe
    portion: float
    calories: float
    protein: float
    carbs: float
    fat: float
    cost: float
    ingredient_keys: frozenset[str]
    cuisine_key: str
    static_score: float


@dataclass
class _BeamState:
    selections: Tuple[PlanSelection, ...]
    score: float
    recent_ids: Tuple[str, ...]
    recipe_counts: Dict[str, int]
    day_calories: float
    day_protein: float
    day_carbs: float
    day_fat: float
    unique_ingredients: frozenset[str]
    cuisines: frozenset[str]


class WeeklyPlanOptimizer:
    """Optimize a complete multi-day plan with deterministic bounded search."""

    def __init__(
        self,
        *,
        beam_width: int = 48,
        max_options_per_slot: int = 36,
        portion_options: Sequence[float] = (0.75, 1.0, 1.25, 1.5),
        repeat_window_slots: int = 8,
        max_recipe_occurrences: int = 2,
    ) -> None:
        if beam_width < 1 or max_options_per_slot < 1:
            raise ValueError("beam_width and max_options_per_slot must be positive")
        clean_portions = tuple(sorted({float(value) for value in portion_options if value > 0}))
        if not clean_portions:
            raise ValueError("at least one positive portion option is required")
        self.beam_width = beam_width
        self.max_options_per_slot = max_options_per_slot
        self.portion_options = clean_portions
        self.repeat_window_slots = max(0, repeat_window_slots)
        self.max_recipe_occurrences = max(1, max_recipe_occurrences)

    @staticmethod
    def _closeness(actual: float, target: float) -> float:
        if target <= 0:
            return 1.0 if actual <= 0 else 0.0
        return max(0.0, 1.0 - abs(actual - target) / target)

    @classmethod
    def _macro_match(
        cls,
        calories: float,
        protein: float,
        carbs: float,
        fat: float,
        target: NutrientTarget,
    ) -> float:
        return (
            cls._closeness(calories, target.calories) * 0.40
            + cls._closeness(protein, target.protein_g) * 0.25
            + cls._closeness(carbs, target.carbs_g) * 0.20
            + cls._closeness(fat, target.fat_g) * 0.15
        )

    @staticmethod
    def _recipe_macros(recipe: Recipe, portion: float) -> Tuple[float, float, float, float]:
        return (
            float(recipe.calories) * portion,
            float(recipe.macros.get("protein", 0) or 0) * portion,
            float(recipe.macros.get("carbs", 0) or 0) * portion,
            float(recipe.macros.get("fat", 0) or 0) * portion,
        )

    def _options_for_slot(
        self,
        *,
        recipes: Sequence[Recipe],
        target: NutrientTarget,
        is_snack: bool,
        taste_score: Callable[[Recipe], float],
        ingredient_keys: Callable[[Recipe], Iterable[str]],
    ) -> List[_CandidateOption]:
        options: List[_CandidateOption] = []
        min_calories, max_calories = ((50.0, 500.0) if is_snack else (150.0, 1200.0))

        for recipe in recipes:
            for portion in self.portion_options:
                calories, protein, carbs, fat = self._recipe_macros(recipe, portion)
                if not min_calories <= calories <= max_calories:
                    continue

                health = self._macro_match(calories, protein, carbs, fat, target)
                taste = max(0.0, min(1.0, float(taste_score(recipe))))
                cost = max(0.0, float(recipe.estimated_cost or 0.0) * portion)
                budget = max(0.0, 1.0 - cost / 20.0)
                static_score = health * 0.62 + taste * 0.30 + budget * 0.08
                options.append(
                    _CandidateOption(
                        recipe=recipe,
                        portion=portion,
                        calories=calories,
                        protein=protein,
                        carbs=carbs,
                        fat=fat,
                        cost=cost,
                        ingredient_keys=frozenset(key for key in ingredient_keys(recipe) if key),
                        cuisine_key=(recipe.cuisine or "unknown").strip().lower(),
                        static_score=static_score,
                    )
                )

        options.sort(
            key=lambda item: (
                -item.static_score,
                item.recipe.id,
                item.portion,
            )
        )
        return options[: self.max_options_per_slot]

    @staticmethod
    def _state_sort_key(state: _BeamState) -> Tuple[float, Tuple[Tuple[str, float], ...]]:
        signature = tuple((item.recipe.id, item.portion) for item in state.selections)
        return (-state.score, signature)

    def optimize(
        self,
        *,
        recipes: Sequence[Recipe],
        days: int,
        meal_slots: Sequence[Tuple[str, float]],
        daily_target: NutrientTarget,
        taste_score: Callable[[Recipe], float],
        ingredient_keys: Callable[[Recipe], Iterable[str]],
    ) -> OptimizationResult:
        if days < 1:
            raise ValueError("days must be positive")
        if not recipes:
            raise OptimizationInfeasible("No recipes are available for optimization")
        if not meal_slots:
            raise OptimizationInfeasible("No meal slots are configured")

        slots: List[Tuple[int, str, float]] = [
            (day, slot, weight)
            for day in range(1, days + 1)
            for slot, weight in meal_slots
        ]
        slot_options: List[List[_CandidateOption]] = []
        slot_candidate_counts: Dict[str, int] = {}
        for day, slot, weight in slots:
            slot_target = NutrientTarget(
                calories=max(1, round(daily_target.calories * weight)),
                protein_g=max(0, round(daily_target.protein_g * weight)),
                carbs_g=max(0, round(daily_target.carbs_g * weight)),
                fat_g=max(0, round(daily_target.fat_g * weight)),
                micro_nutrients={},
            )
            options = self._options_for_slot(
                recipes=recipes,
                target=slot_target,
                is_snack="snack" in slot.lower(),
                taste_score=taste_score,
                ingredient_keys=ingredient_keys,
            )
            key = f"day_{day}:{slot}"
            slot_candidate_counts[key] = len(options)
            if not options:
                raise OptimizationInfeasible(
                    f"No portioned recipes fit the configured calorie range for {slot}",
                    diagnostics={
                        "failed_slot": key,
                        "candidate_counts": slot_candidate_counts,
                        "portion_options": list(self.portion_options),
                    },
                )
            slot_options.append(options)

        slot_count = len(slots)
        effective_max_occurrences = max(
            self.max_recipe_occurrences,
            math.ceil(slot_count / max(1, len(recipes))) + 1,
        )
        effective_repeat_window = min(self.repeat_window_slots, max(0, len(recipes) - 1))
        relaxations: List[str] = []
        if effective_max_occurrences != self.max_recipe_occurrences:
            relaxations.append(
                "Maximum recipe occurrences increased because the recipe pool is too small for the requested horizon."
            )
        if effective_repeat_window != self.repeat_window_slots:
            relaxations.append(
                "Recipe repeat window shortened because the recipe pool is too small for the configured window."
            )

        beam: List[_BeamState] = [
            _BeamState(
                selections=(),
                score=0.0,
                recent_ids=(),
                recipe_counts={},
                day_calories=0.0,
                day_protein=0.0,
                day_carbs=0.0,
                day_fat=0.0,
                unique_ingredients=frozenset(),
                cuisines=frozenset(),
            )
        ]

        for index, ((day, slot, _), options) in enumerate(zip(slots, slot_options)):
            end_of_day = (index + 1) % len(meal_slots) == 0

            def expand(
                ignore_repeat_window: bool = False,
                ignore_occurrence_cap: bool = False,
            ) -> List[_BeamState]:
                expanded: List[_BeamState] = []
                for state in beam:
                    for option in options:
                        recipe_id = option.recipe.id
                        if (
                            not ignore_repeat_window
                            and effective_repeat_window > 0
                            and recipe_id in state.recent_ids[-effective_repeat_window:]
                        ):
                            continue
                        if (
                            not ignore_occurrence_cap
                            and state.recipe_counts.get(recipe_id, 0) >= effective_max_occurrences
                        ):
                            continue

                        if option.ingredient_keys:
                            overlap = len(option.ingredient_keys & state.unique_ingredients)
                            ingredient_novelty = 1.0 - overlap / len(option.ingredient_keys)
                        else:
                            ingredient_novelty = 0.5
                        cuisine_novelty = 1.0 if option.cuisine_key not in state.cuisines else 0.2

                        day_calories = state.day_calories + option.calories
                        day_protein = state.day_protein + option.protein
                        day_carbs = state.day_carbs + option.carbs
                        day_fat = state.day_fat + option.fat
                        score = (
                            state.score
                            + option.static_score
                            + ingredient_novelty * 0.08
                            + cuisine_novelty * 0.04
                        )
                        if end_of_day:
                            score += self._macro_match(
                                day_calories,
                                day_protein,
                                day_carbs,
                                day_fat,
                                daily_target,
                            ) * 0.90

                        counts = dict(state.recipe_counts)
                        counts[recipe_id] = counts.get(recipe_id, 0) + 1
                        expanded.append(
                            _BeamState(
                                selections=state.selections
                                + (PlanSelection(day=day, slot=slot, recipe=option.recipe, portion=option.portion),),
                                score=score,
                                recent_ids=(state.recent_ids + (recipe_id,))[-max(1, effective_repeat_window):],
                                recipe_counts=counts,
                                day_calories=0.0 if end_of_day else day_calories,
                                day_protein=0.0 if end_of_day else day_protein,
                                day_carbs=0.0 if end_of_day else day_carbs,
                                day_fat=0.0 if end_of_day else day_fat,
                                unique_ingredients=state.unique_ingredients | option.ingredient_keys,
                                cuisines=state.cuisines | {option.cuisine_key},
                            )
                        )
                return expanded

            expanded = expand(ignore_repeat_window=False, ignore_occurrence_cap=False)
            if not expanded:
                expanded = expand(ignore_repeat_window=True, ignore_occurrence_cap=False)
                if expanded:
                    message = f"Repeat-window preference relaxed at day {day} slot {slot}."
                    if message not in relaxations:
                        relaxations.append(message)
            if not expanded:
                expanded = expand(ignore_repeat_window=True, ignore_occurrence_cap=True)
                if expanded:
                    message = f"Recipe occurrence cap relaxed at day {day} slot {slot}."
                    if message not in relaxations:
                        relaxations.append(message)
            if not expanded:
                raise OptimizationInfeasible(
                    f"The optimizer exhausted all combinations at day {day} slot {slot}",
                    diagnostics={
                        "failed_slot": f"day_{day}:{slot}",
                        "candidate_counts": slot_candidate_counts,
                        "effective_repeat_window_slots": effective_repeat_window,
                        "effective_max_recipe_occurrences": effective_max_occurrences,
                    },
                )

            expanded.sort(key=self._state_sort_key)
            beam = expanded[: self.beam_width]

        best = min(beam, key=self._state_sort_key)
        normalized_objective = best.score / max(1, slot_count)
        return OptimizationResult(
            selections=best.selections,
            summary=OptimizationSummary(
                method="deterministic_beam_search_v1",
                deterministic=True,
                objective_score=round(normalized_objective, 6),
                beam_width=self.beam_width,
                candidate_count=len(recipes),
                slot_count=slot_count,
                portion_options=list(self.portion_options),
                repeat_window_slots=effective_repeat_window,
                max_recipe_occurrences=effective_max_occurrences,
                relaxations=relaxations,
                slot_candidate_counts=slot_candidate_counts,
            ),
        )
