"""Smoke tests — package imports and basic structure."""

from __future__ import annotations

import bigtech_ai_stakes
from bigtech_ai_stakes import cli, data


def test_version() -> None:
    assert bigtech_ai_stakes.__version__ == "0.1.0"


def test_cli_app_exists() -> None:
    assert cli.app is not None
    assert cli.app.info.name == "bigtech-ai-stakes"


def test_data_paths_exist() -> None:
    assert data.EVENTS_CSV.exists(), f"missing: {data.EVENTS_CSV}"
    assert data.STAKES_CSV.exists(), f"missing: {data.STAKES_CSV}"


def test_loaders_return_nonempty() -> None:
    events = data.load_events()
    stakes = data.load_stakes()
    assert len(events) > 0
    assert len(stakes) > 0
