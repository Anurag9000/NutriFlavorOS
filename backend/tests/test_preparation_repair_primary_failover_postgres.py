from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.api.database_error_handlers import classify_operational_error
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.tests.postgres_commit_ack_drop_proxy import PostgresCommitAckDropProxy
from backend.tests.test_preparation_operations_service import HOUSEHOLD_ID, OWNER_ID
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)


ONE_COUNTS = {
    "acceptances": 1,
    "replacement_schedules": 1,
    "proposal_accepted_events": 1,
    "replacement_created_events": 1,
}


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    assert value, f"required failover environment variable is missing: {name}"
    return value


def _engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        poolclass=NullPool,
        pool_pre_ping=False,
        connect_args={"connect_timeout": 5},
    )


def _session(engine: Engine) -> Session:
    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return factory()


def _proxy_database_url(database_url: str, proxy_port: int):
    direct_url = make_url(database_url)
    query = dict(direct_url.query)
    query.update(
        {
            "connect_timeout": "5",
            "gssencmode": "disable",
            "sslmode": "disable",
        }
    )
    return direct_url.set(host="127.0.0.1", port=proxy_port, query=query)


def _accepted_counts(db: Session, proposal_id: int) -> dict[str, int]:
    db.rollback()
    return {
        "acceptances": (
            db.query(DBPreparationRepairProposalAcceptance)
            .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
            .count()
        ),
        "replacement_schedules": (
            db.query(DBPersistedPreparationSchedule)
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id
                == proposal_id
            )
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
                DBPersistedPreparationSchedule.id
                == DBPreparationScheduleEvent.schedule_id,
            )
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id
                == proposal_id,
                DBPreparationScheduleEvent.event_type == "created",
            )
            .count()
        ),
    }


def _system_identifier(db: Session) -> str:
    db.rollback()
    return str(
        db.execute(
            text("SELECT system_identifier::text FROM pg_control_system()")
        ).scalar_one()
    )


def _current_timeline(db: Session) -> str:
    db.rollback()
    return str(
        db.execute(
            text(
                "SELECT substring(pg_walfile_name(pg_current_wal_lsn()) "
                "from 1 for 8)"
            )
        ).scalar_one()
    )


def _commit_without_acknowledgement(
    *,
    primary_database_url: str,
    proposal_id: int,
    payload,
) -> OperationalError:
    direct_url = make_url(primary_database_url)
    proxy = PostgresCommitAckDropProxy(
        upstream_host=direct_url.host or "127.0.0.1",
        upstream_port=int(direct_url.port or 5432),
    )
    captured_error: OperationalError | None = None
    with proxy:
        proxy.wait_until_ready()
        proxied_engine = create_engine(
            _proxy_database_url(primary_database_url, proxy.listen_port),
            poolclass=NullPool,
            pool_pre_ping=False,
        )
        worker = _session(proxied_engine)
        try:
            worker.execute(text("SET LOCAL synchronous_commit = on"))
            assert (
                worker.execute(text("SHOW synchronous_commit")).scalar_one()
                == "on"
            )
            with pytest.raises(OperationalError) as caught:
                accept_repair_proposal_with_source_guard(
                    worker,
                    household_id=HOUSEHOLD_ID,
                    proposal_id=proposal_id,
                    actor_user_id=OWNER_ID,
                    payload=payload,
                )
            captured_error = caught.value
            proxy.wait_for_commit_ack_drop()
        finally:
            worker.close()
            proxied_engine.dispose()

    assert captured_error is not None
    report = proxy.report()
    assert report.commit_query_seen is True
    assert report.commit_query_forwarded is True
    assert report.commit_command_complete_seen is True
    assert report.commit_acknowledgement_forwarded is False
    assert report.proxy_threads_stopped is True
    return captured_error


