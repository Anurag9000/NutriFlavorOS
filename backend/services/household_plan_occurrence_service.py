"""Derive preparation occurrences from exact approved household plans."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.domain.household_plan_occurrences import (
    ApprovedPlanOccurrenceCandidate,
    ApprovedPlanOccurrenceCandidatesView,
    ConfirmedPlanOccurrenceSetView,
    ConfirmPlanOccurrenceSetRequest,
    PreparationProfileAvailability,
)
from backend.domain.preparation_evidence import RecipePreparationOccurrence
from backend.domain.preparation_operations import PreparationOccurrenceSetDocument
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.household_plan_lifecycle_service import (
    assert_approved_source_plan,
    get_household_plan,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _occurrence_id(day: int, meal_slot: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.:-]+", "-", meal_slot.strip().lower())
    normalized = normalized.strip("-._:") or "meal"
    normalized = normalized[:80]
    digest = hashlib.sha256(meal_slot.encode("utf-8")).hexdigest()[:16]
    return f"day-{day}.{normalized}-{digest}"


def _active_reviewed_profiles(
    db: Session,
    recipe_ids: Iterable[str],
) -> Dict[str, DBRecipePreparationProfile]:
    identifiers = sorted(set(recipe_ids))
    if not identifiers:
        return {}
    rows = (
        db.query(DBRecipePreparationProfile)
        .filter(
            DBRecipePreparationProfile.recipe_id.in_(identifiers),
            DBRecipePreparationProfile.evidence_status == "reviewed",
            DBRecipePreparationProfile.active.is_(True),
        )
        .order_by(
            DBRecipePreparationProfile.recipe_id,
            DBRecipePreparationProfile.id,
        )
        .all()
    )
    return {value.recipe_id: value for value in rows}


def _profile_status(
    profile: DBRecipePreparationProfile | None,
    servings: float,
) -> PreparationProfileAvailability:
    if profile is None:
        return PreparationProfileAvailability.MISSING_REVIEWED_PROFILE
    if (
        servings < profile.supported_servings_min
        or servings > profile.supported_servings_max
    ):
        return PreparationProfileAvailability.REVIEWED_INCOMPATIBLE_SERVINGS
    return PreparationProfileAvailability.REVIEWED_COMPATIBLE


def _profile_version(profile: DBRecipePreparationProfile) -> str:
    return (
        f"profile:{profile.id}/version:{profile.profile_version}/"
        f"sha256:{profile.content_hash}"
    )


def _approved_plan(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
    expected_version: int,
):
    assert_approved_source_plan(
        db,
        household_id=household_id,
        source_plan_id=plan_id,
        source_plan_version=expected_version,
    )
    return get_household_plan(
        db,
        household_id=household_id,
        plan_id=plan_id,
    )


def _derive_candidate_rows(plan) -> List[Tuple[int, str, object, float, float]]:
    rows: List[Tuple[int, str, object, float, float]] = []
    occurrence_ids: set[str] = set()
    for day in sorted(plan.plan.days, key=lambda value: value.day):
        for meal_slot, recipe in sorted(day.meals.items()):
            multiplier = float(day.portions.get(meal_slot, 1.0))
            source_servings = float(recipe.servings)
            planned_servings = source_servings * multiplier
            if multiplier <= 0 or source_servings <= 0 or planned_servings > 1000:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "stored_plan_occurrence_invalid",
                        "message": (
                            "Stored plan contains a non-positive or unsupported "
                            "serving quantity"
                        ),
                        "day": day.day,
                        "meal_slot": meal_slot,
                        "recipe_id": recipe.id,
                    },
                )
            identifier = _occurrence_id(day.day, meal_slot)
            if identifier in occurrence_ids:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "stored_plan_occurrence_id_collision",
                        "message": (
                            "Stored plan meal slots cannot be mapped to unique "
                            "occurrence identifiers"
                        ),
                    },
                )
            occurrence_ids.add(identifier)
            rows.append(
                (
                    day.day,
                    meal_slot,
                    recipe,
                    multiplier,
                    planned_servings,
                )
            )
    if not rows:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "approved_plan_has_no_meals",
                "message": "Approved household plan contains no meal occurrences",
            },
        )
    return rows


def get_approved_plan_occurrence_candidates(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
    expected_version: int,
) -> ApprovedPlanOccurrenceCandidatesView:
    plan = _approved_plan(
        db,
        household_id=household_id,
        plan_id=plan_id,
        expected_version=expected_version,
    )
    rows = _derive_candidate_rows(plan)
    profiles = _active_reviewed_profiles(
        db,
        [recipe.id for _, _, recipe, _, _ in rows],
    )
    candidates: List[ApprovedPlanOccurrenceCandidate] = []
    compatible = 0
    for day, meal_slot, recipe, multiplier, planned_servings in rows:
        profile = profiles.get(recipe.id)
        status = _profile_status(profile, planned_servings)
        if status == PreparationProfileAvailability.REVIEWED_COMPATIBLE:
            compatible += 1
        warnings: List[str] = []
        if status == PreparationProfileAvailability.MISSING_REVIEWED_PROFILE:
            warnings.append(
                "No active reviewed preparation profile exists for this recipe"
            )
        elif (
            status
            == PreparationProfileAvailability.REVIEWED_INCOMPATIBLE_SERVINGS
        ):
            warnings.append(
                "Planned servings fall outside the active reviewed profile range"
            )
        candidates.append(
            ApprovedPlanOccurrenceCandidate(
                occurrence_id=_occurrence_id(day, meal_slot),
                day=day,
                meal_slot=meal_slot,
                recipe_id=recipe.id,
                recipe_name=recipe.name,
                source_recipe_servings=float(recipe.servings),
                planned_portion_multiplier=multiplier,
                planned_servings=planned_servings,
                preparation_profile_status=status,
                preparation_profile_id=profile.id if profile else None,
                preparation_profile_version=(
                    profile.profile_version if profile else None
                ),
                preparation_profile_content_hash=(
                    profile.content_hash if profile else None
                ),
                supported_servings_min=(
                    profile.supported_servings_min if profile else None
                ),
                supported_servings_max=(
                    profile.supported_servings_max if profile else None
                ),
                warnings=warnings,
            )
        )
    return ApprovedPlanOccurrenceCandidatesView(
        household_id=household_id,
        source_plan_id=plan_id,
        source_plan_version=expected_version,
        generated_at=_utcnow_iso(),
        candidates=candidates,
        reviewed_compatible_count=compatible,
        unresolved_profile_count=len(candidates) - compatible,
        warnings=[
            "Planned servings are derived from source recipe servings and the "
            "stored portion multiplier; the household must confirm them",
            "Required finish minutes are not inferred from meal-slot names and "
            "must be entered explicitly",
            "Candidate generation does not persist an occurrence document or "
            "create a preparation schedule",
        ],
    )


def confirm_approved_plan_occurrence_set(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
    payload: ConfirmPlanOccurrenceSetRequest,
) -> ConfirmedPlanOccurrenceSetView:
    candidates_view = get_approved_plan_occurrence_candidates(
        db,
        household_id=household_id,
        plan_id=plan_id,
        expected_version=payload.expected_plan_version,
    )
    candidates = {
        value.occurrence_id: value for value in candidates_view.candidates
    }
    confirmations = {
        value.occurrence_id: value for value in payload.confirmations
    }
    missing = sorted(set(candidates) - set(confirmations))
    unknown = sorted(set(confirmations) - set(candidates))
    if missing or unknown:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "occurrence_confirmation_set_mismatch",
                "message": (
                    "Every approved-plan candidate must be explicitly included "
                    "or excluded exactly once"
                ),
                "missing_occurrence_ids": missing,
                "unknown_occurrence_ids": unknown,
            },
        )

    included = [
        value for value in payload.confirmations if value.include
    ]
    recipe_ids = [candidates[value.occurrence_id].recipe_id for value in included]
    profiles = _active_reviewed_profiles(db, recipe_ids)
    unresolved: List[dict] = []
    occurrences: List[RecipePreparationOccurrence] = []
    profile_versions: Dict[str, str] = {}
    for confirmation in included:
        candidate = candidates[confirmation.occurrence_id]
        servings = float(confirmation.servings)
        profile = profiles.get(candidate.recipe_id)
        status = _profile_status(profile, servings)
        if status != PreparationProfileAvailability.REVIEWED_COMPATIBLE:
            unresolved.append(
                {
                    "occurrence_id": candidate.occurrence_id,
                    "recipe_id": candidate.recipe_id,
                    "servings": servings,
                    "reason_code": status.value,
                    "supported_servings_min": (
                        profile.supported_servings_min if profile else None
                    ),
                    "supported_servings_max": (
                        profile.supported_servings_max if profile else None
                    ),
                }
            )
            continue
        occurrences.append(
            RecipePreparationOccurrence(
                occurrence_id=candidate.occurrence_id,
                recipe_id=candidate.recipe_id,
                required_finish_minute=int(
                    confirmation.required_finish_minute
                ),
                servings=servings,
                priority=confirmation.priority,
            )
        )
        profile_versions[candidate.recipe_id] = _profile_version(profile)

    if unresolved:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "confirmed_occurrence_profile_unavailable",
                "message": (
                    "Every included occurrence requires an active reviewed "
                    "preparation profile compatible with confirmed servings"
                ),
                "unresolved": unresolved,
            },
        )

    document = PreparationOccurrenceSetDocument(
        household_id=household_id,
        occurrence_set_version=payload.occurrence_set_version,
        duration_policy=payload.duration_policy,
        occurrences=occurrences,
    )
    return ConfirmedPlanOccurrenceSetView(
        household_id=household_id,
        source_plan_id=plan_id,
        source_plan_version=payload.expected_plan_version,
        occurrence_set=document,
        profile_versions=dict(sorted(profile_versions.items())),
        confirmed_count=len(occurrences),
        excluded_count=len(payload.confirmations) - len(occurrences),
        warnings=[
            "This confirmed occurrence document is not persisted and does not "
            "create or approve a preparation schedule",
            "The active reviewed resource calendar and deterministic scheduler "
            "must still be selected and reviewed",
        ],
    )
