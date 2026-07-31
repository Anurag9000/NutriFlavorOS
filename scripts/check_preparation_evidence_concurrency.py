#!/usr/bin/env python3
"""PostgreSQL concurrency probe for preparation evidence registration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from typing import Callable

from backend.database import DBRecipe, SessionLocal
from backend.domain.preparation_evidence import RecipePreparationProfileInput
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.preparation_evidence_service import register_profile


RECIPE_ID = "ci-preparation-evidence-concurrency"


def _payload(version: str, *, notes: str | None = None, duration: int = 10):
    return RecipePreparationProfileInput.model_validate(
        {
            "recipe_id": RECIPE_ID,
            "profile_version": version,
            "schema_version": "1",
            "supported_servings_min": 1,
            "supported_servings_max": 4,
            "task_templates": [
                {
                    "template_id": "heat",
                    "name": "Heat fixture",
                    "duration_min_minutes": duration,
                    "duration_max_minutes": duration,
                    "resource_demands": {"burner": 1},
                    "dependencies": [],
                    "active_work": True,
                    "unattended_allowed": False,
                }
            ],
            "source_name": "PostgreSQL concurrency fixture",
            "source_url": f"https://example.test/{RECIPE_ID}/{version}",
            "source_version": version,
            "evidence_status": "reviewed",
            "reviewed_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "reviewed_by": "CI concurrency probe",
            "notes": notes,
            "active": True,
        }
    )


def _reset() -> None:
    with SessionLocal() as db:
        db.query(DBRecipePreparationProfile).filter(
            DBRecipePreparationProfile.recipe_id == RECIPE_ID
        ).delete(synchronize_session=False)
        db.query(DBRecipe).filter(DBRecipe.id == RECIPE_ID).delete(
            synchronize_session=False
        )
        db.add(
            DBRecipe(
                id=RECIPE_ID,
                name="Concurrency recipe",
                description="",
                ingredients=["water"],
                ingredient_data=[],
                servings=2,
                calories=100,
                macros={},
                flavor_profile={},
                tags=[],
                instructions=[],
                estimated_cost=1,
                nutrition_basis="per_serving",
            )
        )
        db.commit()


def _run_pair(
    left: Callable[[], object],
    right: Callable[[], object],
) -> list[tuple[str, object]]:
    barrier = Barrier(2)

    def execute(label: str, callback: Callable[[], object]):
        barrier.wait(timeout=10)
        try:
            return label, callback()
        except Exception as exc:  # probe captures expected conflict type/message
            return label, exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(execute, "left", left),
            pool.submit(execute, "right", right),
        ]
        return [future.result(timeout=30) for future in futures]


def _register(payload: RecipePreparationProfileInput):
    with SessionLocal() as db:
        return register_profile(db, payload)


def _assert_identical_retry_collapses() -> None:
    payload = _payload("identical-1")
    results = _run_pair(
        lambda: _register(payload),
        lambda: _register(payload),
    )
    values = [value for _, value in results]
    errors = [value for value in values if isinstance(value, Exception)]
    assert errors == [], errors
    identifiers = {value.id for value in values}
    hashes = {value.content_hash for value in values}
    assert len(identifiers) == 1
    assert len(hashes) == 1
    with SessionLocal() as db:
        rows = (
            db.query(DBRecipePreparationProfile)
            .filter(
                DBRecipePreparationProfile.recipe_id == RECIPE_ID,
                DBRecipePreparationProfile.profile_version == "identical-1",
            )
            .all()
        )
        assert len(rows) == 1


def _assert_contradictory_version_conflicts() -> None:
    results = _run_pair(
        lambda: _register(_payload("conflict-1", notes="left", duration=10)),
        lambda: _register(_payload("conflict-1", notes="right", duration=11)),
    )
    successes = [
        value for _, value in results if not isinstance(value, Exception)
    ]
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert len(successes) == 1, results
    assert len(errors) == 1, results
    assert isinstance(errors[0], ValueError)
    assert "different evidence content" in str(errors[0]) or "conflicted" in str(
        errors[0]
    )
    with SessionLocal() as db:
        rows = (
            db.query(DBRecipePreparationProfile)
            .filter(
                DBRecipePreparationProfile.recipe_id == RECIPE_ID,
                DBRecipePreparationProfile.profile_version == "conflict-1",
            )
            .all()
        )
        assert len(rows) == 1


def _assert_concurrent_new_versions_keep_one_active_review() -> None:
    results = _run_pair(
        lambda: _register(_payload("successor-a")),
        lambda: _register(_payload("successor-b")),
    )
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert errors == [], errors
    with SessionLocal() as db:
        rows = (
            db.query(DBRecipePreparationProfile)
            .filter(DBRecipePreparationProfile.recipe_id == RECIPE_ID)
            .order_by(DBRecipePreparationProfile.id)
            .all()
        )
        active = [
            value
            for value in rows
            if value.active and value.evidence_status == "reviewed"
        ]
        assert len(active) == 1
        assert active[0].profile_version in {"successor-a", "successor-b"}
        active_versions = {
            value.profile_version
            for value in rows
            if value.profile_version in {"successor-a", "successor-b"}
        }
        assert active_versions == {"successor-a", "successor-b"}
        superseded_new = [
            value
            for value in rows
            if value.profile_version in {"successor-a", "successor-b"}
            and not value.active
        ]
        assert len(superseded_new) == 1
        assert active[0].supersedes_profile_id == superseded_new[0].id


def main() -> int:
    _reset()
    try:
        _assert_identical_retry_collapses()
        _assert_contradictory_version_conflicts()
        _assert_concurrent_new_versions_keep_one_active_review()
        print("Preparation evidence PostgreSQL concurrency probe passed")
        return 0
    finally:
        with SessionLocal() as db:
            db.query(DBRecipePreparationProfile).filter(
                DBRecipePreparationProfile.recipe_id == RECIPE_ID
            ).delete(synchronize_session=False)
            db.query(DBRecipe).filter(DBRecipe.id == RECIPE_ID).delete(
                synchronize_session=False
            )
            db.commit()


if __name__ == "__main__":
    raise SystemExit(main())
