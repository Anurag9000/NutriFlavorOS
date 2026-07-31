"""Preflight inspection for immutable preparation-evidence imports."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable, List

from sqlalchemy.orm import Session

from backend.database import DBRecipe
from backend.domain.preparation_evidence import (
    PreparationEvidenceStatus,
    RecipePreparationProfileInput,
)
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.preparation_evidence_service import profile_content_hash


@dataclass(frozen=True)
class PreparationImportPreview:
    recipe_id: str
    profile_version: str
    content_hash: str
    evidence_status: str
    active: bool
    planned_action: str
    existing_record_id: int | None
    supersedes_profile_id: int | None
    supersedes_profile_version: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_batch_shape(
    payloads: List[RecipePreparationProfileInput],
) -> None:
    keys = [(value.recipe_id, value.profile_version) for value in payloads]
    if len(keys) != len(set(keys)):
        raise ValueError(
            "Preparation import contains duplicate recipe_id/profile_version keys"
        )
    active_reviewed = Counter(
        value.recipe_id
        for value in payloads
        if value.active
        and value.evidence_status == PreparationEvidenceStatus.REVIEWED
    )
    ambiguous = sorted(
        recipe_id for recipe_id, count in active_reviewed.items() if count > 1
    )
    if ambiguous:
        raise ValueError(
            "A batch may contain at most one active reviewed version per recipe: "
            + ", ".join(ambiguous)
        )


def preflight_preparation_profiles(
    db: Session,
    payloads: Iterable[RecipePreparationProfileInput],
) -> List[PreparationImportPreview]:
    """Validate an import against current state without mutating it."""

    values = list(payloads)
    _validate_batch_shape(values)
    recipe_ids = sorted({value.recipe_id for value in values})
    known = {
        value[0]
        for value in db.query(DBRecipe.id)
        .filter(DBRecipe.id.in_(recipe_ids))
        .all()
    }
    unknown = sorted(set(recipe_ids) - known)
    if unknown:
        raise ValueError("Unknown recipe_id values: " + ", ".join(unknown))

    existing_rows = (
        db.query(DBRecipePreparationProfile)
        .filter(DBRecipePreparationProfile.recipe_id.in_(recipe_ids))
        .order_by(
            DBRecipePreparationProfile.recipe_id,
            DBRecipePreparationProfile.created_at.desc(),
            DBRecipePreparationProfile.id.desc(),
        )
        .all()
    )
    existing_by_key = {
        (value.recipe_id, value.profile_version): value
        for value in existing_rows
    }
    active_reviewed_by_recipe = {}
    for row in existing_rows:
        if (
            row.active
            and row.evidence_status == PreparationEvidenceStatus.REVIEWED.value
            and row.recipe_id not in active_reviewed_by_recipe
        ):
            active_reviewed_by_recipe[row.recipe_id] = row

    previews: List[PreparationImportPreview] = []
    for payload in sorted(
        values,
        key=lambda value: (value.recipe_id, value.profile_version),
    ):
        content_hash = profile_content_hash(payload)
        existing = existing_by_key.get(
            (payload.recipe_id, payload.profile_version)
        )
        if existing is not None:
            if existing.content_hash != content_hash:
                raise ValueError(
                    "Preparation profile version already exists with different "
                    f"evidence content: {payload.recipe_id}/{payload.profile_version}"
                )
            previews.append(
                PreparationImportPreview(
                    recipe_id=payload.recipe_id,
                    profile_version=payload.profile_version,
                    content_hash=content_hash,
                    evidence_status=payload.evidence_status.value,
                    active=payload.active,
                    planned_action="idempotent_existing",
                    existing_record_id=existing.id,
                    supersedes_profile_id=existing.supersedes_profile_id,
                    supersedes_profile_version=None,
                )
            )
            continue

        current = (
            active_reviewed_by_recipe.get(payload.recipe_id)
            if payload.active
            and payload.evidence_status == PreparationEvidenceStatus.REVIEWED
            else None
        )
        previews.append(
            PreparationImportPreview(
                recipe_id=payload.recipe_id,
                profile_version=payload.profile_version,
                content_hash=content_hash,
                evidence_status=payload.evidence_status.value,
                active=payload.active,
                planned_action=(
                    "register_and_supersede"
                    if current is not None
                    else "register"
                ),
                existing_record_id=None,
                supersedes_profile_id=current.id if current is not None else None,
                supersedes_profile_version=(
                    current.profile_version if current is not None else None
                ),
            )
        )
    return previews
