"""Tests for the RAYS Studio GUI Python bridge (WebSocket adapter)."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

BRIDGE_SRC = (
    Path(__file__).resolve().parents[1]
    / "Electron_app"
    / "RAYS-Studio"
    / "bridge"
    / "src"
)
if str(BRIDGE_SRC) not in sys.path:
    sys.path.insert(0, str(BRIDGE_SRC))

from rays_bridge.ws_bridge import ApprovalManager, strip_ansi  # noqa: E402


class _RecordingBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict | None]] = []

    def emit(self, event_type: str, payload: dict | None = None) -> None:
        self.events.append((event_type, payload))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("plain text", "plain text"),
        ("\x1B[31mred\x1B[0m", "red"),
        ("", ""),
        ("line\x1B[1;32mok\x1B[0m!", "lineok!"),
    ],
)
def test_strip_ansi(raw: str, expected: str) -> None:
    assert strip_ansi(raw) == expected


def test_approval_manager_approve() -> None:
    bus = _RecordingBus()
    manager = ApprovalManager(bus=bus)
    results: list[bool] = []

    def request() -> None:
        results.append(manager.request("Allow edit?", timeout=5.0))

    worker = threading.Thread(target=request)
    worker.start()

    deadline = time.time() + 2.0
    approval_id = None
    while time.time() < deadline:
        for event_type, payload in bus.events:
            if event_type == "approval_request" and payload:
                approval_id = payload["id"]
                break
        if approval_id:
            break
        time.sleep(0.01)

    assert approval_id is not None
    manager.respond(approval_id, True)
    worker.join(timeout=2.0)
    assert results == [True]


def test_approval_manager_reject() -> None:
    bus = _RecordingBus()
    manager = ApprovalManager(bus=bus)
    results: list[bool] = []

    def request() -> None:
        results.append(manager.request("Delete file?", timeout=5.0))

    worker = threading.Thread(target=request)
    worker.start()

    deadline = time.time() + 2.0
    approval_id = None
    while time.time() < deadline:
        for event_type, payload in bus.events:
            if event_type == "approval_request" and payload:
                approval_id = payload["id"]
                break
        if approval_id:
            break
        time.sleep(0.01)

    assert approval_id is not None
    manager.respond(approval_id, False)
    worker.join(timeout=2.0)
    assert results == [False]


def test_approval_manager_unknown_id_is_ignored() -> None:
    bus = _RecordingBus()
    manager = ApprovalManager(bus=bus)
    manager.respond("does-not-exist", True)
