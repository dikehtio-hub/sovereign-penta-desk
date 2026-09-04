"""Shared pytest configuration for the Polymarket Monarch test suite.

Every test in this suite is fully offline: no test may touch the network or the
production SQLite database.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def temp_db(tmp_path):
    """An isolated SQLite path so tests never write to data/polymarket_whales.db."""
    return tmp_path / "test_whales.db"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch, request):
    """
    Fail loudly if a test performs a real HTTP request.

    Tests that exercise the HTTP layer patch `requests.get` themselves, which
    takes precedence over this guard.
    """
    if "allow_network" in request.keywords:
        return

    import requests

    def _blocked(*args, **kwargs):
        raise AssertionError(
            f"Unexpected real network call in test: {args[:1]}. "
            "Patch requests.get or mark the test with @pytest.mark.allow_network."
        )

    monkeypatch.setattr(requests, "get", _blocked)
