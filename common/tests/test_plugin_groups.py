"""Smoke test that the pyproject.toml group layout resolves correctly
(Refactor #9).

We don't actually rebuild containers here — we just verify the TOML structure
so an accidental refactor of the dependency groups (renaming, splitting,
merging) trips a test immediately rather than at deploy time.
"""
from __future__ import annotations

import tomllib
from pathlib import Path


def _load_groups() -> dict:
    path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data["dependency-groups"]


def test_conserver_slim_group_exists():
    groups = _load_groups()
    assert "conserver_slim" in groups, (
        "conserver_slim group required for slim container image; see "
        "docker/Dockerfile.conserver.slim"
    )


def test_link_ml_group_exists():
    groups = _load_groups()
    assert "link_ml" in groups, "link_ml group required for ML-heavy links"


def test_conserver_group_still_includes_link_ml():
    """Backward compat: `uv sync --group conserver` must still pull ML libs
    so existing Dockerfile.conserver + CI keep working unchanged."""
    groups = _load_groups()
    conserver = groups["conserver"]
    includes = [entry.get("include-group") for entry in conserver if isinstance(entry, dict)]
    assert "link_ml" in includes, (
        "conserver must include-group link_ml so the full image keeps its"
        " transcribe/analyze capabilities"
    )


def test_conserver_slim_does_not_include_link_ml():
    groups = _load_groups()
    slim = groups["conserver_slim"]
    slim_includes = [
        entry.get("include-group") for entry in slim if isinstance(entry, dict)
    ]
    assert "link_ml" not in slim_includes, (
        "conserver_slim must NOT include link_ml — that's the whole point"
    )


def test_link_ml_does_not_accidentally_bundle_storage():
    """ML packages and storage backends must be independently selectable."""
    groups = _load_groups()
    ml = groups["link_ml"]
    includes = [entry.get("include-group") for entry in ml if isinstance(entry, dict)]
    assert "storage" not in includes
