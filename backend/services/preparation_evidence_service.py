"""Persistence and conservative compilation for preparation evidence."""

from __future__ import annotations

from typing import Iterable, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.database import DBRecipe, utcnow
from backend.domain.preparation import PreparationTask
from backend.domain.preparation_evidence import (
    BuildPreparationTasksRequest,
    BuildPreparationTasksResponse,
    DurationPolicy,
    PreparationEvidenceStatus,
    PreparationTaskTemplate,
    RecipePreparationProfileInput,
    RecipePreparationProfileView,
    UnresolvedPreparationOccurrence,
)
from backend.preparation_models import DBRecipePreparationProfile


def _view(value: DBRecipePreparationProfile) -> RecipePreparationProfileView:
    return RecipePreparationProfileView(
        id=value.id,
        recipe_id=value.recipe_id,
        schema_version=value.schema_version,
        supported_servings_min=value.supported_servings_min,
        supported_servings_max=value.supported_servings_max,
        task_templates=[
            PreparationTaskTemplate.model_validate(item)
            for item in list(value.task_templates or [])
        ],
        source_name=value.source_name,
        source_url=value.source_url,
        source_version=value.source_version,
        evidence_status=PreparationEvidenceStatus(value.evidence_status),
        reviewed_at=value.reviewed_at,
        reviewed_by=value.reviewed_by,
        notes=value.notes,
        active=value.active,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def list_profiles(
    db: Session,
    *,
    reviewed_only: bool = True,
    active_only: bool = True,
) -> List[RecipePreparationProfileView]:
    query = db.query(DBRecipePreparationProfile)
    if reviewed_only:
        query = query.filter(
            DBRecipePreparationProfile.evidence_status
            == PreparationEvidenceStatus.REVIEWED.value
        )
    if active_only:
        query = query.filter(DBRecipePreparationProfile.active.is_(True))
    rows = query.order_by(DBRecipePreparationProfile.recipe_id).all()
    return [_view(value) for value in rows]


def get_profile(
    db: Session,
    recipe_id: str,
    *,
    reviewed_only: bool = True,
) -> RecipePreparationProfileView:
    query = db.query(DBRecipePreparationProfile).filter(
        DBRecipePreparationProfile.recipe_id == recipe_id
    )
    if reviewed_only:
        query = query.filter(
            DBRecipePreparationProfile.evidence_status
            == PreparationEvidenceStatus.REVIEWED.value,
            DBRecipePreparationProfile.active.is_(True),
        )
    value = query.first()
    if value is None:
        raise HTTPException(status_code=404, detail="Preparation profile not found")
    return _view(value)


def upsert_profile(
    db: Session,
    payload: RecipePreparationProfileInput,
) -> RecipePreparationProfileView:
    if db.get(DBRecipe, payload.recipe_id) is None:
        raise ValueError(f"Unknown recipe_id: {payload.recipe_id}")
    value = (
        db.query(DBRecipePreparationProfile)
        .filter(DBRecipePreparationProfile.recipe_id == payload.recipe_id)
        .first()
    )
    now = utcnow()
    if value is None:
        value = DBRecipePreparationProfile(
            recipe_id=payload.recipe_id,
            created_at=now,
        )
    value.schema_version = payload.schema_version
    value.supported_servings_min = payload.supported_servings_min
    value.supported_servings_max = payload.supported_servings_max
    value.task_templates = [
        item.model_dump(mode="json") for item in payload.task_templates
    ]
    value.source_name = payload.source_name
    value.source_url = payload.source_url
    value.source_version = payload.source_version
    value.evidence_status = payload.evidence_status.value
    value.reviewed_at = payload.reviewed_at
    value.reviewed_by = payload.reviewed_by
    value.notes = payload.notes
    value.active = payload.active
    value.updated_at = now
    db.add(value)
    db.commit()
    db.refresh(value)
    return _view(value)


def upsert_profiles(
    db: Session,
    payloads: Iterable[RecipePreparationProfileInput],
) -> List[RecipePreparationProfileView]:
    return [upsert_profile(db, payload) for payload in payloads]


def build_tasks_from_profiles(
    db: Session,
    request: BuildPreparationTasksRequest,
) -> BuildPreparationTasksResponse:
    recipe_ids = sorted({value.recipe_id for value in request.occurrences})
    rows = (
        db.query(DBRecipePreparationProfile)
        .filter(DBRecipePreparationProfile.recipe_id.in_(recipe_ids))
        .all()
    )
    profiles = {value.recipe_id: value for value in rows}
    tasks: List[PreparationTask] = []
    unresolved: List[UnresolvedPreparationOccurrence] = []
    profile_versions = {}
    warnings = []

    for occurrence in sorted(request.occurrences, key=lambda value: value.occurrence_id):
        profile = profiles.get(occurrence.recipe_id)
        if profile is None:
            unresolved.append(
                UnresolvedPreparationOccurrence(
                    occurrence_id=occurrence.occurrence_id,
                    recipe_id=occurrence.recipe_id,
                    reason_code="profile_missing",
                    message="No preparation evidence profile exists for this recipe",
                )
            )
            continue
        if not profile.active:
            unresolved.append(
                UnresolvedPreparationOccurrence(
                    occurrence_id=occurrence.occurrence_id,
                    recipe_id=occurrence.recipe_id,
                    reason_code="profile_inactive",
                    message="The preparation evidence profile is inactive",
                )
            )
            continue
        if (
            request.reviewed_only
            and profile.evidence_status != PreparationEvidenceStatus.REVIEWED.value
        ):
            unresolved.append(
                UnresolvedPreparationOccurrence(
                    occurrence_id=occurrence.occurrence_id,
                    recipe_id=occurrence.recipe_id,
                    reason_code="profile_not_reviewed",
                    message="Only reviewed preparation evidence may be compiled",
                )
            )
            continue
        if not (
            float(profile.supported_servings_min)
            <= occurrence.servings
            <= float(profile.supported_servings_max)
        ):
            unresolved.append(
                UnresolvedPreparationOccurrence(
                    occurrence_id=occurrence.occurrence_id,
                    recipe_id=occurrence.recipe_id,
                    reason_code="servings_outside_reviewed_range",
                    message=(
                        f"Requested servings {occurrence.servings:g} are outside the "
                        f"reviewed range {profile.supported_servings_min:g}–"
                        f"{profile.supported_servings_max:g}"
                    ),
                )
            )
            continue

        templates = [
            PreparationTaskTemplate.model_validate(value)
            for value in list(profile.task_templates or [])
        ]
        namespace = occurrence.occurrence_id
        for template in templates:
            duration = (
                template.duration_max_minutes
                if request.duration_policy == DurationPolicy.CONSERVATIVE_MAX
                else template.duration_min_minutes
            )
            tasks.append(
                PreparationTask(
                    task_id=f"{namespace}.{template.template_id}",
                    duration_minutes=duration,
                    earliest_start_minute=0,
                    latest_finish_minute=occurrence.required_finish_minute,
                    priority=occurrence.priority,
                    resource_demands=dict(template.resource_demands),
                    dependencies=[
                        f"{namespace}.{value}" for value in template.dependencies
                    ],
                    metadata={
                        "recipe_id": occurrence.recipe_id,
                        "occurrence_id": occurrence.occurrence_id,
                        "servings": occurrence.servings,
                        "profile_id": profile.id,
                        "profile_schema_version": profile.schema_version,
                        "source_name": profile.source_name,
                        "source_url": profile.source_url,
                        "source_version": profile.source_version,
                        "evidence_status": profile.evidence_status,
                        "template_name": template.name,
                        "duration_min_minutes": template.duration_min_minutes,
                        "duration_max_minutes": template.duration_max_minutes,
                        "active_work": template.active_work,
                        "unattended_allowed": template.unattended_allowed,
                        "notes": template.notes,
                    },
                )
            )
        profile_versions[occurrence.recipe_id] = (
            f"profile:{profile.id}/schema:{profile.schema_version}/source:"
            f"{profile.source_version}"
        )

    if request.duration_policy == DurationPolicy.OPTIMISTIC_MIN:
        warnings.append(
            "Optimistic minimum durations are intended for sensitivity analysis, not conservative operational scheduling."
        )
    if any(
        task.metadata.get("unattended_allowed") is None
        for task in tasks
    ):
        warnings.append(
            "Some tasks do not declare unattended-cooking suitability; the scheduler does not infer it."
        )
    return BuildPreparationTasksResponse(
        tasks=tasks,
        unresolved=unresolved,
        profile_versions=profile_versions,
        duration_policy=request.duration_policy,
        warnings=warnings,
    )
