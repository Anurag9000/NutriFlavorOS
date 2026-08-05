from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

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


REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTER_SCRIPT = REPO_ROOT / "scripts" / "probe_preparation_repair_stable_database_endpoint.py"
CONTROLLER_SCRIPT = (
    REPO_ROOT / "scripts" / "run_preparation_repair_automatic_failover_controller.py"
)
CONTROLLER_COUNT = 2
FAILURE_THRESHOLD = 3
ONE_COUNTS = {
    "acceptances": 1,
    "replacement_schedules": 1,
    "proposal_accepted_events": 1,
    "replacement_created_events": 1,
}


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    assert value, f"required automatic-failover environment variable is missing: {name}"
    return value


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _wait_for_json(
    path: Path,
    predicate: Callable[[dict[str, Any]], bool],
    *,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_value: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        if path.is_file():
            last_value = _read_json(path)
            if predicate(last_value):
                return last_value
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for JSON state {path}: {last_value!r}")


def _worker_environment() -> dict[str, str]:
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        f"{REPO_ROOT}{os.pathsep}{existing}" if existing else str(REPO_ROOT)
    )
    return environment


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
                DBPersistedPreparationSchedule.id == DBPreparationScheduleEvent.schedule_id,
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


def _timeline(db: Session) -> str:
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
    stable_database_url: str,
    proposal_id: int,
    payload,
) -> OperationalError:
    stable_url = make_url(stable_database_url)
    proxy = PostgresCommitAckDropProxy(
        upstream_host=stable_url.host or "127.0.0.1",
        upstream_port=int(stable_url.port or 5432),
    )
    captured_error: OperationalError | None = None
    with proxy:
        proxy.wait_until_ready()
        proxied_engine = create_engine(
            _proxy_database_url(stable_database_url, proxy.listen_port),
            poolclass=NullPool,
            pool_pre_ping=False,
        )
        worker = _session(proxied_engine)
        try:
            worker.execute(text("SET LOCAL synchronous_commit = on"))
            assert worker.execute(text("SHOW synchronous_commit")).scalar_one() == "on"
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
    observed: str | None = None
    while time.monotonic() < deadline:
        with standby_engine.connect() as connection:
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
        assert in_recovery is True
        observed = None if replay_lsn is None else str(replay_lsn)
        if caught_up is True:
            assert observed is not None
            return observed
        time.sleep(0.1)
    raise AssertionError(
        f"standby did not replay target WAL: target={target_lsn}, observed={observed}"
    )


def _collect_process(
    process: subprocess.Popen[str],
    *,
    timeout_seconds: float,
) -> tuple[str, str]:
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate(timeout=15)
        raise AssertionError(
            f"subprocess timed out: pid={process.pid}, stdout={stdout}, stderr={stderr}"
        ) from exc
    if process.returncode != 0:
        raise AssertionError(
            f"subprocess failed: pid={process.pid}, returncode={process.returncode}, "
            f"stdout={stdout}, stderr={stderr}"
        )
    return stdout, stderr


