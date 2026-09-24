import json

import pytest

from app.repositories.restaurant import RestaurantDataError, RestaurantRepository
from app.schemas.restaurant import Restaurant
from app.services.restaurant import RestaurantService


def test_service_returns_models_from_isolated_repository(isolated_restaurants_path):
    expected = [
        Restaurant.model_validate(record)
        for record in json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))
    ]
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    assert service.list_restaurants() == expected


def test_service_preserves_repository_failure(isolated_restaurants_path):
    isolated_restaurants_path.unlink()
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    with pytest.raises(RestaurantDataError):
        service.list_restaurants()
