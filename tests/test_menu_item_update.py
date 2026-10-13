# Verify Food4Thought's partial menu-item updates within the specified restaurant.
# It covers validation, unchanged identifiers and relationships, persistence failures,
# error responses, OpenAPI, and overlapping mutations.

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.restaurant import RestaurantRepository


PATH = "/restaurants/target/menu/items/shared"
ITEM = {"id": "shared", "name": "Soup", "description": "Hot soup", "price": "4.50"}


@pytest.fixture
def menu_data(isolated_restaurants_path):
    records = [
        {
            "id": identifier,
            "name": f"Restaurant {identifier}",
            "cuisine": "Fusion",
            "description": "Test kitchen",
            "legacy_note": {"keep": True},
            "menu_items": [
                {**ITEM, "id": "first"},
                dict(ITEM),
            ],
        }
        for identifier in ("other", "target")
    ]
    isolated_restaurants_path.write_text(json.dumps(records), encoding="utf-8")
    return records


@pytest.mark.parametrize(
    "changes, expected_changes",
    [
        ({"name": "  Stew  "}, {"name": "Stew"}),
        ({"description": "  Seasonal soup  "}, {"description": "Seasonal soup"}),
        ({"price": "12"}, {"price": "12.00"}),
        ({"price": "12.5"}, {"price": "12.50"}),
        ({"price": "0"}, {"price": "0.00"}),
        ({"name": "Soup"}, {"name": "Soup"}),
        (
            {"name": "Stew", "description": "Seasonal", "price": "8.25"},
            {"name": "Stew", "description": "Seasonal", "price": "8.25"},
        ),
    ],
)
def test_update_persists_only_supplied_fields_under_correct_parent(
    isolated_restaurants_path, menu_data, changes, expected_changes
):
    response = TestClient(app).patch(PATH, json=changes)

    expected = {**ITEM, **expected_changes}
    assert response.status_code == 200
    assert response.json() == expected
    menu_data[1]["menu_items"][1] = expected
    assert json.loads(isolated_restaurants_path.read_text(encoding="utf-8")) == menu_data
    reloaded = RestaurantRepository(isolated_restaurants_path).get_record("target")
    assert reloaded.menu_items[1].model_dump() == expected
    assert TestClient(app).get("/restaurants/target/menu").json() == {
        "restaurant_id": "target", "items": menu_data[1]["menu_items"]
    }


@pytest.mark.parametrize(
    "body",
    [
        {}, [], {"name": "Valid", "price": None},
        *[{field: value} for field in ("name", "description")
          for value in (None, "", " \t\n", 12, True, [], {})],
        *[{"price": value} for value in (
            None, 4.5, 0, True, [], {}, "", "-1", "+1", "1e2", "1.234",
            "NaN", "Infinity", " 1.00", "1.00 ", "1.00\n", ".50", "1.",
        )],
        *[{"name": "Valid", field: "chosen"} for field in (
            "id", "restaurant_id", "menu_id", "menu_items", "unknown",
        )],
    ],
)
def test_update_rejects_invalid_input_without_writing(
    isolated_restaurants_path, menu_data, body
):
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app).patch(PATH, json=body)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert isolated_restaurants_path.read_bytes() == before


@pytest.mark.parametrize(
    "body",
    ["", "null", "{broken", '{"price":1e400}', '{"price":NaN}',
     r'{"name":"\ud800"}', '{"extra":{"nested":[Infinity]}}'],
)
def test_update_rejected_raw_json_has_serializable_error(
    isolated_restaurants_path, menu_data, body
):
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app, raise_server_exceptions=False).patch(
        PATH, content=body, headers={"Content-Type": "application/json"}
    )

    def reject_nonfinite(value):
        raise AssertionError(f"Non-JSON number in response: {value}")

    assert response.status_code == 422
    assert isinstance(json.loads(response.content, parse_constant=reject_nonfinite)["detail"], list)
    assert isolated_restaurants_path.read_bytes() == before


