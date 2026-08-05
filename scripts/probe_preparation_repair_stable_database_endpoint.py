#!/usr/bin/env python3
"""Test-only stable TCP endpoint with atomically rotated PostgreSQL targets."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4


COPY_BUFFER_BYTES = 64 * 1024
UPSTREAM_CONNECT_TIMEOUT_SECONDS = 5.0


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"stable-endpoint state must be an object: {path}")
    return value


def _read_target(path: Path) -> tuple[str, int, str, int]:
    value = _read_json(path)
    host = value.get("target_host")
    port = value.get("target_port")
    label = value.get("target_label")
    epoch = value.get("epoch")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("stable-endpoint target_host must be a nonempty string")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("stable-endpoint target_port must be an integer port")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("stable-endpoint target_label must be a nonempty string")
    if type(epoch) is not int or epoch < 0:
        raise ValueError("stable-endpoint epoch must be a nonnegative integer")
    return host.strip(), port, label.strip(), epoch


def _write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


class StablePostgresEndpoint:
    def __init__(
        self,
        *,
        listen_host: str,
        listen_port: int,
        state_path: Path,
        ready_path: Path,
        event_path: Path,
        report_path: Path,
    ) -> None:
        self._listen_host = listen_host
        self._listen_port = listen_port
        self._state_path = state_path
        self._ready_path = ready_path
        self._event_path = event_path
        self._report_path = report_path
        self._stop = threading.Event()
        self._event_lock = threading.Lock()
        self._threads_lock = threading.Lock()
        self._threads: set[threading.Thread] = set()
        self._connection_count = 0
        self._connection_failure_count = 0
        self._target_counts: dict[str, int] = {}

    def stop(self) -> None:
        self._stop.set()

    def _append_event(self, value: dict[str, Any]) -> None:
        self._event_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
        with self._event_lock:
            with self._event_path.open("a", encoding="utf-8") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())

    @staticmethod
    def _pump(source: socket.socket, destination: socket.socket) -> None:
        try:
            while True:
                payload = source.recv(COPY_BUFFER_BYTES)
                if not payload:
                    break
                destination.sendall(payload)
        except (ConnectionError, OSError):
            pass
        finally:
            try:
                destination.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    def _handle_connection(self, client: socket.socket, peer: tuple[Any, ...]) -> None:
        connection_id = uuid4().hex
        upstream: socket.socket | None = None
        label = "unresolved"
        epoch = -1
        opened = False
        try:
            host, port, label, epoch = _read_target(self._state_path)
            upstream = socket.create_connection(
                (host, port),
                timeout=UPSTREAM_CONNECT_TIMEOUT_SECONDS,
            )
            upstream.settimeout(None)
            client.settimeout(None)
            opened = True
            with self._event_lock:
                self._connection_count += 1
                self._target_counts[label] = self._target_counts.get(label, 0) + 1
            self._append_event(
                {
                    "connection_id": connection_id,
                    "epoch": epoch,
                    "event": "connection_opened",
                    "peer_host": str(peer[0]) if peer else "unknown",
                    "target_label": label,
                }
            )

            client_to_upstream = threading.Thread(
                target=self._pump,
                args=(client, upstream),
                daemon=True,
            )
            upstream_to_client = threading.Thread(
                target=self._pump,
                args=(upstream, client),
                daemon=True,
            )
            client_to_upstream.start()
            upstream_to_client.start()
            client_to_upstream.join()
            upstream_to_client.join()
        except Exception as exc:
            with self._event_lock:
                self._connection_failure_count += 1
            self._append_event(
                {
                    "connection_id": connection_id,
                    "epoch": epoch,
                    "error_type": type(exc).__name__,
                    "event": "connection_failed",
                    "target_label": label,
                }
            )
        finally:
            for value in (client, upstream):
                if value is not None:
                    try:
                        value.close()
                    except OSError:
                        pass
            if opened:
                self._append_event(
                    {
                        "connection_id": connection_id,
                        "epoch": epoch,
                        "event": "connection_closed",
                        "target_label": label,
                    }
                )
            current = threading.current_thread()
            with self._threads_lock:
                self._threads.discard(current)

    def serve(self) -> None:
        _read_target(self._state_path)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self._listen_host, self._listen_port))
            listener.listen(64)
            listener.settimeout(0.2)
            _write_json_atomically(
                self._ready_path,
                {
                    "listen_host": self._listen_host,
                    "listen_port": self._listen_port,
                    "ready": True,
                    "router_pid": os.getpid(),
                },
            )
            while not self._stop.is_set():
                try:
                    client, peer = listener.accept()
                except socket.timeout:
                    continue
                thread = threading.Thread(
                    target=self._handle_connection,
                    args=(client, peer),
                    daemon=True,
                )
                with self._threads_lock:
                    self._threads.add(thread)
                thread.start()

        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            with self._threads_lock:
                remaining = tuple(self._threads)
            if not remaining:
                break
            for thread in remaining:
                thread.join(timeout=0.1)

        with self._threads_lock:
            leaked_threads = sum(1 for thread in self._threads if thread.is_alive())
        with self._event_lock:
            report = {
                "connection_count": self._connection_count,
                "connection_failure_count": self._connection_failure_count,
                "leaked_connection_threads": leaked_threads,
                "router_stopped": True,
                "target_counts": dict(sorted(self._target_counts.items())),
            }
        _write_json_atomically(self._report_path, report)
        if leaked_threads:
            raise RuntimeError(f"stable-endpoint connection threads leaked: {leaked_threads}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    endpoint = StablePostgresEndpoint(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        state_path=args.state,
        ready_path=args.ready,
        event_path=args.events,
        report_path=args.report,
    )

    def _stop(_signum: int, _frame: object) -> None:
        endpoint.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    endpoint.serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
