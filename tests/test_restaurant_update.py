import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.restaurant import RestaurantRepository


@pytest.mark.parametrize(
    "changes, expected_changes",
    [
        ({"name": "  New name  "}, {"name": "New name"}),
        ({"cuisine": "  Fusion  "}, {"cuisine": "Fusion"}),
        ({"description": "  Seasonal menu  "}, {"description": "Seasonal menu"}),
        (
            {"name": "New name", "cuisine": "Fusion", "description": "Seasonal menu"},
            {"name": "New name", "cuisine": "Fusion", "description": "Seasonal menu"},
        ),
    ],
)
def test_update_persists_only_supplied_fields_and_preserves_menus(
    isolated_restaurants_path, changes, expected_changes
):
    before = json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))
    target = before[1]  # Selecting the second record catches updating the wrong one.
    expected = {**target, **expected_changes}

    response = TestClient(app).patch(f"/restaurants/{target['id']}", json=changes)

    assert response.status_code == 200
    assert response.json() == {
        key: expected[key] for key in ("id", "name", "cuisine", "description")
    }
    reloaded = RestaurantRepository(isolated_restaurants_path).load_records()
    assert [record.model_dump(mode="json") for record in reloaded] == [before[0], expected]
    assert TestClient(app).get(f"/restaurants/{target['id']}/menu").json() == {
        "restaurant_id": target["id"], "items": target["menu_items"]
    }
    listed = TestClient(app).get("/restaurants").json()
    assert listed[1] == response.json()


def test_update_accepts_unchanged_value(isolated_restaurants_path):
    original = json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))
    target = original[0]

    response = TestClient(app).patch(
        f"/restaurants/{target['id']}", json={"name": target["name"]}
    )

    assert response.status_code == 200
    assert json.loads(isolated_restaurants_path.read_text(encoding="utf-8")) == original


def test_update_preserves_legacy_fields_and_omitted_unnormalized_text(
    isolated_restaurants_path,
):
    original = {
        "id": "legacy", "name": "  Original name  ", "cuisine": " ",
        "description": "Original", "legacy_note": {"keep": True},
    }
    isolated_restaurants_path.write_text(json.dumps([original]), encoding="utf-8")

    response = TestClient(app).patch("/restaurants/legacy", json={"description": "New"})

    assert response.status_code == 200
    assert response.json() == {
        "id": "legacy", "name": "  Original name  ", "cuisine": " ", "description": "New"
    }
    assert json.loads(isolated_restaurants_path.read_text(encoding="utf-8")) == [
        {**original, "description": "New", "menu_items": []}
    ]


@pytest.mark.parametrize("field", ["name", "cuisine", "description"])
@pytest.mark.parametrize("value", [None, "", " \t\n", 12, True, [], {}])
def test_update_rejects_invalid_fields_without_writing(
    isolated_restaurants_path, field, value
):
    original = isolated_restaurants_path.read_bytes()

    response = TestClient(app).patch("/restaurants/restaurant-001", json={field: value})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert isolated_restaurants_path.read_bytes() == original


@pytest.mark.parametrize(
    "body",
    [{}, [], {"name": "New", "id": "chosen"}, {"menu_items": []},
     {"restaurant_id": "chosen"}, {"menu_id": "chosen"}, {"unknown": "value"}],
)
def test_update_rejects_empty_or_unsupported_body_without_writing(
    isolated_restaurants_path, body
):
    original = isolated_restaurants_path.read_bytes()

    response = TestClient(app).patch("/restaurants/restaurant-001", json=body)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert isolated_restaurants_path.read_bytes() == original


