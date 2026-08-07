#!/usr/bin/env python3
"""Validate lowest-layer preparation schedule completion authority."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MODULE = "backend.services.preparation_operations_service"
IMPLEMENTATION_MODULE = "backend.services.preparation_operations_service_impl"
PUBLIC_FILE = ROOT / "backend/services/preparation_operations_service.py"
IMPLEMENTATION_FILE = ROOT / "backend/services/preparation_operations_service_impl.py"
COMPLETION_SERVICE = ROOT / "backend/services/preparation_task_completion_service.py"
ROUTES = ROOT / "backend/api/preparation_operations_routes.py"
DIRECT_TEST = ROOT / "backend/tests/test_preparation_operations_service.py"
PRESERVED_TESTS = ROOT / "backend/tests/preparation_operations_service_cases.py"
POSTGRES_FIXTURE = ROOT / "backend/tests/postgres_preparation_fixture.py"
POSTGRES_TEST = ROOT / "backend/tests/test_preparation_schedule_completion_postgres.py"


def _read(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        errors.append(f"missing completion-authority file: {path.relative_to(ROOT)}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=str(path.relative_to(ROOT)))
    return source


def _scan_implementation_imports(errors: list[str]) -> int:
    inspected = 0
    allowed = {PUBLIC_FILE}
    for base in [ROOT / "backend/api", ROOT / "backend/services"]:
        for path in sorted(base.rglob("*.py")):
            if path in allowed or path == IMPLEMENTATION_FILE:
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path.relative_to(ROOT)))
            inspected += 1
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == IMPLEMENTATION_MODULE
                ):
                    errors.append(
                        f"{path.relative_to(ROOT)} imports compatibility implementation directly"
                    )
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == IMPLEMENTATION_MODULE:
                            errors.append(
                                f"{path.relative_to(ROOT)} imports compatibility implementation directly"
                            )
    return inspected


def validate_completion_authority() -> dict:
    errors: list[str] = []
    public_source = _read(PUBLIC_FILE, errors)
    implementation_source = _read(IMPLEMENTATION_FILE, errors)
    completion_source = _read(COMPLETION_SERVICE, errors)
    route_source = _read(ROUTES, errors)
    direct_test_source = _read(DIRECT_TEST, errors)
    preserved_test_source = _read(PRESERVED_TESTS, errors)
    postgres_fixture_source = _read(POSTGRES_FIXTURE, errors)
    postgres_test_source = _read(POSTGRES_TEST, errors)

    required_public = {
        "preparation_operations_service_impl as _impl",
        "def _assert_completion_authority",
        "event_type != PreparationScheduleEventType.COMPLETED",
        "existing_event =",
        "schedule.version != payload.expected_version",
        "schedule.status != PreparationScheduleStatus.APPROVED.value",
        "from backend.services.preparation_task_execution_service import",
        "assert_schedule_tasks_terminal(db, schedule=schedule)",
        "def transition_schedule",
        "return _original_transition_schedule(",
    }
    for fragment in sorted(required_public):
        if fragment not in public_source:
            errors.append(f"public transition facade lacks authority fragment: {fragment}")

    for fragment in {
        "def transition_schedule",
        "PreparationScheduleEventType.COMPLETED",
        "schedule.status = target.value",
    }:
        if fragment not in implementation_source:
            errors.append(f"preserved transition implementation lacks: {fragment}")

    required_wrapper = {
        "def complete_schedule_with_execution_guard",
        "return transition_schedule(",
        "PreparationScheduleEventType.COMPLETED",
        "lowest authoritative transition layer",
    }
    for fragment in sorted(required_wrapper):
        if fragment not in completion_source:
            errors.append(f"completion compatibility service lacks: {fragment}")
    for forbidden in {
        "assert_schedule_tasks_terminal",
        "DBPersistedPreparationSchedule",
        "_lock_household",
        ".with_for_update()",
    }:
        if forbidden in completion_source:
            errors.append(
                f"completion compatibility service duplicates authority: {forbidden}"
            )

    for fragment in {
        "complete_schedule_with_execution_guard",
        '"/schedules/{schedule_id}/complete"',
        "HouseholdRole.EDITOR",
    }:
        if fragment not in route_source:
            errors.append(f"completion route lacks protected fragment: {fragment}")

    required_test = {
        "test_transitions_are_optimistic_idempotent_and_terminal",
        "Direct low-level completion must fail closed",
        'exc.value.detail["code"] == "schedule_tasks_not_terminal"',
        "record_task_execution_event(",
        "completion_retry = transition_schedule(",
    }
    for fragment in sorted(required_test):
        if fragment not in direct_test_source:
            errors.append(f"direct transition regression lacks: {fragment}")
    if "test_transitions_are_optimistic_idempotent_and_terminal" not in preserved_test_source:
        errors.append("preserved historical test corpus is incomplete")

    # PostgreSQL CI runs against the exact Alembic-reviewed schema. The fixture
    # must therefore preserve migrated DDL and reset rows only; Base.metadata
    # drop/create is intentionally forbidden because migration-owned tables may
    # sit outside the imported ORM metadata graph while still owning FKs.
    required_fixture = {
        'assert engine.dialect.name == "postgresql"',
        "verify_runtime_schema()",
        "inspect(engine).get_table_names(schema=\"public\")",
        'table_name != "alembic_version"',
        "TRUNCATE TABLE",
        "RESTART IDENTITY CASCADE",
        "expire_on_commit=False",
    }
    for fragment in sorted(required_fixture):
        if fragment not in postgres_fixture_source:
            errors.append(f"PostgreSQL fixture lacks authority fragment: {fragment}")
    for forbidden in {
        "Base.metadata.drop_all(engine)",
        "Base.metadata.create_all(engine)",
    }:
        if forbidden in postgres_fixture_source:
            errors.append(
                f"PostgreSQL fixture rebuilds migrated schema instead of resetting data: {forbidden}"
            )

    for fragment in {
        "test_postgres_schedule_cannot_complete_ahead_of_final_task_event",
        "record_task_execution_event(",
        "transition_schedule(",
        'sum(value["kind"] == "schedule_completed" for value in results) == 0',
        '"schedule_tasks_not_terminal"',
        '"schedule_version_conflict"',
        "Complete only after the final task event committed",
    }:
        if fragment not in postgres_test_source:
            errors.append(f"PostgreSQL completion race lacks: {fragment}")

    inspected = _scan_implementation_imports(errors)

    return {
        "valid": not errors,
        "public_module": PUBLIC_MODULE,
        "implementation_module": IMPLEMENTATION_MODULE,
        "authority": "transition_schedule",
        "compatibility_entry_point": "complete_schedule_with_execution_guard",
        "postgres_race": True,
        "postgres_fixture_schema_authority": "alembic_reviewed_schema_data_reset_only",
        "inspected_product_file_count": inspected,
        "errors": errors,
    }


def main() -> int:
    report = validate_completion_authority()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
