"""Give Food4Thought contract consumers disposable paths for every proposed store.
These fixtures reuse M1's restaurant copy and never initialize application data.
"""

import pytest


@pytest.fixture
def m2_store_paths(tmp_path, monkeypatch, isolated_restaurants_path):
    paths = {"restaurants": isolated_restaurants_path}
    for store in ("customers", "carts", "orders"):
        path = tmp_path / f"{store}.json"
        path.write_text("[]\n", encoding="utf-8")
        monkeypatch.setenv(f"{store.upper()}_DATA_PATH", str(path))
        paths[store] = path
    return paths