@pytest.mark.parametrize(
    "parent, item, detail",
    [("missing", "shared", "Restaurant not found"),
     ("target", "missing", "Menu item not found"),
     ("target", "other-only", "Menu item not found")],
)
def test_update_missing_or_wrong_parent_item_does_not_write(
    isolated_restaurants_path, menu_data, parent, item, detail
):
    menu_data[0]["menu_items"].append({**ITEM, "id": "other-only"})
    isolated_restaurants_path.write_text(json.dumps(menu_data), encoding="utf-8")
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app).patch(
        f"/restaurants/{parent}/menu/items/{item}", json={"price": "7"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": detail}
    assert isolated_restaurants_path.read_bytes() == before
    assert TestClient(app).patch(PATH, json={"price": "7"}).status_code == 200


@pytest.mark.parametrize("legacy", [False, True])
def test_update_empty_menu_does_not_create_item(isolated_restaurants_path, menu_data, legacy):
    menu_data[1]["menu_items"] = []
    if legacy:
        menu_data[1].pop("menu_items")
    isolated_restaurants_path.write_text(json.dumps(menu_data), encoding="utf-8")
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app).patch(PATH, json={"price": "7"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Menu item not found"}
    assert isolated_restaurants_path.read_bytes() == before


@pytest.mark.parametrize("contents", [None, "{broken", "{}", '[{"id":"invalid"}]'])
def test_update_storage_failure_precedes_lookup(isolated_restaurants_path, contents):
    if contents is None:
        isolated_restaurants_path.unlink()
    else:
        isolated_restaurants_path.write_text(contents, encoding="utf-8")

    response = TestClient(app).patch(PATH, json={"price": "7"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}
    if contents is None:
        assert not isolated_restaurants_path.exists()
    else:
        assert isolated_restaurants_path.read_text(encoding="utf-8") == contents


@pytest.mark.parametrize("corruption", ["restaurant-id", "item-id", "unrelated-price"])
def test_update_rejects_corrupt_stored_relationships(
    isolated_restaurants_path, menu_data, corruption
):
    if corruption == "restaurant-id":
        menu_data[0]["id"] = "target"
    elif corruption == "item-id":
        menu_data[1]["menu_items"][0]["id"] = "shared"
    else:
        menu_data[0]["menu_items"][0]["price"] = "-1"
    isolated_restaurants_path.write_text(json.dumps(menu_data), encoding="utf-8")
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app).patch(PATH, json={"price": "7"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}
    assert isolated_restaurants_path.read_bytes() == before


def test_update_validates_request_before_storage(isolated_restaurants_path):
    isolated_restaurants_path.unlink()
    response = TestClient(app).patch(PATH, json={"price": None})
    assert response.status_code == 422
    assert not isolated_restaurants_path.exists()


def test_update_failed_save_preserves_file_and_allows_retry(
    isolated_restaurants_path, menu_data, monkeypatch
):
    before = isolated_restaurants_path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("private storage detail")

    with monkeypatch.context() as patch:
        patch.setattr("app.repositories.restaurant.os.replace", fail_replace)
        response = TestClient(app).patch(PATH, json={"price": "7"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}
    assert isolated_restaurants_path.read_bytes() == before
    assert list(isolated_restaurants_path.parent.iterdir()) == [isolated_restaurants_path]
    assert TestClient(app).patch(PATH, json={"price": "7"}).json() == {**ITEM, "price": "7.00"}


def test_update_openapi_describes_partial_input_and_scoped_errors():
    schema = TestClient(app).get("/openapi.json").json()
    operation = schema["paths"]["/restaurants/{restaurant_id}/menu/items/{item_id}"]["patch"]
    assert operation["description"]
    assert {p["name"] for p in operation["parameters"]} == {"restaurant_id", "item_id"}
    assert all(p["required"] and p["in"] == "path" and p["description"]
               for p in operation["parameters"])
    assert operation["requestBody"]["required"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/MenuItemUpdate"
    }
    assert {"200", "404", "422", "500"} <= operation["responses"].keys()
    for code, model in [("200", "MenuItem"), ("404", "ErrorResponse"),
                        ("422", "HTTPValidationError"), ("500", "ErrorResponse")]:
        assert operation["responses"][code]["content"]["application/json"]["schema"] == {
            "$ref": f"#/components/schemas/{model}"
        }
    update = schema["components"]["schemas"]["MenuItemUpdate"]
    assert not update.get("required")
    assert update["minProperties"] == 1
    assert update["additionalProperties"] is False
    assert set(update["properties"]) == {"name", "description", "price"}
    for field in update["properties"].values():
        assert field["type"] == "string"
        assert "default" not in field
    assert update["properties"]["name"]["minLength"] == 1
    assert update["properties"]["description"]["minLength"] == 1
    assert update["properties"]["price"]["pattern"] == r"^[0-9]+(\.[0-9]{1,2})?$"


@pytest.mark.parametrize("other_write", ["update-item", "add-item", "update-restaurant"])
def test_overlapping_menu_update_and_existing_writes_preserve_both_changes(
    isolated_restaurants_path, menu_data, monkeypatch, other_write
):
    import app.repositories.restaurant as repository_module
    from app.schemas.restaurant import MenuItemCreate, MenuItemUpdate, RestaurantUpdate
    from app.services.restaurant import RestaurantService

    first = RestaurantRepository(isolated_restaurants_path)
    second = RestaurantRepository(isolated_restaurants_path)
    loaded = threading.Event()
    waiting = threading.Event()
    real_lock = repository_module._mutation_lock
    real_load = first.load_records

    class ObservedLock:
        def __enter__(self):
            if loaded.is_set():
                waiting.set()
            real_lock.acquire()

        def __exit__(self, *_):
            real_lock.release()

    def load_first():
        records = real_load()
        loaded.set()
        assert waiting.wait(5)
        return records

    monkeypatch.setattr(repository_module, "_mutation_lock", ObservedLock())
    monkeypatch.setattr(first, "load_records", load_first)
    service = RestaurantService(second)
    if other_write == "update-item":
        method, args = service.update_menu_item, ("shared", MenuItemUpdate(name="Stew"))
    elif other_write == "add-item":
        method, args = service.add_menu_item, (MenuItemCreate(name="New", description="New item", price="2"),)
    else:
        method, args = service.update_restaurant, (RestaurantUpdate(name="New restaurant"),)

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(RestaurantService(first).update_menu_item, "target", "shared",
                          MenuItemUpdate(price="7"))
        assert loaded.wait(5)
        two = pool.submit(method, "target", *args)
        assert one.result(timeout=10).price == "7.00"
        second_result = two.result(timeout=10)

    saved = RestaurantRepository(isolated_restaurants_path).get_record("target")
    assert saved.menu_items[1].price == "7.00"
    if other_write == "update-item":
        assert saved.menu_items[1].name == "Stew"
    elif other_write == "add-item":
        assert len(saved.menu_items) == 3
        assert saved.menu_items[-1] == second_result
    else:
        assert saved.name == "New restaurant"
    assert RestaurantRepository(isolated_restaurants_path).get_record("other").model_dump() == menu_data[0]
