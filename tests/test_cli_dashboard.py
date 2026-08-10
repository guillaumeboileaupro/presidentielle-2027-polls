from __future__ import annotations

import subprocess

import pytest

from presidentielle2027 import cli


class DummyProcess:
    def __init__(self, *, running: bool = True) -> None:
        self.running = running
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return None if self.running else 0

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: int) -> int:
        self.running = False
        return 0

    def kill(self) -> None:
        self.killed = True


def test_start_dashboard_scraper_uses_current_python(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    process = DummyProcess()

    def fake_popen(command: list[str]) -> DummyProcess:
        calls.append(command)
        return process

    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)

    assert cli._start_dashboard_scraper() is process
    assert calls == [[cli.sys.executable, "-m", "presidentielle2027.cli", "auto-refresh-pipeline"]]


def test_stop_dashboard_scraper_terminates_running_process() -> None:
    process = DummyProcess()

    cli._stop_dashboard_scraper(process)  # type: ignore[arg-type]

    assert process.terminated
    assert not process.killed


def test_stop_dashboard_scraper_kills_process_after_timeout() -> None:
    process = DummyProcess()

    def timeout_wait(timeout: int) -> int:
        if not process.killed:
            raise subprocess.TimeoutExpired("scraper", timeout)
        return 0

    process.wait = timeout_wait  # type: ignore[method-assign]

    cli._stop_dashboard_scraper(process)  # type: ignore[arg-type]

    assert process.terminated
    assert process.killed
