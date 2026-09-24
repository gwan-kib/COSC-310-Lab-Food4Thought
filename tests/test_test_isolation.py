import json
import os
from pathlib import Path

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