def _ensure_process_stopped(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.kill()
        process.communicate(timeout=15)


def _stop_primary(container_name: str) -> None:
    result = subprocess.run(
        ["docker", "stop", "--time", "0", container_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def _container_absent(container_name: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", container_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode != 0


def _volume_exists(volume_name: str) -> bool:
    result = subprocess.run(
        ["docker", "volume", "inspect", volume_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode == 0


def _old_primary_endpoint_is_unavailable(database_url: str) -> bool:
    engine = _engine(database_url)
    try:
        with pytest.raises(OperationalError):
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        return True
    finally:
        engine.dispose()


def _read_router_events(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            assert isinstance(value, dict)
            values.append(value)
    return values


def _write_evidence(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomically(path, value)


def test_postgres_automatic_fenced_failover_recovers_through_stable_endpoint(
    tmp_path: Path,
):
    primary_database_url = _required_environment("FAILOVER_PRIMARY_DATABASE_URL")
    standby_database_url = _required_environment("FAILOVER_STANDBY_DATABASE_URL")
    stable_database_url = _required_environment("FAILOVER_STABLE_DATABASE_URL")
    primary_container = _required_environment("FAILOVER_PRIMARY_CONTAINER")
    primary_volume = _required_environment("FAILOVER_PRIMARY_VOLUME")
    primary_port = int(_required_environment("FAILOVER_PRIMARY_PORT"))
    stable_port = int(_required_environment("FAILOVER_STABLE_PORT"))
    evidence_path = Path(_required_environment("FAILOVER_AUTOMATIC_REPORT_PATH"))

    route_path = tmp_path / "stable-route.json"
    router_ready_path = tmp_path / "stable-router-ready.json"
    router_event_path = tmp_path / "stable-router-events.jsonl"
    router_report_path = tmp_path / "stable-router-report.json"
    witness_path = tmp_path / "failover-witness.json"
    lease_path = tmp_path / "failover-witness.lock"
    controller_report_paths = [
        tmp_path / f"automatic-controller-{index}.json"
        for index in range(CONTROLLER_COUNT)
    ]

    _write_json_atomically(
        route_path,
        {
            "epoch": 0,
            "target_host": "127.0.0.1",
            "target_label": "original-primary",
            "target_port": primary_port,
        },
    )

    router = subprocess.Popen(
        [
            sys.executable,
            str(ROUTER_SCRIPT),
            "--listen-port",
            str(stable_port),
            "--state",
            str(route_path),
            "--ready",
            str(router_ready_path),
            "--events",
            str(router_event_path),
            "--report",
            str(router_report_path),
        ],
        cwd=REPO_ROOT,
        env=_worker_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    controllers: list[subprocess.Popen[str]] = []
    stable_engine = _engine(stable_database_url)
    primary_engine = _engine(primary_database_url)
    standby_engine = _engine(standby_database_url)
    stable_db: Session | None = None
    primary_db: Session | None = None
    standby_db: Session | None = None
    promoted_db: Session | None = None

    try:
        ready = _wait_for_json(
            router_ready_path,
            lambda value: value.get("ready") is True,
            timeout_seconds=15,
        )
        assert ready["listen_port"] == stable_port
        assert router.poll() is None

        stable_db = _session(stable_engine)
        primary_db = _session(primary_engine)
        standby_db = _session(standby_engine)
        assert stable_db.execute(text("SELECT pg_is_in_recovery()" )).scalar_one() is False
        assert standby_db.execute(text("SELECT pg_is_in_recovery()" )).scalar_one() is True

        primary_system_identifier = _system_identifier(primary_db)
        standby_system_identifier = _system_identifier(standby_db)
        assert primary_system_identifier == standby_system_identifier
        primary_timeline = _timeline(primary_db)

        _, _, proposal = create_proposal(stable_db)
        proposal_id = int(proposal.id)
        idempotency_key = "pg-automatic-failover-stable-endpoint-exact-key"
        payload = acceptance_payload(proposal, key=idempotency_key)

        captured_error = _commit_without_acknowledgement(
            stable_database_url=stable_database_url,
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
        replay_lsn = _wait_for_replay(standby_engine, target_lsn=target_lsn)
        assert _accepted_counts(standby_db, proposal_id) == ONE_COUNTS

        stable_db.close()
        stable_db = None
        primary_db.close()
        primary_db = None
        standby_db.close()
        standby_db = None
        primary_engine.dispose()

        controller_ids = [uuid4().hex for _ in range(CONTROLLER_COUNT)]
        for index, controller_id in enumerate(controller_ids):
            controllers.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(CONTROLLER_SCRIPT),
                        "--primary-host",
                        "127.0.0.1",
                        "--primary-port",
                        str(primary_port),
                        "--standby-database-url",
                        standby_database_url,
                        "--primary-container",
                        primary_container,
                        "--primary-volume",
                        primary_volume,
                        "--route-state",
                        str(route_path),
                        "--witness",
                        str(witness_path),
                        "--lease",
                        str(lease_path),
                        "--report",
                        str(controller_report_paths[index]),
                        "--controller-id",
                        controller_id,
                        "--failure-threshold",
                        str(FAILURE_THRESHOLD),
                    ],
                    cwd=REPO_ROOT,
                    env=_worker_environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )

        time.sleep(1.0)
        assert all(process.poll() is None for process in controllers)
        _stop_primary(primary_container)

        for process in controllers:
            _collect_process(process, timeout_seconds=120)

        controller_reports = [_read_json(path) for path in controller_report_paths]
        winners = [value for value in controller_reports if value["promotion_performed"] is True]
        followers = [value for value in controller_reports if value["promotion_performed"] is False]
        assert len(winners) == 1
        assert len(followers) == 1
        winner = winners[0]
        follower = followers[0]
        assert winner["lease_acquired"] is True
        assert winner["route_rotation_performed"] is True
        assert winner["failure_threshold"] == FAILURE_THRESHOLD
        assert winner["failure_observations"] >= FAILURE_THRESHOLD
        assert winner["old_primary_container_removed"] is True
        assert winner["old_primary_volume_retained"] is True
        assert winner["standby_promoted"] is True
        assert winner["server_automatic_mutation_retry"] is False
        assert follower["lease_acquired"] is False
        assert follower["route_rotation_performed"] is False
        assert follower["failure_observations"] >= FAILURE_THRESHOLD
        assert follower["winner_controller_id"] == winner["controller_id"]
        assert follower["lease_contended"] is True or follower["already_promoted"] is True

        witness = _read_json(witness_path)
        route = _read_json(route_path)
        assert witness["status"] == "promoted"
        assert witness["epoch"] == 1
        assert witness["winner_controller_id"] == winner["controller_id"]
        assert witness["old_primary_container_removed"] is True
        assert witness["old_primary_volume_retained"] is True
        assert route["epoch"] == 1
        assert route["target_label"] == "promoted-standby"
        assert route["controller_id"] == winner["controller_id"]
        assert _container_absent(primary_container) is True
        assert _volume_exists(primary_volume) is True
        assert _old_primary_endpoint_is_unavailable(primary_database_url) is True

        promoted_db = _session(stable_engine)
        assert promoted_db.execute(text("SELECT pg_is_in_recovery()" )).scalar_one() is False
        assert promoted_db.execute(text("SHOW transaction_read_only")).scalar_one() == "off"
        promoted_system_identifier = _system_identifier(promoted_db)
        promoted_timeline = _timeline(promoted_db)
        assert promoted_system_identifier == primary_system_identifier
        assert promoted_timeline != primary_timeline
        assert winner["promoted_system_identifier"] == primary_system_identifier
        assert winner["promoted_timeline"] == promoted_timeline

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
        assert [value.event_type for value in proposal_events] == ["created", "accepted"]

        promoted_db.close()
        promoted_db = None
        router.terminate()
        _collect_process(router, timeout_seconds=30)
        router_report = _read_json(router_report_path)
        router_events = _read_router_events(router_event_path)
        opened_events = [
            value for value in router_events if value.get("event") == "connection_opened"
        ]
        assert any(
            value.get("target_label") == "original-primary" and value.get("epoch") == 0
            for value in opened_events
        )
        assert any(
            value.get("target_label") == "promoted-standby" and value.get("epoch") == 1
            for value in opened_events
        )
        assert router_report["router_stopped"] is True
        assert router_report["leaked_connection_threads"] == 0
        assert router_report["target_counts"]["original-primary"] >= 1
        assert router_report["target_counts"]["promoted-standby"] >= 1

        _write_evidence(
            evidence_path,
            {
                "valid": True,
                "postgresql_major": 16,
                "physical_streaming_replication": True,
                "stable_application_endpoint": True,
                "stable_endpoint_url_unchanged": True,
                "controller_count": CONTROLLER_COUNT,
                "promotion_winner_count": 1,
                "promotion_follower_count": 1,
                "single_local_witness_lease": True,
                "fence_epoch": 1,
                "failure_threshold": FAILURE_THRESHOLD,
                "automatic_failure_detection": True,
                "old_primary_container_removed": True,
                "old_primary_volume_retained": True,
                "old_primary_endpoint_unavailable": True,
                "standby_promoted": True,
                "shared_system_identifier": True,
                "timeline_advanced": True,
                "target_flush_lsn": target_lsn,
                "standby_replay_lsn": replay_lsn,
                "stable_route_rotated": True,
                "same_key_recovery": True,
                "acceptance_count": 1,
                "replacement_count": 1,
                "accepted_event_count": 1,
                "created_event_count": 1,
                "server_automatic_mutation_retry": False,
                "distributed_consensus_proven": False,
                "production_stonith_proven": False,
                "quorum_proven": False,
                "old_primary_rejoin_proven": False,
                "multi_region_failover_proven": False,
                "hosted_green_claim": False,
            },
        )
    finally:
        for value in (stable_db, primary_db, standby_db, promoted_db):
            if value is not None:
                value.close()
        for process in controllers:
            _ensure_process_stopped(process)
        if router.poll() is None:
            router.terminate()
            try:
                router.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                router.kill()
                router.communicate(timeout=15)
        stable_engine.dispose()
        primary_engine.dispose()
        standby_engine.dispose()
