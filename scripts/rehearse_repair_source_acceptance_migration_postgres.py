#!/usr/bin/env python3
"""Rehearse migration 0018 over valid historical repair acceptance evidence.

Run ``seed`` while PostgreSQL is at revision 20260802_0017, upgrade with
Alembic, then run ``verify`` at 20260802_0018. Synthetic payload builders feed
production services; rows are never inserted by bypassing lifecycle APIs.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import (
    DBHousehold,
    DBUser,
    SessionLocal,
    engine,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_repair_proposal_acceptance_service import (
    accept_repair_proposal,
)
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_proposal_read_service import (
    get_repair_proposal,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.tests.preparation_operations_service_cases import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    create_schedule,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
)
from backend.tests.test_preparation_repair_proposals import proposal_payload


PREDECESSOR = "20260802_0017"
HEAD = "20260802_0018"
CONSTRAINT = "uq_preparation_repair_acceptance_source_version"
DEFAULT_COUNT = 64


def _revision(db: Session) -> str:
    value = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    return str(value)


def _counts(db: Session) -> dict[str, int]:
    return {
        "proposal_count": db.query(DBPreparationRepairProposal).count(),
        "acceptance_count": db.query(DBPreparationRepairProposalAcceptance).count(),
        "schedule_count": db.query(DBPersistedPreparationSchedule).count(),
        "proposal_event_count": db.query(DBPreparationRepairProposalEvent).count(),
    }


def _assert_empty(db: Session) -> None:
    observed = _counts(db)
    if any(observed.values()):
        raise RuntimeError(
            "Migration rehearsal requires an empty application dataset: "
            + json.dumps(observed, sort_keys=True)
        )


def _create_scope(db: Session) -> None:
    db.add(
        DBUser(
            id=OWNER_ID,
            name="Migration Rehearsal Owner",
            liked_ingredients=[],
            disliked_ingredients=[],
            allergies=[],
            dietary_restrictions=[],
            health_conditions=[],
            medications=[],
        )
    )
    db.add(
        DBHousehold(
            id=HOUSEHOLD_ID,
            owner_user_id=OWNER_ID,
            name="Migration rehearsal household",
            timezone="UTC",
            version=1,
        )
    )
    db.commit()


def _acceptance_snapshot(db: Session, acceptance_id: int) -> dict[str, Any]:
    acceptance = db.get(DBPreparationRepairProposalAcceptance, acceptance_id)
    if acceptance is None:
        raise RuntimeError(f"Acceptance {acceptance_id} disappeared")
    proposal = db.get(DBPreparationRepairProposal, acceptance.proposal_id)
    source = db.get(DBPersistedPreparationSchedule, acceptance.source_schedule_id)
    replacement = db.get(DBPersistedPreparationSchedule, acceptance.created_schedule_id)
    if proposal is None or source is None or replacement is None:
        raise RuntimeError("Acceptance dependencies are incomplete")
    event_types = [
        row.event_type
        for row in (
            db.query(DBPreparationRepairProposalEvent)
            .filter(DBPreparationRepairProposalEvent.proposal_id == proposal.id)
            .order_by(DBPreparationRepairProposalEvent.id)
            .all()
        )
    ]
    return {
        "proposal_id": proposal.id,
        "proposal_version": proposal.version,
        "proposal_status": proposal.status,
        "repair_request_hash": proposal.repair_request_hash,
        "repair_result_hash": proposal.repair_result_hash,
        "revised_request_hash": proposal.revised_request_hash,
        "repaired_response_hash": proposal.repaired_response_hash,
        "acceptance_id": acceptance.id,
        "acceptance_fingerprint": acceptance.request_fingerprint,
        "source_schedule_id": source.id,
        "source_schedule_version": acceptance.source_schedule_version,
        "source_schedule_hash": source.schedule_hash,
        "replacement_schedule_id": replacement.id,
        "replacement_schedule_version": replacement.version,
        "replacement_schedule_status": replacement.status,
        "replacement_schedule_hash": replacement.schedule_hash,
        "event_types": event_types,
    }


def seed(*, count: int, manifest_path: Path) -> dict[str, Any]:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Migration volume rehearsal must run on PostgreSQL")
    started = time.perf_counter()
    db = SessionLocal()
    try:
        revision = _revision(db)
        if revision != PREDECESSOR:
            raise RuntimeError(
                f"Seed phase requires {PREDECESSOR}, observed {revision}"
            )
        _assert_empty(db)
        _create_scope(db)
        calendar = create_calendar(
            db,
            version="migration-rehearsal-calendar-v1",
            key="migration-rehearsal-calendar-create-v1",
        )

        records: list[dict[str, Any]] = []
        first_source = None
        for index in range(count):
            source = create_schedule(
                db,
                calendar,
                key=f"migration-rehearsal-source-{index:04d}",
            )
            proposal = create_repair_proposal(
                db,
                household_id=HOUSEHOLD_ID,
                actor_user_id=OWNER_ID,
                payload=proposal_payload(
                    schedule=source,
                    calendar=calendar,
                    key=f"migration-rehearsal-proposal-{index:04d}",
                ),
            )
            accepted = accept_repair_proposal_with_source_guard(
                db,
                household_id=HOUSEHOLD_ID,
                proposal_id=proposal.id,
                actor_user_id=OWNER_ID,
                payload=acceptance_payload(
                    proposal,
                    key=f"migration-rehearsal-acceptance-{index:04d}",
                ),
            )
            records.append(
                _acceptance_snapshot(db, accepted.acceptance.id)
            )
            if first_source is None:
                first_source = source

        if first_source is None:
            raise RuntimeError("Rehearsal count must be positive")
        competing = create_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=proposal_payload(
                schedule=first_source,
                calendar=calendar,
                key="migration-rehearsal-competing-proposal",
            ),
        )
        counts = _counts(db)
        expected_counts = {
            "proposal_count": count + 1,
            "acceptance_count": count,
            "schedule_count": count * 2,
            "proposal_event_count": count * 2 + 1,
        }
        if counts != expected_counts:
            raise RuntimeError(
                f"Unexpected predecessor counts: {counts} != {expected_counts}"
            )

        manifest = {
            "schema_revision": revision,
            "rehearsal_count": count,
            "household_id": HOUSEHOLD_ID,
            "calendar_id": calendar.id,
            "calendar_content_hash": calendar.content_hash,
            "records": records,
            "competing_proposal_id": competing.id,
            "competing_source_schedule_id": first_source.id,
            "competing_source_schedule_version": first_source.version,
            "counts": counts,
            "seed_duration_seconds": round(time.perf_counter() - started, 6),
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return manifest
    finally:
        db.close()


def _constraint_definition(db: Session) -> str:
    row = db.execute(
        text(
            """
            SELECT pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'preparation_repair_proposal_acceptances'::regclass
              AND conname = :constraint_name
            """
        ),
        {"constraint_name": CONSTRAINT},
    ).mappings().first()
    if row is None:
        raise RuntimeError(f"Constraint {CONSTRAINT} is absent")
    return str(row["definition"])


def verify(*, manifest_path: Path, report_path: Path) -> dict[str, Any]:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Migration volume rehearsal must run on PostgreSQL")
    started = time.perf_counter()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    count = int(manifest["rehearsal_count"])
    db = SessionLocal()
    try:
        revision = _revision(db)
        if revision != HEAD:
            raise RuntimeError(f"Verify phase requires {HEAD}, observed {revision}")
        counts = _counts(db)
        if counts != manifest["counts"]:
            raise RuntimeError(
                f"Migration changed table counts: {counts} != {manifest['counts']}"
            )

        observed_records = [
            _acceptance_snapshot(db, int(record["acceptance_id"]))
            for record in manifest["records"]
        ]
        if observed_records != manifest["records"]:
            raise RuntimeError("Migration changed acceptance identity or hash evidence")

        distinct_sources = db.execute(
            text(
                """
                SELECT COUNT(*) AS acceptance_count,
                       COUNT(DISTINCT (source_schedule_id, source_schedule_version))
                           AS distinct_source_versions
                FROM preparation_repair_proposal_acceptances
                """
            )
        ).mappings().one()
        if int(distinct_sources["acceptance_count"]) != count:
            raise RuntimeError("Acceptance count changed during migration")
        if int(distinct_sources["distinct_source_versions"]) != count:
            raise RuntimeError("Historical source/version identity is not unique")

        definition = _constraint_definition(db)
        normalized = definition.replace('"', "").replace(" ", "").lower()
        if "unique(source_schedule_id,source_schedule_version)" not in normalized:
            raise RuntimeError(f"Unexpected constraint definition: {definition}")

        before_bypass = _counts(db)
        competitor = get_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=int(manifest["competing_proposal_id"]),
        )
        bypass_code = None
        try:
            accept_repair_proposal(
                db,
                household_id=HOUSEHOLD_ID,
                proposal_id=competitor.id,
                actor_user_id=OWNER_ID,
                payload=acceptance_payload(
                    competitor,
                    key="migration-rehearsal-lower-level-bypass",
                ),
            )
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            bypass_code = (
                exc.detail.get("code")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            )
        else:
            raise RuntimeError("Database uniqueness allowed a second source replacement")
        if bypass_code != "repair_acceptance_creation_conflict":
            raise RuntimeError(f"Unexpected bypass conflict code: {bypass_code}")
        db.expire_all()
        after_bypass = _counts(db)
        if after_bypass != before_bypass:
            raise RuntimeError(
                f"Failed bypass left rows behind: {after_bypass} != {before_bypass}"
            )
        competitor_row = db.get(
            DBPreparationRepairProposal,
            int(manifest["competing_proposal_id"]),
        )
        if competitor_row is None or competitor_row.status != "proposed":
            raise RuntimeError("Failed bypass changed the competing proposal")
        competitor_schedule_count = (
            db.query(DBPersistedPreparationSchedule)
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id
                == competitor_row.id
            )
            .count()
        )
        if competitor_schedule_count != 0:
            raise RuntimeError("Failed bypass left a replacement draft behind")

        report = {
            "valid": True,
            "predecessor_revision": PREDECESSOR,
            "head_revision": revision,
            "rehearsal_count": count,
            "constraint_name": CONSTRAINT,
            "constraint_definition": definition,
            "preserved_counts": counts,
            "preserved_record_count": len(observed_records),
            "lower_level_bypass_conflict_code": bypass_code,
            "lower_level_bypass_rows_added": 0,
            "verification_duration_seconds": round(
                time.perf_counter() - started,
                6,
            ),
            "network_or_failover_simulated": False,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return report
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["seed", "verify"])
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("reports/repair-source-acceptance-migration-seed.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/repair-source-acceptance-migration-report.json"),
    )
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    if args.mode == "seed":
        seed(count=args.count, manifest_path=args.manifest)
    else:
        verify(manifest_path=args.manifest, report_path=args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
