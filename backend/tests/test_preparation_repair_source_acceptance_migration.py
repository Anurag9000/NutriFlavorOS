from __future__ import annotations

from importlib import import_module

import pytest


migration = import_module(
    "backend.migrations.versions."
    "20260802_0018_unique_repair_source_acceptance"
)


class _Mappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _Mappings(self._rows)


class _Connection:
    def __init__(self, rows):
        self._rows = rows
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return _Result(self._rows)


def test_source_acceptance_preflight_allows_unique_rows(monkeypatch):
    connection = _Connection([])
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

    migration._assert_no_duplicate_source_acceptances()

    assert len(connection.statements) == 1
    assert "GROUP BY source_schedule_id, source_schedule_version" in (
        connection.statements[0]
    )
    assert "HAVING COUNT(*) > 1" in connection.statements[0]


def test_source_acceptance_preflight_lists_duplicate_rows(monkeypatch):
    connection = _Connection(
        [
            {
                "source_schedule_id": 7,
                "source_schedule_version": 2,
                "acceptance_count": 3,
            },
            {
                "source_schedule_id": 9,
                "source_schedule_version": 1,
                "acceptance_count": 2,
            },
        ]
    )
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

    with pytest.raises(RuntimeError) as exc:
        migration._assert_no_duplicate_source_acceptances()

    message = str(exc.value)
    assert "Cannot add one-replacement-per-source constraint" in message
    assert "schedule=7 version=2 acceptances=3" in message
    assert "schedule=9 version=1 acceptances=2" in message
