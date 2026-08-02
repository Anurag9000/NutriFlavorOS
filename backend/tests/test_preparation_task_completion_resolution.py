from __future__ import annotations

from pathlib import Path

from backend.services import preparation_task_completion_service


def test_completion_import_resolves_authoritative_package_entrypoint():
    path = Path(preparation_task_completion_service.__file__).resolve()
    assert path.name == "__init__.py"
    assert path.parent.name == "preparation_task_completion_service"
    assert callable(
        preparation_task_completion_service.complete_schedule_with_execution_guard
    )
