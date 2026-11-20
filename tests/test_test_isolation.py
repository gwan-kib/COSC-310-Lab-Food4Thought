# Verify that Food4Thought's shared fixtures route every store to temporary data.
# Check that implicit configuration and writes to the restaurant copy leave
# committed data untouched.

import json
import os
from pathlib import Path

import pytest

COMMITTED_DATA = Path(__file__).resolve().parents[1] / "data" / "restaurants.json"


def test_restaurant_data_path_is_isolated_by_default(isolated_restaurants_path):
    configured = Path(os.environ["RESTAURANTS_DATA_PATH"])

    assert configured == isolated_restaurants_path
    assert configured.resolve() != COMMITTED_DATA.resolve()


def test_isolated_copy_starts_with_representative_data(isolated_restaurants_path):
    assert json.loads(isolated_restaurants_path.read_text(encoding="utf-8")) == json.loads(
        COMMITTED_DATA.read_text(encoding="utf-8")
    )


def test_writes_to_isolated_copy_do_not_reach_committed_data(isolated_restaurants_path):
    original = COMMITTED_DATA.read_bytes()

    isolated_restaurants_path.write_text("[]", encoding="utf-8")

    assert COMMITTED_DATA.read_bytes() == original


@pytest.mark.parametrize("store", ["customers", "carts", "orders", "staff", "sessions"])
def test_m2_store_is_isolated_without_requesting_a_fixture(tmp_path, store):
    path = tmp_path / f"{store}.json"
    configured = os.environ.get(f"{store.upper()}_DATA_PATH")

    assert configured == str(path)
    if store == "orders":
        # The repository must report a missing store without creating one.
        assert not path.exists()
    else:
        assert json.loads(path.read_text(encoding="utf-8")) == []


def test_requesting_initialized_m2_stores_creates_order_file(m2_store_paths):
    order_path = m2_store_paths["orders"]
    assert json.loads(order_path.read_text(encoding="utf-8")) == []
