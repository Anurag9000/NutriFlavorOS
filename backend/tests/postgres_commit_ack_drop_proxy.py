"""Test-only PostgreSQL wire proxy that drops the COMMIT acknowledgement.

The proxy forwards one real PostgreSQL connection. It detects a frontend COMMIT
query, arms the drop before forwarding it upstream, waits until PostgreSQL emits
CommandComplete with payload ``COMMIT``, withholds that server frame from the
client, and closes the connection. The server has completed COMMIT while the
client receives only a connection failure and therefore cannot know the outcome.
"""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from typing import Final


_MAX_FRAME_BYTES: Final[int] = 16 * 1024 * 1024
_SOCKET_TIMEOUT_SECONDS: Final[float] = 0.5


def _frame_length(buffer: bytearray) -> int | None:
    if len(buffer) < 5:
        return None
    length = int.from_bytes(buffer[1:5], byteorder="big", signed=False)
    if length < 4 or length > _MAX_FRAME_BYTES:
        raise AssertionError(f"invalid PostgreSQL protocol frame length: {length}")
    return 1 + length


def _startup_packet_length(buffer: bytearray) -> int | None:
    if len(buffer) < 4:
        return None
    length = int.from_bytes(buffer[:4], byteorder="big", signed=False)
    if length < 8 or length > _MAX_FRAME_BYTES:
        raise AssertionError(f"invalid PostgreSQL startup packet length: {length}")
    return length


def _cstring_values(payload: bytes) -> tuple[bytes, ...]:
    values: list[bytes] = []
    remaining = payload
    while remaining:
        value, separator, remaining = remaining.partition(b"\x00")
        if not separator:
            break
        values.append(value)
    return tuple(values)


def _frontend_query(frame: bytes) -> bytes | None:
    message_type = frame[:1]
    payload = frame[5:]
    if message_type == b"Q":
        return payload.rstrip(b"\x00").strip()
    if message_type == b"P":
        values = _cstring_values(payload)
        if len(values) >= 2:
            return values[1].strip()
    return None


def _is_commit_query(query: bytes | None) -> bool:
    if query is None:
        return False
    return query.strip().rstrip(b";").strip().upper() == b"COMMIT"


def _command_complete_tag(frame: bytes) -> bytes | None:
    if frame[:1] != b"C":
        return None
    return frame[5:].rstrip(b"\x00").strip()


@dataclass(frozen=True)
class CommitAckDropReport:
    listen_host: str
    listen_port: int
    upstream_host: str
    upstream_port: int
    commit_query_seen: bool
    commit_query_forwarded: bool
    commit_command_complete_seen: bool
    commit_acknowledgement_forwarded: bool
    client_connection_closed_after_drop: bool
    upstream_connection_closed_after_drop: bool
    proxy_threads_stopped: bool


