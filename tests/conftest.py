"""Shared pytest fixtures that keep tests away from committed data.

Every test runs with RESTAURANTS_DATA_PATH pointing at a temporary copy of
data/restaurants.json, so code that uses the default configured path can
never write to the representative data in the repository. A session-level
check also fails the run if any file under data/ changed while tests ran.
"""

import hashlib
import shutil
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _snapshot_data_files() -> dict[str, str]:
    return {
        str(path.relative_to(DATA_DIR)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(DATA_DIR.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="session", autouse=True)
def committed_data_is_unchanged():
    before = _snapshot_data_files()
    yield
    after = _snapshot_data_files()
    assert after == before, "Tests modified committed files under data/"


@pytest.fixture(autouse=True)
def isolated_restaurants_path(tmp_path, monkeypatch) -> Path:
    """Point the app at a per-test copy of the representative restaurant data."""
    path = tmp_path / "restaurants.json"
    shutil.copyfile(DATA_DIR / "restaurants.json", path)
    monkeypatch.setenv("RESTAURANTS_DATA_PATH", str(path))
    return path
