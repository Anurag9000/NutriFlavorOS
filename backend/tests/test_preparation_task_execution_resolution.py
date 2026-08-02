from __future__ import annotations

from pathlib import Path

from backend.services import preparation_task_execution_authoritative_service


def test_task_execution_authority_resolves_package_entrypoint():
    path = Path(preparation_task_execution_authoritative_service.__file__).resolve()
    assert path.name == "__init__.py"
    assert path.parent.name == "preparation_task_execution_authoritative_service"
    assert callable(
        preparation_task_execution_authoritative_service.validate_task_execution_snapshot
    )
    assert callable(
        preparation_task_execution_authoritative_service.get_task_execution_overview
    )
    assert callable(
        preparation_task_execution_authoritative_service.record_task_execution_event
    )
