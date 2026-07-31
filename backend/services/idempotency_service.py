"""Full-request idempotency for public household inventory mutations.

The inventory ledger enforces a unique ``(household_id, idempotency_key)`` pair.
This coordinator additionally fingerprints the complete normalized request and
serializes concurrent use of the same key.

Fingerprint metadata is attached by a SQLAlchemy ``before_flush`` listener, so
the inventory effect and its request identity are committed atomically by the
underlying service. PostgreSQL uses a dedicated session-level advisory lock;
local engines use a bounded process-local keyed-lock registry.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, Optional, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from backend.database import DBInventoryEvent


T = TypeVar("T")
_LOCK_TIMEOUT_SECONDS = 15.0
_SESSION_CONTEXT_KEY = "nutriflavos_inventory_idempotency"


@dataclass
class _ProcessLockEntry:
    lock: Any
    users: int = 0


_PROCESS_LOCKS: Dict[str, _ProcessLockEntry] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def _conflict(message: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": "idempotency_key_reused", "message": message},
    )


def _canonical_payload(payload: BaseModel | Dict[str, Any] | Any) -> Any:
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json", exclude={"idempotency_key"})
    if isinstance(payload, dict):
        return {
            key: value
            for key, value in payload.items()
            if key != "idempotency_key"
        }
    return payload


def request_fingerprint(
    *,
    operation: str,
    payload: BaseModel | Dict[str, Any] | Any,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    document = {
        "operation": operation,
        "context": context or {},
        "payload": _canonical_payload(payload),
    }
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _lock_identity(household_id: str, key: str) -> str:
    return f"{household_id}\x1f{key}"


def _advisory_key(identity: str) -> int:
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def _reserve_process_lock(identity: str) -> _ProcessLockEntry:
    with _PROCESS_LOCKS_GUARD:
        entry = _PROCESS_LOCKS.get(identity)
        if entry is None:
            entry = _ProcessLockEntry(lock=threading.RLock())
            _PROCESS_LOCKS[identity] = entry
        entry.users += 1
        return entry


def _release_process_lock(identity: str, entry: _ProcessLockEntry) -> None:
    with _PROCESS_LOCKS_GUARD:
        entry.users -= 1
        if entry.users == 0 and _PROCESS_LOCKS.get(identity) is entry:
            _PROCESS_LOCKS.pop(identity, None)


@event.listens_for(Session, "before_flush")
def _attach_inventory_request_fingerprint(
    session: Session,
    _flush_context: Any,
    _instances: Any,
) -> None:
    context = session.info.get(_SESSION_CONTEXT_KEY)
    if not isinstance(context, dict):
        return
    for value in session.new:
        if not isinstance(value, DBInventoryEvent):
            continue
        if (
            value.household_id != context["household_id"]
            or value.idempotency_key != context["key"]
        ):
            continue
        metadata = dict(value.event_metadata or {})
        stored = metadata.get("request_fingerprint")
        if stored is not None and stored != context["fingerprint"]:
            raise _conflict(
                "The pending ledger event contains a different request fingerprint"
            )
        metadata.update(
            {
                "request_fingerprint": context["fingerprint"],
                "idempotency_operation": context["operation"],
                "idempotency_context": context["context"],
            }
        )
        value.event_metadata = metadata


@contextmanager
def _postgres_lock(db: Session, identity: str) -> Iterator[None]:
    engine = db.get_bind()
    connection: Connection = engine.connect()
    key = _advisory_key(identity)
    deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
    acquired = False
    try:
        while time.monotonic() < deadline:
            acquired = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
                ).scalar()
            )
            if acquired:
                break
            time.sleep(0.05)
        if not acquired:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_lock_timeout",
                    "message": "Another request with this idempotency key is still running",
                },
            )
        yield
    finally:
        if acquired:
            try:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                )
            finally:
                connection.close()
        else:
            connection.close()


@contextmanager
def idempotency_lock(db: Session, household_id: str, key: str) -> Iterator[None]:
    identity = _lock_identity(household_id, key)
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        with _postgres_lock(db, identity):
            yield
        return

    entry = _reserve_process_lock(identity)
    acquired = entry.lock.acquire(timeout=_LOCK_TIMEOUT_SECONDS)
    if not acquired:
        _release_process_lock(identity, entry)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_lock_timeout",
                "message": "Another request with this idempotency key is still running",
            },
        )
    try:
        yield
    finally:
        entry.lock.release()
        _release_process_lock(identity, entry)


def _event_for_key(
    db: Session, household_id: str, key: str
) -> Optional[DBInventoryEvent]:
    return (
        db.query(DBInventoryEvent)
        .filter(
            DBInventoryEvent.household_id == household_id,
            DBInventoryEvent.idempotency_key == key,
        )
        .first()
    )


def _verify_existing_event(
    event_value: DBInventoryEvent,
    fingerprint: str,
) -> None:
    metadata = dict(event_value.event_metadata or {})
    stored = metadata.get("request_fingerprint")
    if stored is None:
        raise _conflict(
            "This key belongs to a legacy event without a complete request fingerprint; use a new key"
        )
    if stored != fingerprint:
        raise _conflict(
            "This idempotency key was already used for a different operation or request body"
        )


def run_idempotent_inventory_operation(
    db: Session,
    *,
    household_id: str,
    key: Optional[str],
    operation: str,
    payload: BaseModel | Dict[str, Any] | Any,
    handler: Callable[[], T],
    context: Optional[Dict[str, Any]] = None,
) -> T:
    """Run one public inventory mutation with complete-request idempotency."""

    if not key:
        return handler()

    fingerprint = request_fingerprint(
        operation=operation,
        payload=payload,
        context=context,
    )
    with idempotency_lock(db, household_id, key):
        prior = _event_for_key(db, household_id, key)
        if prior is not None:
            _verify_existing_event(prior, fingerprint)

        previous_context = db.info.get(_SESSION_CONTEXT_KEY)
        db.info[_SESSION_CONTEXT_KEY] = {
            "household_id": household_id,
            "key": key,
            "fingerprint": fingerprint,
            "operation": operation,
            "context": context or {},
        }
        try:
            result = handler()
        finally:
            if previous_context is None:
                db.info.pop(_SESSION_CONTEXT_KEY, None)
            else:
                db.info[_SESSION_CONTEXT_KEY] = previous_context

        event_value = _event_for_key(db, household_id, key)
        if event_value is None:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "idempotency_event_missing",
                    "message": "The mutation completed without its required audit event",
                },
            )
        _verify_existing_event(event_value, fingerprint)
        return result
