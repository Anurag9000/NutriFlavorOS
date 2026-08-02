from __future__ import annotations

from pathlib import Path

from backend.services import preparation_operations_coverage_service
from backend.services import preparation_task_completion_service


def _assert_package_entrypoint(module, expected_directory: str, symbol: str):
    path = Path(module.__file__).resolve()
    assert path.name == "__init__.py"
    assert path.parent.name == expected_directory
    assert callable(getattr(module, symbol))


def test_completion_service_resolves_authoritative_package():
    _assert_package_entrypoint(
        preparation_task_completion_service,
        "preparation_task_completion_service",
        "complete_schedule_with_execution_guard",
    )


def test_coverage_service_resolves_authoritative_package():
    _assert_package_entrypoint(
        preparation_operations_coverage_service,
        "preparation_operations_coverage_service",
        "get_preparation_operations_coverage",
    )
