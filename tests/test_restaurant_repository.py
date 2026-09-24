import json
from pathlib import Path
from shutil import copyfile

import pytest


def test_repository_loads_representative_restaurants_from_isolated_copy(tmp_path):
    from app.repositories.restaurant import RestaurantRepository
    from app.schemas.restaurant import Restaurant

    source = Path(__file__).resolve().parents[1] / "data" / "restaurants.json"
    isolated_path = tmp_path / "restaurants.json"
    copyfile(source, isolated_path)

    restaurants = RestaurantRepository(isolated_path).list_restaurants()

    assert len(restaurants) >= 2
    assert all(isinstance(restaurant, Restaurant) for restaurant in restaurants)
    assert [restaurant.model_dump() for restaurant in restaurants] == json.loads(
        isolated_path.read_text(encoding="utf-8")
    )
    assert len({restaurant.id for restaurant in restaurants}) == len(restaurants)


def test_repository_uses_configured_data_path(tmp_path, monkeypatch):
    from app.repositories.restaurant import RestaurantRepository

    isolated_path = tmp_path / "alternate-restaurants.json"
    isolated_path.write_text(
        json.dumps(
            [
                {
                    "id": "restaurant-test",
                    "name": "Test Kitchen",
                    "cuisine": "Fusion",
                    "description": "Temporary test restaurant",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RESTAURANTS_DATA_PATH", str(isolated_path))

    restaurants = RestaurantRepository().list_restaurants()

    assert [restaurant.id for restaurant in restaurants] == ["restaurant-test"]


def test_repository_reports_missing_data_file(tmp_path):
    from app.repositories.restaurant import RestaurantDataError, RestaurantRepository

    missing_path = tmp_path / "missing.json"

    with pytest.raises(RestaurantDataError, match="missing.json"):
        RestaurantRepository(missing_path).list_restaurants()


def test_repository_reports_malformed_json(tmp_path):
    from app.repositories.restaurant import RestaurantDataError, RestaurantRepository

    isolated_path = tmp_path / "restaurants.json"
    isolated_path.write_text("{invalid JSON", encoding="utf-8")

    with pytest.raises(RestaurantDataError, match="restaurants.json"):
        RestaurantRepository(isolated_path).list_restaurants()


def test_repository_rejects_invalid_restaurant_record(tmp_path):
    from app.repositories.restaurant import RestaurantDataError, RestaurantRepository

    isolated_path = tmp_path / "restaurants.json"
    isolated_path.write_text(
        json.dumps([{"name": "Incomplete Kitchen", "cuisine": "Fusion"}]),
        encoding="utf-8",
    )

    with pytest.raises(RestaurantDataError, match="restaurants.json"):
        RestaurantRepository(isolated_path).list_restaurants()
