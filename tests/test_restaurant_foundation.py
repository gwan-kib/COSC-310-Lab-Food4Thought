import json
from pathlib import Path

import pytest
from pydantic import ValidationError


def test_restaurant_model_defines_meaningful_response_fields():
    from app.schemas.restaurant import Restaurant

    restaurant = Restaurant(
        id="restaurant-001",
        name="Cedar Bowl",
        cuisine="Japanese",
        description="Rice bowls and noodles",
    )

    assert restaurant.model_dump() == {
        "id": "restaurant-001",
        "name": "Cedar Bowl",
        "cuisine": "Japanese",
        "description": "Rice bowls and noodles",
    }


def test_restaurant_model_rejects_empty_identifiers():
    from app.schemas.restaurant import Restaurant

    with pytest.raises(ValidationError):
        Restaurant(
            id="",
            name="Cedar Bowl",
            cuisine="Japanese",
            description="Rice bowls and noodles",
        )


def test_representative_data_contains_distinct_valid_restaurants():
    from app.schemas.restaurant import Restaurant

    path = Path(__file__).resolve().parents[1] / "data" / "restaurants.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    restaurants = [Restaurant.model_validate(record) for record in records]

    assert len(restaurants) >= 2
    assert len({restaurant.id for restaurant in restaurants}) == len(restaurants)


def test_restaurant_data_path_can_be_overridden_for_isolated_tests(tmp_path, monkeypatch):
    from app.core.config import get_restaurants_data_path

    isolated_path = tmp_path / "restaurants.json"
    monkeypatch.setenv("RESTAURANTS_DATA_PATH", str(isolated_path))

    assert get_restaurants_data_path() == isolated_path


def test_default_restaurant_data_path_points_to_project_data(monkeypatch):
    from app.core.config import get_restaurants_data_path

    monkeypatch.delenv("RESTAURANTS_DATA_PATH", raising=False)

    assert get_restaurants_data_path() == (
        Path(__file__).resolve().parents[1] / "data" / "restaurants.json"
    )
