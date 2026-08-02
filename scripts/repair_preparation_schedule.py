#!/usr/bin/env python3
"""Generate a non-persisted deterministic preparation repair from strict JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from backend.domain.preparation_repair import PreparationScheduleRepairRequest
from backend.engines.prep_schedule_repair import (
    PreparationRepairError,
    repair_preparation_schedule,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a deterministic minimal-change preparation repair. "
            "The command never reads or writes the application database."
        )
    )
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        raw = json.loads(args.request.read_text(encoding="utf-8"))
        request = PreparationScheduleRepairRequest.model_validate(raw)
        result = repair_preparation_schedule(request)
        payload = {
            "document_version": "preparation-schedule-repair-result-v1",
            "status": "complete" if result.complete else "partial",
            "persistence": "not_persisted",
            "human_acceptance_required": True,
            "result": result.model_dump(mode="json"),
        }
        exit_code = 0
    except FileNotFoundError as exc:
        payload = {
            "document_version": "preparation-schedule-repair-error-v1",
            "status": "invalid_request",
            "error": {"code": "request_file_missing", "message": str(exc)},
        }
        exit_code = 2
    except json.JSONDecodeError as exc:
        payload = {
            "document_version": "preparation-schedule-repair-error-v1",
            "status": "invalid_request",
            "error": {
                "code": "request_json_invalid",
                "message": str(exc),
            },
        }
        exit_code = 2
    except ValidationError as exc:
        payload = {
            "document_version": "preparation-schedule-repair-error-v1",
            "status": "invalid_request",
            "error": {
                "code": "request_contract_invalid",
                "message": "Repair request failed strict validation",
                "details": exc.errors(include_url=False),
            },
        }
        exit_code = 2
    except PreparationRepairError as exc:
        payload = {
            "document_version": "preparation-schedule-repair-error-v1",
            "status": "repair_rejected",
            "error": exc.as_dict(),
        }
        exit_code = 3

    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
