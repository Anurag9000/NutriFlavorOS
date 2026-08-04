from __future__ import annotations

import pytest

from backend.tests.postgres_commit_ack_drop_proxy import (
    _command_complete_tag,
    _frame_length,
    _frontend_query,
    _startup_packet_length,
)


def _frame(message_type: bytes, payload: bytes) -> bytes:
    assert len(message_type) == 1
    length = 4 + len(payload)
    return message_type + length.to_bytes(4, byteorder="big") + payload


def test_simple_query_commit_is_detected_exactly():
    assert _frontend_query(_frame(b"Q", b"  COMMIT;\x00")) == b"COMMIT;"
    assert _frontend_query(_frame(b"Q", b"ROLLBACK\x00")) == b"ROLLBACK"


def test_extended_protocol_parse_commit_is_detected_exactly():
    parse = _frame(b"P", b"statement-name\x00 COMMIT \x00\x00\x00")
    assert _frontend_query(parse) == b"COMMIT"


def test_command_complete_commit_tag_is_detected_exactly():
    assert _command_complete_tag(_frame(b"C", b"COMMIT\x00")) == b"COMMIT"
    assert _command_complete_tag(_frame(b"C", b"UPDATE 1\x00")) == b"UPDATE 1"
    assert _command_complete_tag(_frame(b"Z", b"I")) is None


def test_protocol_lengths_wait_for_complete_prefix_and_reject_invalid_values():
    query = _frame(b"Q", b"COMMIT\x00")
    assert _frame_length(bytearray(query[:4])) is None
    assert _frame_length(bytearray(query)) == len(query)

    startup = (8).to_bytes(4, byteorder="big") + (196608).to_bytes(
        4,
        byteorder="big",
    )
    assert _startup_packet_length(bytearray(startup[:3])) is None
    assert _startup_packet_length(bytearray(startup)) == len(startup)

    with pytest.raises(AssertionError, match="frame length"):
        _frame_length(bytearray(b"Q\x00\x00\x00\x03"))
    with pytest.raises(AssertionError, match="startup packet length"):
        _startup_packet_length(bytearray(b"\x00\x00\x00\x07\x00\x00\x00\x00"))
