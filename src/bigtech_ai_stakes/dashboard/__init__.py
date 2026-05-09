"""Stage 3 — Streamlit dashboard helpers (Streamlit-free for testability)."""

from bigtech_ai_stakes.dashboard.data import (
    EXTRACTED_CSV,
    FIXTURES_CATALOG,
    FIXTURES_DIR,
    LOOKTHROUGH_PRESETS,
    LookthroughPreset,
    load_extracted,
    load_fixture,
)

__all__ = [
    "EXTRACTED_CSV",
    "FIXTURES_CATALOG",
    "FIXTURES_DIR",
    "LOOKTHROUGH_PRESETS",
    "LookthroughPreset",
    "load_extracted",
    "load_fixture",
]
