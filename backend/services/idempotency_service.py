"""Full-request idempotency for public household inventory mutations.

The inventory ledger already enforces a unique ``(household_id,
idempotency_key)`` pair. This coordinator adds two missing guarantees:

* the *complete normalized request* is fingerprinted, rather than only the
  quantity and target row; and
* concurrent requests are serialized before the service performs its own
  transaction and commit.

PostgreSQL uses a dedicated connection and session-level advisory lock so the
lock survives commits performed by the underlying service. SQLite and other
local engines use a process-local keyed lock; SQLite still supplies its normal
file/transaction serialization across processes.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from backend.database import DBInventoryEvent


T = TypeVar("T")
_LOCK_TIMEOUT_SECONDS = 15.0
_PROCESS_LOCKS: Dict[str, threading.RLock] = {}
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
        return payload
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


def _process_lock(identity: str) -> threading.RLock:
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(identity, threading.RLock())


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

    lock = _process_lock(identity)
    acquired = lock.acquire(timeout=_LOCK_TIMEOUT_SECONDS)
    if not acquired:
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
        lock.release()


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
    """Run and annotate one public inventory mutation.

    Requests without an idempotency key retain the underlying service behavior.
    For keyed requests, any pre-existing event must contain the same complete
    request fingerprint. Events created before fingerprints were introduced are
    deliberately treated as ambiguous and require a new key.
    """

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
            metadata = dict(prior.event_metadata or {})
            stored = metadata.get("request_fingerprint")
            if stored is None:
                raise _conflict(
                    "This key belongs to a legacy event without a complete request fingerprint; use a new key"
                )
            if stored != fingerprint:
                raise _conflict(
                    "This idempotency key was already used for a different operation or request body"
                )

        result = handler()
        event = _event_for_key(db, household_id, key)
        if event is None:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "idempotency_event_missing",
                    "message": "The mutation completed without its required audit event",
                },
            )

        metadata = dict(event.event_metadata or {})
        stored = metadata.get("request_fingerprint")
        if stored is not None and stored != fingerprint:
            db.rollback()
            raise _conflict(
                "This idempotency key was already used for a different operation or request body"
            )
        metadata.update(
            {
                "request_fingerprint": fingerprint,
                "idempotency_operation": operation,
                "idempotency_context": context or {},
            }
        )
        event.event_metadata = metadata
        db.add(event)
        db.commit()
        return result