@pytest.mark.parametrize("body", ["", "null", "{broken"])
def test_update_rejects_missing_null_or_malformed_json(isolated_restaurants_path, body):
    original = isolated_restaurants_path.read_bytes()

    response = TestClient(app).patch(
        "/restaurants/restaurant-001", content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert isolated_restaurants_path.read_bytes() == original


def test_update_unknown_opaque_id_does_not_create_restaurant(isolated_restaurants_path):
    original = isolated_restaurants_path.read_bytes()

    response = TestClient(app).patch("/restaurants/not-a-uuid", json={"name": "New"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Restaurant not found"}
    assert isolated_restaurants_path.read_bytes() == original
    # A failed lookup must release the shared lock for subsequent writes.
    assert TestClient(app).patch(
        "/restaurants/restaurant-001", json={"name": "Still writable"}
    ).status_code == 200


@pytest.mark.parametrize("identifier", ["restaurant-001", "unknown"])
@pytest.mark.parametrize("contents", [None, "{broken", '[{"id":"invalid"}]'])
def test_update_storage_error_precedes_not_found_and_exposes_no_details(
    isolated_restaurants_path, identifier, contents
):
    if contents is None:
        isolated_restaurants_path.unlink()
    else:
        isolated_restaurants_path.write_text(contents, encoding="utf-8")

    response = TestClient(app).patch(f"/restaurants/{identifier}", json={"name": "New"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}
    if contents is None:
        assert not isolated_restaurants_path.exists()
    else:
        assert isolated_restaurants_path.read_text(encoding="utf-8") == contents


def test_update_invalid_request_precedes_storage_and_lookup(isolated_restaurants_path):
    isolated_restaurants_path.unlink()

    response = TestClient(app).patch("/restaurants/unknown", json={"name": None})

    assert response.status_code == 422
    assert not isolated_restaurants_path.exists()


def test_update_save_failure_preserves_file_and_allows_retry(
    isolated_restaurants_path, monkeypatch
):
    original = isolated_restaurants_path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("private filesystem detail")

    with monkeypatch.context() as patch:
        patch.setattr("app.repositories.restaurant.os.replace", fail_replace)
        response = TestClient(app).patch(
            "/restaurants/restaurant-001", json={"name": "New"}
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}
    assert isolated_restaurants_path.read_bytes() == original
    assert list(isolated_restaurants_path.parent.iterdir()) == [isolated_restaurants_path]
    assert TestClient(app).patch(
        "/restaurants/restaurant-001", json={"name": "Retry"}
    ).status_code == 200
    assert RestaurantRepository(isolated_restaurants_path).get_record(
        "restaurant-001"
    ).name == "Retry"


def test_update_openapi_describes_partial_nonnullable_input_and_errors():
    schema = TestClient(app).get("/openapi.json").json()
    operation = schema["paths"]["/restaurants/{restaurant_id}"]["patch"]

    assert operation["description"]
    parameter = operation["parameters"][0]
    assert parameter["name"] == "restaurant_id"
    assert parameter["in"] == "path"
    assert parameter["required"] is True
    assert parameter["description"]
    assert operation["requestBody"]["required"] is True
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RestaurantUpdate"
    }
    responses = operation["responses"]
    assert set(responses) == {"200", "404", "422", "500"}
    for status, model in [("200", "Restaurant"), ("404", "ErrorResponse"),
                          ("422", "HTTPValidationError"), ("500", "ErrorResponse")]:
        assert responses[status]["content"]["application/json"]["schema"]["$ref"] == (
            f"#/components/schemas/{model}"
        )
    update = schema["components"]["schemas"]["RestaurantUpdate"]
    assert update["additionalProperties"] is False
    assert update["minProperties"] == 1
    assert not update.get("required")
    assert set(update["properties"]) == {"name", "cuisine", "description"}
    for field in update["properties"].values():
        assert field["type"] == "string"
        assert field["minLength"] == 1
        assert "default" not in field


def test_overlapping_updates_through_independent_services_preserve_both_changes(
    isolated_restaurants_path, monkeypatch
):
    import app.repositories.restaurant as repository_module
    from app.schemas.restaurant import RestaurantUpdate
    from app.services.restaurant import RestaurantService

    first = RestaurantRepository(isolated_restaurants_path)
    second = RestaurantRepository(isolated_restaurants_path)
    first_loaded = threading.Event()
    second_attempted_lock = threading.Event()
    real_lock = repository_module._mutation_lock
    real_load = first.load_records

    class ObservedLock:
        def __enter__(self):
            if first_loaded.is_set():
                second_attempted_lock.set()
            real_lock.acquire()

        def __exit__(self, *_):
            real_lock.release()

    def load_first():
        records = real_load()
        first_loaded.set()
        assert second_attempted_lock.wait(5)
        return records

    monkeypatch.setattr(repository_module, "_mutation_lock", ObservedLock())
    monkeypatch.setattr(first, "load_records", load_first)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(
            RestaurantService(first).update_restaurant, "restaurant-001",
            RestaurantUpdate(name="Concurrent name"),
        )
        assert first_loaded.wait(5)
        two = pool.submit(
            RestaurantService(second).update_restaurant, "restaurant-001",
            RestaurantUpdate(description="Concurrent description"),
        )
        assert one.result(timeout=10).name == "Concurrent name"
        saved = two.result(timeout=10)

    reloaded = RestaurantRepository(isolated_restaurants_path).get_record("restaurant-001")
    assert saved == reloaded.as_restaurant()
    assert reloaded.name == "Concurrent name"
    assert reloaded.description == "Concurrent description"
