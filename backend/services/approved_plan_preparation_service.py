"""Compile confirmed approved-plan occurrences against a reviewed calendar."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.database import DBMealPlan
from backend.domain.approved_plan_preparation import (
    ApprovedPlanPreparationCompileRequest,
    ApprovedPlanPreparationCompileView,
    ReviewedPreparationTaskTemplate,
)
from backend.domain.household_plan_lifecycle import HouseholdPlanStatus
from backend.domain.preparation import (
    PreparationResource,
    PreparationScheduleRequest,
    PreparationTask,
)
from backend.domain.preparation_evidence import DurationPolicy
from backend.domain.preparation_operations import CalendarEvidenceStatus
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.approved_plan_occurrence_validation_service import (
    validate_occurrence_set_against_approved_plan,
)
from backend.services.preparation_operations_service import get_resource_calendar


PROFILE_IDENTITY_PATTERN = re.compile(
    r"^profile:(?P<profile_id>[1-9][0-9]*)/"
    r"version:(?P<version>[^/]+)/sha256:(?P<sha256>[a-f0-9]{64})$"
)


def _conflict(code: str, message: str, **details) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": code, "message": message, **details},
    )


def _lock_approved_plan(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
    expected_version: int,
) -> DBMealPlan:
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
            "Preparation compilation requires an approved household plan",
            current_status=row.status,
            current_version=row.version,
        )
    return row


def _parse_profile_identities(
    values: Dict[str, str],
) -> Dict[str, Tuple[int, str, str]]:
    parsed: Dict[str, Tuple[int, str, str]] = {}
    for recipe_id, identity in values.items():
        match = PROFILE_IDENTITY_PATTERN.fullmatch(identity)
        if not match:
            raise _conflict(
                "preparation_profile_identity_invalid",
                "Preparation profile identity is malformed",
                recipe_id=recipe_id,
            )
        parsed[recipe_id] = (
            int(match.group("profile_id")),
            match.group("version"),
            match.group("sha256"),
        )
    return parsed


def _load_profiles(
    db: Session,
    identities: Dict[str, Tuple[int, str, str]],
) -> Dict[str, DBRecipePreparationProfile]:
    rows = (
        db.query(DBRecipePreparationProfile)
        .filter(
            DBRecipePreparationProfile.id.in_(
                sorted(value[0] for value in identities.values())
            )
        )
        .all()
    )
    by_id = {value.id: value for value in rows}
    profiles: Dict[str, DBRecipePreparationProfile] = {}
    drift: List[dict] = []
    for recipe_id, (profile_id, version, content_hash) in identities.items():
        row = by_id.get(profile_id)
        if (
            row is None
            or row.recipe_id != recipe_id
            or row.profile_version != version
            or row.content_hash != content_hash
            or row.evidence_status != "reviewed"
            or not row.active
        ):
            drift.append(
                {
                    "recipe_id": recipe_id,
                    "expected_profile_id": profile_id,
                    "expected_version": version,
                    "expected_content_hash": content_hash,
                    "current_profile_id": row.id if row else None,
                    "current_version": row.profile_version if row else None,
                    "current_content_hash": row.content_hash if row else None,
                    "current_status": row.evidence_status if row else None,
                    "current_active": bool(row.active) if row else None,
                }
            )
            continue
        profiles[recipe_id] = row
    if drift:
        raise _conflict(
            "preparation_profile_version_mismatch",
            "One or more confirmed preparation profile identities are no longer active and exact",
            drift=drift,
        )
    return profiles


def _task_id(occurrence_id: str, template_id: str) -> str:
    raw = f"{occurrence_id}:{template_id}"
    if len(raw) <= 160 and re.fullmatch(r"[A-Za-z0-9_.:-]+", raw):
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    prefix = re.sub(r"[^A-Za-z0-9_.:-]+", "-", raw).strip("-._:")
    prefix = prefix[:134] or "preparation-task"
    return f"{prefix}:{digest}"


def _calendar_resources(calendar) -> List[PreparationResource]:
    resources: List[PreparationResource] = []
    for value in sorted(calendar.resources, key=lambda item: item.resource_id):
        resources.append(
            PreparationResource(
                resource_id=value.resource_id,
                label=value.label,
                capacity=value.capacity,
                availability_windows=[
                    {
                        "start_minute": window.start_minute,
                        "end_minute": window.end_minute,
                    }
                    for window in value.availability_windows
                ],
            )
        )
    return resources


def _compile_tasks(
    *,
    request: ApprovedPlanPreparationCompileRequest,
    profiles: Dict[str, DBRecipePreparationProfile],
) -> List[PreparationTask]:
    tasks: List[PreparationTask] = []
    profile_failures: List[dict] = []
    for occurrence in request.occurrence_set.occurrences:
        profile = profiles[occurrence.recipe_id]
        if (
            occurrence.servings < profile.supported_servings_min
            or occurrence.servings > profile.supported_servings_max
        ):
            profile_failures.append(
                {
                    "occurrence_id": occurrence.occurrence_id,
                    "recipe_id": occurrence.recipe_id,
                    "servings": occurrence.servings,
                    "supported_servings_min": profile.supported_servings_min,
                    "supported_servings_max": profile.supported_servings_max,
                }
            )
            continue
        try:
            templates = [
                ReviewedPreparationTaskTemplate.model_validate(value)
                for value in profile.task_templates
            ]
        except Exception as exc:
            raise _conflict(
                "reviewed_preparation_profile_invalid",
                "A stored reviewed preparation profile cannot be compiled",
                recipe_id=occurrence.recipe_id,
                profile_id=profile.id,
                error=str(exc),
            ) from exc
        template_ids = [value.template_id for value in templates]
        if len(template_ids) != len(set(template_ids)):
            raise _conflict(
                "reviewed_preparation_profile_invalid",
                "A reviewed profile contains duplicate task-template IDs",
                recipe_id=occurrence.recipe_id,
                profile_id=profile.id,
            )
        unknown_dependencies = sorted(
            {
                dependency
                for template in templates
                for dependency in template.dependencies
                if dependency not in set(template_ids)
            }
        )
        if unknown_dependencies:
            raise _conflict(
                "reviewed_preparation_profile_invalid",
                "A reviewed profile references unknown task-template dependencies",
                recipe_id=occurrence.recipe_id,
                profile_id=profile.id,
                unknown_dependencies=unknown_dependencies,
            )
        task_ids = {
            template.template_id: _task_id(
                occurrence.occurrence_id,
                template.template_id,
            )
            for template in templates
        }
        for template in sorted(templates, key=lambda value: value.template_id):
            duration = (
                template.duration_max_minutes
                if request.occurrence_set.duration_policy
                == DurationPolicy.CONSERVATIVE_MAX
                else template.duration_min_minutes
            )
            tasks.append(
                PreparationTask(
                    task_id=task_ids[template.template_id],
                    duration_minutes=duration,
                    earliest_start_minute=0,
                    latest_finish_minute=occurrence.required_finish_minute,
                    priority=occurrence.priority,
                    resource_demands=template.resource_demands,
                    dependencies=[
                        task_ids[value] for value in template.dependencies
                    ],
                    metadata={
                        "occurrence_id": occurrence.occurrence_id,
                        "recipe_id": occurrence.recipe_id,
                        "servings": occurrence.servings,
                        "profile_id": profile.id,
                        "profile_version": profile.profile_version,
                        "profile_content_hash": profile.content_hash,
                        "duration_min_minutes": template.duration_min_minutes,
                        "duration_max_minutes": template.duration_max_minutes,
                        "duration_policy": request.occurrence_set.duration_policy.value,
                        "template_id": template.template_id,
                        "template_name": template.name,
                        "active_work": template.active_work,
                        "unattended_allowed": template.unattended_allowed,
                        "notes": template.notes,
                    },
                )
            )
    if profile_failures:
        raise _conflict(
            "confirmed_occurrence_profile_unavailable",
            "Confirmed servings fall outside reviewed preparation profile ranges",
            unresolved=profile_failures,
        )
    return tasks


def compile_approved_plan_preparation(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
    payload: ApprovedPlanPreparationCompileRequest,
) -> ApprovedPlanPreparationCompileView:
    if payload.occurrence_set.household_id != household_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "occurrence_household_mismatch",
                "message": "Occurrence document household does not match the route",
            },
        )
    _lock_approved_plan(
        db,
        household_id=household_id,
        plan_id=plan_id,
        expected_version=payload.expected_plan_version,
    )
    validate_occurrence_set_against_approved_plan(
        db,
        household_id=household_id,
        plan_id=plan_id,
        expected_version=payload.expected_plan_version,
        occurrence_set=payload.occurrence_set,
        lock=False,
    )
    calendar = get_resource_calendar(
        db,
        household_id=household_id,
        calendar_id=payload.calendar_version_id,
    )
    if (
        not calendar.active
        or calendar.evidence_status != CalendarEvidenceStatus.REVIEWED
    ):
        raise _conflict(
            "resource_calendar_not_active_reviewed",
            "Preparation compilation requires the active reviewed household calendar",
            calendar_version_id=calendar.id,
            current_active=calendar.active,
            current_status=calendar.evidence_status.value,
        )

    identities = _parse_profile_identities(payload.profile_versions)
    profiles = _load_profiles(db, identities)
    tasks = _compile_tasks(request=payload, profiles=profiles)
    schedule_request = PreparationScheduleRequest(
        horizon_minutes=calendar.horizon_minutes,
        granularity_minutes=payload.granularity_minutes,
        resources=_calendar_resources(calendar),
        tasks=tasks,
    )
    schedule_response = build_preparation_schedule(schedule_request)
    partial = bool(schedule_response.unscheduled)
    execution_status = "complete" if not partial else "partial_unscheduled"
    warnings = [
        "Compilation and deterministic scheduling are non-persisted until a separate operations handoff is reviewed",
        "Plan, profile, and calendar versions are rechecked again during schedule persistence and approval",
    ]
    if partial:
        reason_counts: Dict[str, int] = defaultdict(int)
        for value in schedule_response.unscheduled:
            reason_counts[value.reason_code] += 1
        warnings.append(
            "Unscheduled work remains: "
            + ", ".join(
                f"{key}={reason_counts[key]}" for key in sorted(reason_counts)
            )
        )
    return ApprovedPlanPreparationCompileView(
        household_id=household_id,
        source_plan_id=plan_id,
        source_plan_version=payload.expected_plan_version,
        calendar_version_id=calendar.id,
        calendar_version=calendar.calendar_version,
        calendar_content_hash=calendar.content_hash,
        occurrence_set=payload.occurrence_set,
        profile_versions=payload.profile_versions,
        schedule_request=schedule_request,
        schedule_response=schedule_response,
        partial=partial,
        execution_status=execution_status,
        warnings=warnings,
    )
