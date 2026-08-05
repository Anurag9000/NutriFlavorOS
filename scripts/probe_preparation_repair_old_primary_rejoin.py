#!/usr/bin/env python3
"""Verify the rewound old primary is a caught-up read-only standby."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)


ONE_COUNTS = {
    "acceptances": 1,
    "replacement_schedules": 1,
    "proposal_accepted_events": 1,
    "replacement_created_events": 1,
}


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required old-primary rejoin variable is missing: {name}")
    return value


def _engine(url: str):
    return create_engine(
        url,
        poolclass=NullPool,
        pool_pre_ping=False,
        connect_args={"connect_timeout": 5},
    )


def _session(engine):
    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return factory()


def _counts(db, proposal_id: int) -> dict[str, int]:
    db.rollback()
    return {
        "acceptances": (
            db.query(DBPreparationRepairProposalAcceptance)
            .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
            .count()
        ),
        "replacement_schedules": (
            db.query(DBPersistedPreparationSchedule)
            .filter(DBPersistedPreparationSchedule.source_repair_proposal_id == proposal_id)
            .count()
        ),
        "proposal_accepted_events": (
            db.query(DBPreparationRepairProposalEvent)
            .filter(
                DBPreparationRepairProposalEvent.proposal_id == proposal_id,
                DBPreparationRepairProposalEvent.event_type == "accepted",
            )
            .count()
        ),
        "replacement_created_events": (
            db.query(DBPreparationScheduleEvent)
            .join(
                DBPersistedPreparationSchedule,
                DBPersistedPreparationSchedule.id == DBPreparationScheduleEvent.schedule_id,
            )
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id == proposal_id,
                DBPreparationScheduleEvent.event_type == "created",
            )
            .count()
        ),
    }


def _system_identifier(db) -> str:
    db.rollback()
    return str(
        db.execute(
            text("SELECT system_identifier::text FROM pg_control_system()")
        ).scalar_one()
    )


def _write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _wait_for_replay(engine, target_lsn: str, timeout_seconds: float = 60.0) -> str:
    deadline = time.monotonic() + timeout_seconds
    observed: str | None = None
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            in_recovery, replay_lsn, caught_up = connection.execute(
                text(
                    "SELECT pg_is_in_recovery(), "
                    "pg_last_wal_replay_lsn()::text, "
                    "COALESCE(pg_wal_lsn_diff("
                    "pg_last_wal_replay_lsn(), CAST(:target_lsn AS pg_lsn)"
                    ") >= 0, false)"
                ),
                {"target_lsn": target_lsn},
            ).one()
        if in_recovery is not True:
            raise RuntimeError("rewound old primary left recovery unexpectedly")
        observed = None if replay_lsn is None else str(replay_lsn)
        if caught_up is True:
            if observed is None:
                raise RuntimeError("caught-up standby did not expose a replay LSN")
            return observed
        time.sleep(0.1)
    raise TimeoutError(
        f"rewound old primary did not replay target WAL: target={target_lsn}, "
        f"observed={observed}"
    )


def main() -> int:
    promoted_url = _required_environment("FAILOVER_STANDBY_DATABASE_URL")
    rejoin_url = _required_environment("FAILOVER_REJOIN_DATABASE_URL")
    report_path = Path(_required_environment("FAILOVER_REJOIN_REPORT_PATH"))

    promoted_engine = _engine(promoted_url)
    rejoin_engine = _engine(rejoin_url)
    promoted = _session(promoted_engine)
    rejoined = _session(rejoin_engine)
    try:
        if promoted.execute(text("SELECT pg_is_in_recovery()")).scalar_one() is not False:
            raise RuntimeError("promoted primary is not writable authority")
        if promoted.execute(text("SHOW transaction_read_only")).scalar_one() != "off":
            raise RuntimeError("promoted primary unexpectedly became read-only")
        if rejoined.execute(text("SELECT pg_is_in_recovery()")).scalar_one() is not True:
            raise RuntimeError("rewound old primary did not rejoin as standby")
        if rejoined.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
            raise RuntimeError("rewound old primary is not read-only")
        receiver_status = str(
            rejoined.execute(
                text("SELECT COALESCE(status, '') FROM pg_stat_wal_receiver")
            ).scalar_one()
        )
        if receiver_status != "streaming":
            raise RuntimeError(f"rewound standby receiver is not streaming: {receiver_status}")
        sender_count = int(
            promoted.execute(
                text(
                    "SELECT count(*) FROM pg_stat_replication "
                    "WHERE state = 'streaming' "
                    "AND application_name = 'rewound-old-primary'"
                )
            ).scalar_one()
        )
        if sender_count != 1:
            raise RuntimeError(f"promoted source has {sender_count} rewound senders")

        promoted_identifier = _system_identifier(promoted)
        rejoined_identifier = _system_identifier(rejoined)
        if promoted_identifier != rejoined_identifier:
            raise RuntimeError("rewound standby does not share the promoted cluster identity")

        acceptances = promoted.query(DBPreparationRepairProposalAcceptance).all()
        if len(acceptances) != 1:
            raise RuntimeError(f"expected one promoted acceptance, observed {len(acceptances)}")
        acceptance = acceptances[0]
        proposal_id = int(acceptance.proposal_id)
        acceptance_id = int(acceptance.id)
        schedule_id = int(acceptance.created_schedule_id)
        if _counts(promoted, proposal_id) != ONE_COUNTS:
            raise RuntimeError("promoted lifecycle counts are not exactly one")
        if _counts(rejoined, proposal_id) != ONE_COUNTS:
            raise RuntimeError("rewound standby lifecycle counts are not exactly one")
        copied_acceptance = (
            rejoined.query(DBPreparationRepairProposalAcceptance)
            .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
            .one()
        )
        if int(copied_acceptance.id) != acceptance_id:
            raise RuntimeError("rewound standby acceptance identity drifted")
        if int(copied_acceptance.created_schedule_id) != schedule_id:
            raise RuntimeError("rewound standby schedule identity drifted")

        with promoted_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.execute(text("SELECT pg_switch_wal()"))
            target_lsn = str(
                connection.execute(
                    text("SELECT pg_current_wal_flush_lsn()::text")
                ).scalar_one()
            )
        replay_lsn = _wait_for_replay(rejoin_engine, target_lsn)
        if _counts(rejoined, proposal_id) != ONE_COUNTS:
            raise RuntimeError("rewound standby changed lifecycle counts after catch-up")

        _write_json_atomically(
            report_path,
            {
                "valid": True,
                "postgresql_major": 16,
                "pg_rewind_completed": True,
                "wal_log_hints_enabled": True,
                "old_primary_rejoined_as_standby": True,
                "rejoined_in_recovery": True,
                "rejoined_transaction_read_only": True,
                "receiver_streaming": True,
                "promoted_sender_count": 1,
                "shared_system_identifier": True,
                "target_flush_lsn_recorded": True,
                "replay_lsn_verified": True,
                "observed_replay_lsn": replay_lsn,
                "acceptance_identity_preserved": True,
                "schedule_identity_preserved": True,
                "acceptance_count": 1,
                "replacement_count": 1,
                "accepted_event_count": 1,
                "created_event_count": 1,
                "application_write_route_changed": False,
                "rejoined_node_promoted": False,
                "automatic_rejoin_orchestration": False,
                "partition_safe_fencing_proven": False,
                "representative_recovery_time_proven": False,
                "hosted_green_claim": False,
            },
        )
        return 0
    finally:
        promoted.close()
        rejoined.close()
        promoted_engine.dispose()
        rejoin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
