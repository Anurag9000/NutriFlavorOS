from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from backend.api import preparation_operations_routes


def test_operations_routes_resolve_authoritative_package():
    path = Path(preparation_operations_routes.__file__).resolve()
    assert path.name == "__init__.py"
    assert path.parent.name == "preparation_operations_routes"
    assert preparation_operations_routes.router is not None


def test_source_linked_persistence_validates_exact_plan_occurrence_membership(
    monkeypatch,
):
    calls: list[tuple[str, dict]] = []
    payload = SimpleNamespace(
        source_plan_id=42,
        source_plan_version=2,
        occurrence_set=object(),
    )
    user = SimpleNamespace(id="editor@example.test")

    monkeypatch.setattr(
        preparation_operations_routes,
        "_access",
        lambda *args, **kwargs: calls.append(("access", kwargs)),
    )
    monkeypatch.setattr(
        preparation_operations_routes,
        "validate_occurrence_set_against_approved_plan",
        lambda *args, **kwargs: calls.append(("validate", kwargs)),
    )
    monkeypatch.setattr(
        preparation_operations_routes,
        "assert_approved_source_plan",
        lambda *args, **kwargs: calls.append(("assert", kwargs)),
    )
    monkeypatch.setattr(
        preparation_operations_routes,
        "create_persisted_schedule",
        lambda *args, **kwargs: calls.append(("create", kwargs)) or "created",
    )

    result = preparation_operations_routes.create_persisted_schedule_route(
        household_id="home-1",
        payload=payload,
        db=object(),
        current_user=user,
    )

    assert result == "created"
    validation = next(value for name, value in calls if name == "validate")
    assert validation == {
        "household_id": "home-1",
        "plan_id": 42,
        "expected_version": 2,
        "occurrence_set": payload.occurrence_set,
        "lock": False,
    }
    assert not any(name == "assert" for name, _ in calls)
    creation = next(value for name, value in calls if name == "create")
    assert creation["household_id"] == "home-1"
    assert creation["actor_user_id"] == user.id
    assert creation["payload"] is payload


def test_unlinked_persistence_preserves_pair_validation(monkeypatch):
    calls: list[tuple[str, dict]] = []
    payload = SimpleNamespace(
        source_plan_id=None,
        source_plan_version=None,
        occurrence_set=object(),
    )
    user = SimpleNamespace(id="editor@example.test")

    monkeypatch.setattr(preparation_operations_routes, "_access", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        preparation_operations_routes,
        "validate_occurrence_set_against_approved_plan",
        lambda *args, **kwargs: calls.append(("validate", kwargs)),
    )
    monkeypatch.setattr(
        preparation_operations_routes,
        "assert_approved_source_plan",
        lambda *args, **kwargs: calls.append(("assert", kwargs)),
    )
    monkeypatch.setattr(
        preparation_operations_routes,
        "create_persisted_schedule",
        lambda *args, **kwargs: "created",
    )

    assert preparation_operations_routes.create_persisted_schedule_route(
        household_id="home-1",
        payload=payload,
        db=object(),
        current_user=user,
    ) == "created"
    assert not any(name == "validate" for name, _ in calls)
    pair = next(value for name, value in calls if name == "assert")
    assert pair == {
        "household_id": "home-1",
        "source_plan_id": None,
        "source_plan_version": None,
    }
