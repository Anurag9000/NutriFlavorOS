from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_repair import PreparationScheduleRepairRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "repair_preparation_schedule.py"


def request(capacity: int) -> PreparationScheduleRequest:
    return PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 90,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": "person",
                    "capacity": capacity,
                    "label": "Available cook",
                    "availability_windows": [
                        {"start_minute": 0, "end_minute": 90}
                    ],
                }
            ],
            "tasks": [
                {
                    "task_id": "cli.a",
                    "duration_minutes": 10,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 60,
                    "priority": 1,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {},
                },
                {
                    "task_id": "cli.b",
                    "duration_minutes": 10,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 60,
                    "priority": 1,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {},
                },
            ],
        }
    )


def write_request(path: Path, *, immutable: list[str] | None = None) -> None:
    previous = request(2)
    revised = request(1)
    payload = PreparationScheduleRepairRequest(
        previous_request=previous,
        previous_response=build_preparation_schedule(previous),
        revised_request=revised,
        immutable_task_ids=immutable or [],
    )
    path.write_text(
        json.dumps(payload.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def test_cli_emits_non_persisted_typed_result(tmp_path):
    source = tmp_path / "request.json"
    output = tmp_path / "result.json"
    write_request(source)

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    stdout = json.loads(completed.stdout)
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert stdout == persisted
    assert stdout["document_version"] == "preparation-schedule-repair-result-v1"
    assert stdout["status"] == "complete"
    assert stdout["persistence"] == "not_persisted"
    assert stdout["human_acceptance_required"] is True
    assert stdout["result"]["complete"] is True
    assert stdout["result"]["objective"]["changed_task_count"] == 1


def test_cli_emits_machine_readable_repair_conflict(tmp_path):
    source = tmp_path / "request.json"
    write_request(source, immutable=["cli.a"])
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["revised_request"]["resources"][0]["availability_windows"] = [
        {"start_minute": 20, "end_minute": 90}
    ]
    source.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(source)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 3
    response = json.loads(completed.stdout)
    assert response["document_version"] == "preparation-schedule-repair-error-v1"
    assert response["status"] == "repair_rejected"
    assert response["error"]["code"] == "immutable_task_infeasible"
