"""Persistence and conservative compilation for preparation evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, List

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
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


def profile_content_hash(payload: RecipePreparationProfileInput) -> str:
    """Hash immutable evidence content, excluding lifecycle activation state."""

    canonical = {
        "recipe_id": payload.recipe_id,
        "profile_version": payload.profile_version,
        "schema_version": payload.schema_version,
        "supported_servings_min": payload.supported_servings_min,
        "supported_servings_max": payload.supported_servings_max,
        "task_templates": [
            value.model_dump(mode="json") for value in payload.task_templates
        ],
        "source_name": payload.source_name,
        "source_url": payload.source_url,
        "source_version": payload.source_version,
        "evidence_status": payload.evidence_status.value,
        "reviewed_at": (
            payload.reviewed_at.isoformat() if payload.reviewed_at else None
        ),
        "reviewed_by": payload.reviewed_by,
        "notes": payload.notes,
    }
    raw = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _view(value: DBRecipePreparationProfile) -> RecipePreparationProfileView:
    return RecipePreparationProfileView(
        id=value.id,
        recipe_id=value.recipe_id,
        profile_version=value.profile_version,
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
        content_hash=value.content_hash,
        supersedes_profile_id=value.supersedes_profile_id,
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
    rows = query.order_by(
        DBRecipePreparationProfile.recipe_id,
        DBRecipePreparationProfile.created_at.desc(),
        DBRecipePreparationProfile.id.desc(),
    ).all()
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
    value = query.order_by(
        DBRecipePreparationProfile.active.desc(),
        DBRecipePreparationProfile.created_at.desc(),
        DBRecipePreparationProfile.id.desc(),
    ).first()
    if value is None:
        raise HTTPException(status_code=404, detail="Preparation profile not found")
    return _view(value)


def register_profile(
    db: Session,
    payload: RecipePreparationProfileInput,
) -> RecipePreparationProfileView:
    """Register one immutable evidence version and supersede prior active review."""

    if db.get(DBRecipe, payload.recipe_id) is None:
        raise ValueError(f"Unknown recipe_id: {payload.recipe_id}")
    content_hash = profile_content_hash(payload)
    existing = (
        db.query(DBRecipePreparationProfile)
        .filter(
            DBRecipePreparationProfile.recipe_id == payload.recipe_id,
            DBRecipePreparationProfile.profile_version
            == payload.profile_version,
        )
        .with_for_update()
        .first()
    )
    if existing is not None:
        if existing.content_hash == content_hash:
            return _view(existing)
        raise ValueError(
            "Preparation profile version already exists with different evidence content"
        )

    supersedes = None
    now = utcnow()
    if (
        payload.active
        and payload.evidence_status == PreparationEvidenceStatus.REVIEWED
    ):
        current = (
            db.query(DBRecipePreparationProfile)
            .filter(
                DBRecipePreparationProfile.recipe_id == payload.recipe_id,
                DBRecipePreparationProfile.evidence_status
                == PreparationEvidenceStatus.REVIEWED.value,
                DBRecipePreparationProfile.active.is_(True),
            )
            .order_by(
                DBRecipePreparationProfile.created_at.desc(),
                DBRecipePreparationProfile.id.desc(),
            )
            .with_for_update()
            .first()
        )
        if current is not None:
            current.active = False
            current.updated_at = now
            supersedes = current.id
            db.add(current)

    value = DBRecipePreparationProfile(
        recipe_id=payload.recipe_id,
        profile_version=payload.profile_version,
        schema_version=payload.schema_version,
        supported_servings_min=payload.supported_servings_min,
        supported_servings_max=payload.supported_servings_max,
        task_templates=[
            item.model_dump(mode="json") for item in payload.task_templates
        ],
        source_name=payload.source_name,
        source_url=payload.source_url,
        source_version=payload.source_version,
        evidence_status=payload.evidence_status.value,
        reviewed_at=payload.reviewed_at,
        reviewed_by=payload.reviewed_by,
        notes=payload.notes,
        content_hash=content_hash,
        supersedes_profile_id=supersedes,
        active=payload.active,
        created_at=now,
        updated_at=now,
    )
    db.add(value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        winner = (
            db.query(DBRecipePreparationProfile)
            .filter(
                DBRecipePreparationProfile.recipe_id == payload.recipe_id,
                DBRecipePreparationProfile.profile_version
                == payload.profile_version,
            )
            .first()
        )
        if winner is not None and winner.content_hash == content_hash:
            return _view(winner)
        raise ValueError(
            "Preparation profile registration conflicted with concurrent evidence state"
        ) from exc
    db.refresh(value)
    return _view(value)


def upsert_profile(
    db: Session,
    payload: RecipePreparationProfileInput,
) -> RecipePreparationProfileView:
    """Backward-compatible name for immutable registration."""

    return register_profile(db, payload)


def upsert_profiles(
    db: Session,
    payloads: Iterable[RecipePreparationProfileInput],
) -> List[RecipePreparationProfileView]:
    values = list(payloads)
    keys = [(value.recipe_id, value.profile_version) for value in values]
    if len(keys) != len(set(keys)):
        raise ValueError(
            "Preparation import contains duplicate recipe_id/profile_version keys"
        )
    return [register_profile(db, payload) for payload in values]


def build_tasks_from_profiles(
    db: Session,
    request: BuildPreparationTasksRequest,
) -> BuildPreparationTasksResponse:
    recipe_ids = sorted({value.recipe_id for value in request.occurrences})
    all_rows = (
        db.query(DBRecipePreparationProfile)
        .filter(DBRecipePreparationProfile.recipe_id.in_(recipe_ids))
        .order_by(
            DBRecipePreparationProfile.recipe_id,
            DBRecipePreparationProfile.active.desc(),
            DBRecipePreparationProfile.created_at.desc(),
            DBRecipePreparationProfile.id.desc(),
        )
        .all()
    )
    rows_by_recipe = {}
    for value in all_rows:
        rows_by_recipe.setdefault(value.recipe_id, []).append(value)

    tasks: List[PreparationTask] = []
    unresolved: List[UnresolvedPreparationOccurrence] = []
    profile_versions = {}
    warnings = []

    for occurrence in sorted(
        request.occurrences,
        key=lambda value: value.occurrence_id,
    ):
        candidates = rows_by_recipe.get(occurrence.recipe_id, [])
        if not candidates:
            unresolved.append(
                UnresolvedPreparationOccurrence(
                    occurrence_id=occurrence.occurrence_id,
                    recipe_id=occurrence.recipe_id,
                    reason_code="profile_missing",
                    message="No preparation evidence profile exists for this recipe",
                )
            )
            continue
        active = [value for value in candidates if value.active]
        if not active:
            unresolved.append(
                UnresolvedPreparationOccurrence(
                    occurrence_id=occurrence.occurrence_id,
                    recipe_id=occurrence.recipe_id,
                    reason_code="profile_inactive",
                    message="All preparation evidence profiles for this recipe are inactive",
                )
            )
            continue
        eligible = (
            [
                value
                for value in active
                if value.evidence_status
                == PreparationEvidenceStatus.REVIEWED.value
            ]
            if request.reviewed_only
            else active
        )
        if not eligible:
            unresolved.append(
                UnresolvedPreparationOccurrence(
                    occurrence_id=occurrence.occurrence_id,
                    recipe_id=occurrence.recipe_id,
                    reason_code="profile_not_reviewed",
                    message="Only reviewed preparation evidence may be compiled",
                )
            )
            continue
        profile = eligible[0]
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
                        "profile_version": profile.profile_version,
                        "profile_schema_version": profile.schema_version,
                        "profile_content_hash": profile.content_hash,
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
            f"profile:{profile.id}/version:{profile.profile_version}/"
            f"schema:{profile.schema_version}/source:{profile.source_version}/"
            f"sha256:{profile.content_hash}"
        )

    if request.duration_policy == DurationPolicy.OPTIMISTIC_MIN:
        warnings.append(
            "Optimistic minimum durations are intended for sensitivity analysis, not conservative operational scheduling."
        )
    if any(
        task.metadata.get("unattended_allowed") is None for task in tasks
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
