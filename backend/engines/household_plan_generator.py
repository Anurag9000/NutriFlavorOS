"""Member-safe, pantry-aware household meal planning."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.database import (
    CURRENT_HOUSEHOLD_PLAN_SCHEMA_VERSION,
    CURRENT_PLAN_SCHEMA_VERSION,
    DBHousehold,
    DBHouseholdMember,
    DBMealPlan,
    DBUser,
)
from backend.domain.household_access import (
    HouseholdPlanRequest,
    HouseholdPlanResponse,
    HouseholdTargetSummary,
    ReservationView,
)
from backend.engines.health_engine import HealthEngine
from backend.engines.plan_generator import InfeasiblePlanError, PlanGenerator
from backend.engines.variety_engine import VarietyEngine
from backend.engines.weekly_optimizer import OptimizationInfeasible, PlanSelection
from backend.engines.household_optimizer import optimize_household_horizon
from backend.models import NutrientTarget, PlanResponse, UserProfile
from backend.services.inventory_service import list_pantry_items, reconcile_shopping_list
from backend.services.reservation_service import (
    create_plan_reservations,
    ingredient_availability_score,
    usable_pantry_intervals,
)
from backend.utils.user_profiles import db_user_to_profile


class HouseholdPlanningError(ValueError):
    def __init__(self, message: str, diagnostics: Dict[str, object] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


def _clean(values: Iterable[str]) -> List[str]:
    return sorted({str(value).strip().lower() for value in values if str(value).strip()})


def _scaled_target(target: NutrientTarget, multiplier: float) -> NutrientTarget:
    return NutrientTarget(
        calories=max(1, round(target.calories * multiplier)),
        protein_g=max(0, round(target.protein_g * multiplier)),
        carbs_g=max(0, round(target.carbs_g * multiplier)),
        fat_g=max(0, round(target.fat_g * multiplier)),
        micro_nutrients={
            name: float(value) * multiplier
            for name, value in target.micro_nutrients.items()
        },
    )


def _member_target(
    *,
    db: Session,
    member: DBHouseholdMember,
    owner_target: NutrientTarget,
    health_engine: HealthEngine,
) -> Tuple[NutrientTarget, str]:
    fallback = _scaled_target(owner_target, float(member.servings_multiplier))
    linked = db.get(DBUser, member.linked_user_id) if member.linked_user_id else None
    if linked is not None:
        try:
            linked_target = health_engine.calculate_targets(db_user_to_profile(linked))
            source = "linked_user_profile"
        except (TypeError, ValueError) as exc:
            if not any(value is not None for value in (member.target_calories, member.target_protein_g, member.target_carbs_g, member.target_fat_g)):
                raise HouseholdPlanningError(
                    f"Linked member {member.id} has an incomplete profile and no explicit member targets",
                    {"member_id": member.id, "linked_user_id": member.linked_user_id},
                ) from exc
            linked_target = fallback
            source = "explicit_member_overrides_with_owner_scaled_base"
    else:
        linked_target = fallback
        source = "declared_servings_multiplier"

    updates = {
        "calories": member.target_calories,
        "protein_g": member.target_protein_g,
        "carbs_g": member.target_carbs_g,
        "fat_g": member.target_fat_g,
    }
    if any(value is not None for value in updates.values()):
        linked_target = NutrientTarget(
            calories=int(updates["calories"] or linked_target.calories),
            protein_g=int(
                updates["protein_g"]
                if updates["protein_g"] is not None
                else linked_target.protein_g
            ),
            carbs_g=int(
                updates["carbs_g"]
                if updates["carbs_g"] is not None
                else linked_target.carbs_g
            ),
            fat_g=int(
                updates["fat_g"]
                if updates["fat_g"] is not None
                else linked_target.fat_g
            ),
            micro_nutrients=dict(linked_target.micro_nutrients),
        )
        source = f"{source}+member_overrides"
    return linked_target, source


def _aggregate_targets(
    *,
    db: Session,
    members: List[DBHouseholdMember],
    owner_profile: UserProfile,
    health_engine: HealthEngine,
) -> Tuple[NutrientTarget, HouseholdTargetSummary]:
    owner_target = health_engine.calculate_targets(owner_profile)
    total_calories = total_protein = total_carbs = total_fat = 0
    total_multiplier = 0.0
    micro: Dict[str, float] = defaultdict(float)
    sources: Dict[str, str] = {}

    for member in members:
        target, source = _member_target(
            db=db,
            member=member,
            owner_target=owner_target,
            health_engine=health_engine,
        )
        total_calories += target.calories
        total_protein += target.protein_g
        total_carbs += target.carbs_g
        total_fat += target.fat_g
        total_multiplier += float(member.servings_multiplier)
        for name, value in target.micro_nutrients.items():
            micro[name] += float(value)
        sources[str(member.id)] = source

    if not members:
        raise HouseholdPlanningError("No active household members are available")
    aggregate = NutrientTarget(
        calories=max(1, total_calories),
        protein_g=max(0, total_protein),
        carbs_g=max(0, total_carbs),
        fat_g=max(0, total_fat),
        micro_nutrients=dict(micro),
    )
    summary = HouseholdTargetSummary(
        calories=aggregate.calories,
        protein_g=aggregate.protein_g,
        carbs_g=aggregate.carbs_g,
        fat_g=aggregate.fat_g,
        member_count=len(members),
        servings_multiplier=round(total_multiplier, 3),
        source_status="linked_profiles_member_overrides_or_explicit_serving_fallback",
        member_sources=sources,
    )
    return aggregate, summary


def _aggregate_hard_constraints(
    owner_profile: UserProfile, members: List[DBHouseholdMember]
) -> UserProfile:
    allergies = list(owner_profile.allergies)
    restrictions = list(owner_profile.dietary_restrictions)
    dislikes = list(owner_profile.disliked_ingredients)
    for member in members:
        allergies.extend(member.allergies or [])
        restrictions.extend(member.dietary_restrictions or [])
        dislikes.extend(member.disliked_ingredients or [])
    return owner_profile.model_copy(
        update={
            "allergies": _clean(allergies),
            "dietary_restrictions": _clean(restrictions),
            "disliked_ingredients": _clean(dislikes),
        }
    )


def create_household_plan(
    *,
    db: Session,
    household: DBHousehold,
    owner: DBUser,
    request: HouseholdPlanRequest,
) -> HouseholdPlanResponse:
    members_query = db.query(DBHouseholdMember).filter(
        DBHouseholdMember.household_id == household.id
    )
    if not request.include_inactive_members:
        members_query = members_query.filter(DBHouseholdMember.active.is_(True))
    members = members_query.order_by(DBHouseholdMember.id).all()
    if not members:
        raise HTTPException(status_code=422, detail="Household has no active members")

    owner_profile = db_user_to_profile(owner)
    generator = PlanGenerator(db_session=db)
    aggregate_profile = _aggregate_hard_constraints(owner_profile, members)
    aggregate_target, target_summary = _aggregate_targets(
        db=db,
        members=members,
        owner_profile=owner_profile,
        health_engine=generator.health_engine,
    )
    candidates = generator._filter_valid_recipes(aggregate_profile)
    genome = generator.taste_engine.generate_flavor_genome(owner_profile)
    pantry_intervals = usable_pantry_intervals(db, household.id)

    availability: Dict[str, float] = {}
    for recipe in candidates:
        keys = list(generator._recipe_ingredient_keys(recipe))
        availability[recipe.id] = ingredient_availability_score(keys, pantry_intervals)

    try:
        optimized = optimize_household_horizon(
            recipes=candidates,
            days=request.days,
            meal_slots=generator.MEAL_SLOTS,
            daily_target=aggregate_target,
            preference_score=lambda recipe: generator.taste_engine.predict_hedonic_score(recipe, genome),
            pantry_score=lambda recipe: availability[recipe.id],
            ingredient_keys=generator._recipe_ingredient_keys,
            beam_width=int(__import__("os").getenv("HOUSEHOLD_OPTIMIZER_BEAM_WIDTH", "64")),
            max_options_per_slot=int(__import__("os").getenv("HOUSEHOLD_OPTIMIZER_OPTIONS_PER_SLOT", "48")),
        )
    except OptimizationInfeasible as exc:
        raise InfeasiblePlanError(str(exc), diagnostics=exc.diagnostics) from exc

    selections_by_day: Dict[int, List[PlanSelection]] = defaultdict(list)
    for selection in optimized.selections:
        selections_by_day[selection.day].append(selection)

    daily_plans = []
    variety_engine = VarietyEngine(no_repeat_window=7)
    for day in range(1, request.days + 1):
        daily_plans.append(
            generator._build_daily_plan(
                day=day,
                selections=selections_by_day[day],
                target=aggregate_target,
                genome=genome,
                variety_engine=variety_engine,
            )
        )

    shopping_list = generator._generate_shopping_list(optimized.selections)
    summary = optimized.summary
    warnings = [
        "Hard restrictions and allergies from every included member were unioned before recipe selection.",
        "Unlinked members without explicit targets use the owner's calculated target scaled by their serving multiplier.",
        "Pantry availability influences recipe selection as an ordinal coverage objective; it is not represented as monetary savings.",
        "Inventory reservations are provisional and do not consume pantry stock until explicitly committed.",
        "Member-specific medical-condition compatibility is not clinically validated.",
    ]
    warnings.extend(summary.relaxations)
    plan_response = PlanResponse(
        user_id=owner.id,
        days=daily_plans,
        shopping_list=shopping_list,
        prep_timeline=generator._generate_prep_timeline(daily_plans),
        overall_stats=generator._calculate_overall_stats(daily_plans, aggregate_target),
        optimization=summary,
        warnings=warnings,
    )
    stored = DBMealPlan(
        user_id=owner.id,
        household_id=household.id,
        schema_version=CURRENT_PLAN_SCHEMA_VERSION,
        plan_data=plan_response.model_dump(mode="json"),
    )
    db.add(stored)
    db.commit()
    db.refresh(stored)

    reconciled = reconcile_shopping_list(
        plan_response, list_pantry_items(db, household.id)
    )
    reservations = []
    if request.reserve_inventory:
        reservations = create_plan_reservations(
            db,
            household=household,
            plan=stored,
            shopping=reconciled,
            reservation_hours=request.reservation_hours,
        )

    selected_scores = [availability[item.recipe.id] for item in optimized.selections]
    pantry_coverage = (
        sum(selected_scores) / len(selected_scores) if selected_scores else 0.0
    )
    diagnostics = {
        "active_member_ids": [member.id for member in members],
        "candidate_count_after_hard_filters": len(candidates),
        "pantry_ingredient_unit_pairs": len(pantry_intervals),
        "recipe_availability_scores": {
            key: round(value, 6) for key, value in sorted(availability.items())
        },
    }
    return HouseholdPlanResponse(
        household_id=household.id,
        plan_id=stored.id,
        plan_schema_version=CURRENT_PLAN_SCHEMA_VERSION,
        household_plan_schema_version=CURRENT_HOUSEHOLD_PLAN_SCHEMA_VERSION,
        plan=plan_response,
        target_summary=target_summary,
        pantry_coverage_score=round(pantry_coverage, 6),
        reservations=[ReservationView.model_validate(value) for value in reservations],
        warnings=warnings,
        diagnostics=diagnostics,
    )