def _wait_for_replay(
    standby_engine: Engine,
    *,
    target_lsn: str,
    timeout_seconds: float = 60.0,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_replay_lsn: str | None = None
    while time.monotonic() < deadline:
        with standby_engine.connect() as connection:
            in_recovery, replay_lsn, caught_up = connection.execute(
                text(
                    "SELECT pg_is_in_recovery(), "
                    "pg_last_wal_replay_lsn()::text, "
                    "COALESCE("
                    "pg_wal_lsn_diff("
                    "pg_last_wal_replay_lsn(), CAST(:target_lsn AS pg_lsn)"
                    ") >= 0, false)"
                ),
                {"target_lsn": target_lsn},
            ).one()
        assert in_recovery is True
        last_replay_lsn = None if replay_lsn is None else str(replay_lsn)
        if caught_up is True:
            assert last_replay_lsn is not None
            return last_replay_lsn
        time.sleep(0.1)
    raise AssertionError(
        "standby did not replay the committed acceptance WAL position: "
        f"target={target_lsn}, observed={last_replay_lsn}"
    )


def _stop_primary(container_name: str) -> None:
    result = subprocess.run(
        ["docker", "stop", "--time", "0", container_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    inspection = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert inspection.returncode == 0, inspection.stderr
    assert inspection.stdout.strip() == "false"


def _assert_primary_unavailable(primary_database_url: str) -> None:
    unavailable_engine = _engine(primary_database_url)
    try:
        with pytest.raises(OperationalError):
            with unavailable_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
    finally:
        unavailable_engine.dispose()


def _promote_standby(standby_engine: Engine) -> None:
    with standby_engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as connection:
        promoted = connection.execute(text("SELECT pg_promote(true, 60)")).scalar_one()
    assert promoted is True

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        with standby_engine.connect() as connection:
            if connection.execute(text("SELECT pg_is_in_recovery()" )).scalar_one() is False:
                return
        time.sleep(0.1)
    raise AssertionError("standby did not leave recovery after promotion")


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def test_postgres_physical_standby_promotion_recovers_exact_committed_request():
    primary_database_url = _required_environment("FAILOVER_PRIMARY_DATABASE_URL")
    standby_database_url = _required_environment("FAILOVER_STANDBY_DATABASE_URL")
    primary_container = _required_environment("FAILOVER_PRIMARY_CONTAINER")
    report_path = Path(_required_environment("FAILOVER_REPORT_PATH"))

    primary_engine = _engine(primary_database_url)
    standby_engine = _engine(standby_database_url)
    primary_db = _session(primary_engine)
    standby_db = _session(standby_engine)

    try:
        assert primary_db.get_bind().dialect.name == "postgresql"
        assert standby_db.get_bind().dialect.name == "postgresql"
        assert primary_db.execute(text("SELECT pg_is_in_recovery()" )).scalar_one() is False
        assert standby_db.execute(text("SELECT pg_is_in_recovery()" )).scalar_one() is True

        primary_system_identifier = _system_identifier(primary_db)
        standby_system_identifier = _system_identifier(standby_db)
        assert primary_system_identifier == standby_system_identifier
        primary_timeline = _current_timeline(primary_db)

        _, _, proposal = create_proposal(primary_db)
        proposal_id = int(proposal.id)
        idempotency_key = "pg-physical-failover-exact-key"
        payload = acceptance_payload(proposal, key=idempotency_key)

        captured_error = _commit_without_acknowledgement(
            primary_database_url=primary_database_url,
            proposal_id=proposal_id,
            payload=payload,
        )
        classification = classify_operational_error(captured_error)
        assert classification["code"] == "database_commit_outcome_unknown"
        assert classification["retryable"] is True
        assert classification["retry_safe"] is False
        assert classification["outcome_unknown"] is True
        assert classification["automatic_retry_performed"] is False
        assert captured_error.connection_invalidated is True

        assert _accepted_counts(primary_db, proposal_id) == ONE_COUNTS
        acceptance = (
            primary_db.query(DBPreparationRepairProposalAcceptance)
            .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
            .one()
        )
        committed_acceptance_id = int(acceptance.id)
        committed_schedule_id = int(acceptance.created_schedule_id)
        target_lsn = str(
            primary_db.execute(
                text("SELECT pg_current_wal_flush_lsn()::text")
            ).scalar_one()
        )

        replay_lsn = _wait_for_replay(
            standby_engine,
            target_lsn=target_lsn,
        )
        standby_db.rollback()
        assert _accepted_counts(standby_db, proposal_id) == ONE_COUNTS
        replicated_acceptance = (
            standby_db.query(DBPreparationRepairProposalAcceptance)
            .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
            .one()
        )
        assert int(replicated_acceptance.id) == committed_acceptance_id
        assert int(replicated_acceptance.created_schedule_id) == committed_schedule_id
    finally:
        primary_db.close()
        standby_db.close()
        primary_engine.dispose()

    _stop_primary(primary_container)
    _assert_primary_unavailable(primary_database_url)

    _promote_standby(standby_engine)
    promoted_db = _session(standby_engine)
    try:
        assert promoted_db.execute(text("SELECT pg_is_in_recovery()" )).scalar_one() is False
        assert promoted_db.execute(text("SHOW transaction_read_only")).scalar_one() == "off"
        promoted_system_identifier = _system_identifier(promoted_db)
        assert promoted_system_identifier == primary_system_identifier

        promoted_db.rollback()
        promoted_db.execute(text("CHECKPOINT"))
        promoted_db.commit()
        promoted_timeline = _current_timeline(promoted_db)
        assert promoted_timeline != primary_timeline

        replayed = accept_repair_proposal_with_source_guard(
            promoted_db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal_id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
        assert replayed.acceptance.id == committed_acceptance_id
        assert replayed.acceptance.created_schedule_id == committed_schedule_id
        assert replayed.acceptance.idempotency_key == idempotency_key
        assert _accepted_counts(promoted_db, proposal_id) == ONE_COUNTS

        proposal_row = promoted_db.get(DBPreparationRepairProposal, proposal_id)
        assert proposal_row is not None
        promoted_db.refresh(proposal_row)
        assert proposal_row.status == "accepted"

        accepted_schedule = promoted_db.get(
            DBPersistedPreparationSchedule,
            committed_schedule_id,
        )
        assert accepted_schedule is not None
        assert accepted_schedule.status == "draft"
        assert accepted_schedule.version == 1

        proposal_events = (
            promoted_db.query(DBPreparationRepairProposalEvent)
            .filter(DBPreparationRepairProposalEvent.proposal_id == proposal_id)
            .order_by(DBPreparationRepairProposalEvent.id)
            .all()
        )
        assert [value.event_type for value in proposal_events] == [
            "created",
            "accepted",
        ]

        _write_report(
            report_path,
            {
                "valid": True,
                "postgresql_major": 16,
                "physical_streaming_replication": True,
                "primary_system_identifier": primary_system_identifier,
                "promoted_system_identifier": promoted_system_identifier,
                "shared_system_identifier": True,
                "primary_timeline": primary_timeline,
                "promoted_timeline": promoted_timeline,
                "timeline_advanced": promoted_timeline != primary_timeline,
                "target_flush_lsn": target_lsn,
                "standby_replay_lsn": replay_lsn,
                "standby_caught_up_before_primary_stop": True,
                "old_primary_stopped": True,
                "old_primary_endpoint_unavailable": True,
                "standby_promoted": True,
                "explicit_endpoint_rotation": True,
                "client_outcome_unknown_before_failover": True,
                "client_retry_safe": False,
                "server_automatic_retry": False,
                "same_key_recovery": True,
                "acceptance_count": 1,
                "replacement_count": 1,
                "accepted_event_count": 1,
                "created_event_count": 1,
                "automatic_dns_rotation": False,
                "automatic_failover_orchestrator": False,
                "old_primary_rejoin_proven": False,
                "split_brain_fencing_proven": False,
                "synchronous_replica_durability_proven": False,
                "multi_region_failover_proven": False,
                "hosted_green_claim": False,
            },
        )
    finally:
        promoted_db.close()
        standby_engine.dispose()