class PostgresCommitAckDropProxy:
    """Forward one PostgreSQL connection and drop its COMMIT CommandComplete."""

    def __init__(
        self,
        *,
        upstream_host: str,
        upstream_port: int,
        listen_host: str = "127.0.0.1",
    ) -> None:
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.listen_host = listen_host
        self.listen_port = 0
        self._listener: socket.socket | None = None
        self._client: socket.socket | None = None
        self._upstream: socket.socket | None = None
        self._serve_thread: threading.Thread | None = None
        self._forward_threads: tuple[threading.Thread, threading.Thread] | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._commit_query_seen = threading.Event()
        self._commit_query_forwarded = threading.Event()
        self._commit_command_complete_seen = threading.Event()
        self._client_closed_after_drop = threading.Event()
        self._upstream_closed_after_drop = threading.Event()
        self._errors: list[BaseException] = []
        self._error_lock = threading.Lock()

    def start(self) -> "PostgresCommitAckDropProxy":
        if self._serve_thread is not None:
            raise RuntimeError("commit acknowledgement proxy already started")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.listen_host, 0))
        listener.listen(1)
        listener.settimeout(_SOCKET_TIMEOUT_SECONDS)
        self.listen_port = int(listener.getsockname()[1])
        self._listener = listener
        self._serve_thread = threading.Thread(
            target=self._serve,
            name="postgres-commit-ack-drop-proxy",
            daemon=True,
        )
        self._serve_thread.start()
        self._ready.set()
        return self

    def wait_until_ready(self, timeout_seconds: float = 5) -> None:
        if not self._ready.wait(timeout_seconds):
            raise AssertionError("commit acknowledgement proxy did not become ready")

    def wait_for_commit_ack_drop(self, timeout_seconds: float = 15) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            self._raise_thread_errors()
            if self._commit_command_complete_seen.is_set():
                return
            time.sleep(0.01)
        raise AssertionError("PostgreSQL COMMIT acknowledgement was not observed")

    def report(self) -> CommitAckDropReport:
        threads_stopped = bool(
            self._serve_thread is not None
            and not self._serve_thread.is_alive()
            and self._forward_threads is not None
            and all(not value.is_alive() for value in self._forward_threads)
        )
        return CommitAckDropReport(
            listen_host=self.listen_host,
            listen_port=self.listen_port,
            upstream_host=self.upstream_host,
            upstream_port=self.upstream_port,
            commit_query_seen=self._commit_query_seen.is_set(),
            commit_query_forwarded=self._commit_query_forwarded.is_set(),
            commit_command_complete_seen=self._commit_command_complete_seen.is_set(),
            commit_acknowledgement_forwarded=False,
            client_connection_closed_after_drop=self._client_closed_after_drop.is_set(),
            upstream_connection_closed_after_drop=self._upstream_closed_after_drop.is_set(),
            proxy_threads_stopped=threads_stopped,
        )

    def close(self) -> None:
        self._stop.set()
        self._close_socket(self._client)
        self._close_socket(self._upstream)
        self._close_socket(self._listener)
        for thread in self._forward_threads or ():
            thread.join(timeout=5)
        if self._serve_thread is not None:
            self._serve_thread.join(timeout=5)
        self._raise_thread_errors()
        alive = [
            value.name
            for value in (
                *((self._forward_threads or ())),
                *((self._serve_thread,) if self._serve_thread else ()),
            )
            if value.is_alive()
        ]
        if alive:
            raise AssertionError(f"commit acknowledgement proxy threads leaked: {alive}")

    def __enter__(self) -> "PostgresCommitAckDropProxy":
        return self.start()

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def _record_error(self, exc: BaseException) -> None:
        if self._stop.is_set() or self._commit_command_complete_seen.is_set():
            return
        with self._error_lock:
            self._errors.append(exc)

    def _raise_thread_errors(self) -> None:
        with self._error_lock:
            errors = tuple(self._errors)
        if errors:
            raise AssertionError("commit acknowledgement proxy thread failed") from errors[0]

    @staticmethod
    def _close_socket(value: socket.socket | None) -> None:
        if value is None:
            return
        try:
            value.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            value.close()
        except OSError:
            pass

    def _serve(self) -> None:
        try:
            client = self._accept_client()
            upstream = socket.create_connection(
                (self.upstream_host, self.upstream_port),
                timeout=5,
            )
            client.settimeout(_SOCKET_TIMEOUT_SECONDS)
            upstream.settimeout(_SOCKET_TIMEOUT_SECONDS)
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            upstream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._client = client
            self._upstream = upstream
            client_thread = threading.Thread(
                target=self._forward_client_to_upstream,
                name="postgres-client-to-upstream",
                daemon=True,
            )
            server_thread = threading.Thread(
                target=self._forward_upstream_to_client,
                name="postgres-upstream-to-client",
                daemon=True,
            )
            self._forward_threads = (client_thread, server_thread)
            client_thread.start()
            server_thread.start()
            client_thread.join()
            server_thread.join()
        except BaseException as exc:  # pragma: no cover - thread diagnostic path
            self._record_error(exc)
        finally:
            self._stop.set()
            self._close_socket(self._client)
            self._close_socket(self._upstream)
            self._close_socket(self._listener)

    def _accept_client(self) -> socket.socket:
        if self._listener is None:
            raise AssertionError("proxy listener is missing")
        while not self._stop.is_set():
            try:
                client, _address = self._listener.accept()
                return client
            except socket.timeout:
                continue
        raise ConnectionAbortedError("proxy stopped before a client connected")

    def _forward_client_to_upstream(self) -> None:
        if self._client is None or self._upstream is None:
            raise AssertionError("proxy sockets are not initialized")
        buffer = bytearray()
        startup_complete = False
        try:
            while not self._stop.is_set():
                try:
                    chunk = self._client.recv(65536)
                except socket.timeout:
                    continue
                if not chunk:
                    return
                buffer.extend(chunk)
                while True:
                    if not startup_complete:
                        packet_length = _startup_packet_length(buffer)
                        if packet_length is None or len(buffer) < packet_length:
                            break
                        packet = bytes(buffer[:packet_length])
                        del buffer[:packet_length]
                        self._upstream.sendall(packet)
                        startup_complete = True
                        continue
                    packet_length = _frame_length(buffer)
                    if packet_length is None or len(buffer) < packet_length:
                        break
                    frame = bytes(buffer[:packet_length])
                    del buffer[:packet_length]
                    is_commit = _is_commit_query(_frontend_query(frame))
                    if is_commit:
                        self._commit_query_seen.set()
                    self._upstream.sendall(frame)
                    if is_commit:
                        self._commit_query_forwarded.set()
        except BaseException as exc:  # pragma: no cover - thread diagnostic path
            self._record_error(exc)

    def _forward_upstream_to_client(self) -> None:
        if self._client is None or self._upstream is None:
            raise AssertionError("proxy sockets are not initialized")
        buffer = bytearray()
        try:
            while not self._stop.is_set():
                try:
                    chunk = self._upstream.recv(65536)
                except socket.timeout:
                    continue
                if not chunk:
                    return
                buffer.extend(chunk)
                while True:
                    packet_length = _frame_length(buffer)
                    if packet_length is None or len(buffer) < packet_length:
                        break
                    frame = bytes(buffer[:packet_length])
                    del buffer[:packet_length]
                    if (
                        self._commit_query_seen.is_set()
                        and _command_complete_tag(frame) == b"COMMIT"
                    ):
                        self._commit_command_complete_seen.set()
                        self._close_socket(self._client)
                        self._client_closed_after_drop.set()
                        self._close_socket(self._upstream)
                        self._upstream_closed_after_drop.set()
                        self._stop.set()
                        return
                    self._client.sendall(frame)
        except BaseException as exc:  # pragma: no cover - thread diagnostic path
            self._record_error(exc)


__all__ = ["CommitAckDropReport", "PostgresCommitAckDropProxy"]
