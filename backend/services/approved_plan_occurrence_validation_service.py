"""Fail-closed validation for occurrence documents derived from approved plans."""

from __future__ import annotations

from typing import Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.database import DBMealPlan
from backend.domain.household_plan_lifecycle import HouseholdPlanStatus
from backend.domain.preparation_operations import PreparationOccurrenceSetDocument
from backend.services.household_plan_occurrence_service import (
    get_approved_plan_occurrence_candidates,
)


def _conflict(code: str, message: str, **details) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": code, "message": message, **details},
    )


def _lock_source_plan(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
    expected_version: int,
) -> None:
    row = (
        db.query(DBMealPlan)
        .filter(
            DBMealPlan.id == plan_id,
            DBMealPlan.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if row is None or row.version != expected_version:
        raise _conflict(
            "source_plan_version_mismatch",
            "The source household plan is missing or its version changed",
        )
    if row.status != HouseholdPlanStatus.APPROVED.value:
        raise _conflict(
            "source_plan_not_approved",
            "Preparation occurrences must reference an approved household plan",
            current_status=row.status,
            current_version=row.version,
        )


def validate_occurrence_set_against_approved_plan(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
    expected_version: int,
    occurrence_set: PreparationOccurrenceSetDocument,
    lock: bool = True,
) -> None:
    """Prove that every occurrence belongs to the exact approved source plan.

    A confirmed occurrence document may intentionally contain only a subset of the
    approved plan because the household explicitly includes or excludes every
    candidate during confirmation. Confirmed servings, deadlines, and priorities
    are also household decisions and therefore are not forced back to the plan's
    original portion values here.

    What cannot change is the source household, source plan/version, occurrence
    identity, or recipe identity. Optional occurrence-level source references are
    accepted for compatibility, but when present they must exactly match the
    top-level source-plan evidence.
    """

    if occurrence_set.household_id != household_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "occurrence_household_mismatch",
                "message": "Occurrence document household does not match the route",
                "expected_household_id": household_id,
                "actual_household_id": occurrence_set.household_id,
            },
        )

    if lock:
        _lock_source_plan(
            db,
            household_id=household_id,
            plan_id=plan_id,
            expected_version=expected_version,
        )

    candidates_view = get_approved_plan_occurrence_candidates(
        db,
        household_id=household_id,
        plan_id=plan_id,
        expected_version=expected_version,
    )
    expected_recipe_by_occurrence: Dict[str, str] = {
        candidate.occurrence_id: candidate.recipe_id
        for candidate in candidates_view.candidates
    }

    unknown_occurrence_ids = []
    recipe_mismatches = []
    source_reference_mismatches = []
    for occurrence in occurrence_set.occurrences:
        expected_recipe_id = expected_recipe_by_occurrence.get(
            occurrence.occurrence_id
        )
        if expected_recipe_id is None:
            unknown_occurrence_ids.append(occurrence.occurrence_id)
        elif occurrence.recipe_id != expected_recipe_id:
            recipe_mismatches.append(
                {
                    "occurrence_id": occurrence.occurrence_id,
                    "expected_recipe_id": expected_recipe_id,
                    "actual_recipe_id": occurrence.recipe_id,
                }
            )

        if (
            occurrence.source_plan_id is not None
            and (
                occurrence.source_plan_id != plan_id
                or occurrence.source_plan_version != expected_version
            )
        ):
            source_reference_mismatches.append(
                {
                    "occurrence_id": occurrence.occurrence_id,
                    "expected_source_plan_id": plan_id,
                    "expected_source_plan_version": expected_version,
                    "actual_source_plan_id": occurrence.source_plan_id,
                    "actual_source_plan_version": occurrence.source_plan_version,
                }
            )

    if unknown_occurrence_ids or recipe_mismatches or source_reference_mismatches:
        raise _conflict(
            "approved_plan_occurrence_mismatch",
            (
                "Occurrence document is not an exact recipe-identity subset of "
                "the approved source plan"
            ),
            source_plan_id=plan_id,
            source_plan_version=expected_version,
            unknown_occurrence_ids=sorted(unknown_occurrence_ids),
            recipe_mismatches=sorted(
                recipe_mismatches,
                key=lambda value: value["occurrence_id"],
            ),
            source_reference_mismatches=sorted(
                source_reference_mismatches,
                key=lambda value: value["occurrence_id"],
            ),
        )
