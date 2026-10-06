import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.restaurant import RestaurantDataError, RestaurantRepository
from app.schemas.restaurant import MenuItem, MenuItemCreate
from app.services.restaurant import RestaurantNotFoundError, RestaurantService


BODY = {"name": "Soup", "description": "Hot soup", "price": "4.50"}
PATH = "/restaurants/target/menu/items"


@pytest.fixture
def menu_data(isolated_restaurants_path):
    records = [
        {
            "id": identifier,
            "name": f"Restaurant {identifier}",
            "cuisine": "Fusion",
            "description": "Test kitchen",
            "legacy_note": "Keep this field",
            "menu_items": [{"id": "existing", **BODY}],
        }
        for identifier in ("other", "target")
    ]
    isolated_restaurants_path.write_text(json.dumps(records), encoding="utf-8")
    return records


@pytest.mark.parametrize(
    ("price", "expected_price"), [("12.5", "12.50"), ("12", "12.00"), ("0", "0.00")]
)
def test_add_item_persists_under_correct_parent_and_can_be_browsed(
    isolated_restaurants_path, menu_data, price, expected_price
):
    response = TestClient(app).post(
        PATH, json={"name": "  Soup  ", "description": " Hot soup ", "price": price}
    )

    assert response.status_code == 201
    created = response.json()
    assert created == {**BODY, "id": created["id"], "price": expected_price}
    identifier = UUID(created["id"])
    assert identifier.version == 4
    assert str(identifier) == created["id"]
    assert created["id"] != "existing"

    stored = json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))
    assert stored == [
        menu_data[0],
        {**menu_data[1], "menu_items": [menu_data[1]["menu_items"][0], created]},
    ]
    fresh_repository = RestaurantRepository(isolated_restaurants_path)
    assert fresh_repository.get_record("target").menu_items[-1].model_dump() == created
    browsed = TestClient(app).get("/restaurants/target/menu")
    assert browsed.status_code == 200
    assert browsed.json() == {
        "restaurant_id": "target",
        "items": [menu_data[1]["menu_items"][0], created],
    }


@pytest.mark.parametrize("legacy", [True, False])
def test_add_item_to_empty_or_legacy_menu(isolated_restaurants_path, menu_data, legacy):
    menu_data[1].pop("menu_items")
    if not legacy:
        menu_data[1]["menu_items"] = []
    isolated_restaurants_path.write_text(json.dumps(menu_data), encoding="utf-8")

    response = TestClient(app).post(PATH, json=BODY)

    assert response.status_code == 201
    assert TestClient(app).get("/restaurants/target/menu").json()["items"] == [
        response.json()
    ]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "Soup", "description": "Hot soup"},
        {"description": "Hot soup", "price": "4.50"},
        {"name": "Soup", "price": "4.50"},
        {**BODY, "name": "   "},
        {**BODY, "description": ""},
        {**BODY, "name": 1},
        {**BODY, "description": None},
        *[{**BODY, "price": price} for price in (
            4.5, 0, True, None, "", "-1", "+1", "1e2", "1.234", "NaN",
            "Infinity", " 1.00", "1.00 ", "1.00\n", ".50", "1.",
        )],
        *[{**BODY, field: "client-value"} for field in (
            "id", "restaurant_id", "menu_id", "menu_items", "unknown",
        )],
    ],
)
def test_add_item_rejects_invalid_body_without_writing(
    isolated_restaurants_path, menu_data, body
):
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app).post(PATH, json=body)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert isolated_restaurants_path.read_bytes() == before


def test_add_item_unknown_parent_does_not_create_or_modify_records(
    isolated_restaurants_path, menu_data
):
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app).post("/restaurants/unknown/menu/items", json=BODY)

    assert response.status_code == 404
    assert response.json() == {"detail": "Restaurant not found"}
    assert isolated_restaurants_path.read_bytes() == before


@pytest.mark.parametrize("contents", [None, "{broken", "{}", '[{"id":"invalid"}]'])
def test_add_item_storage_errors_take_precedence_over_missing_parent(
    isolated_restaurants_path, contents
):
    if contents is None:
        isolated_restaurants_path.unlink()
    else:
        isolated_restaurants_path.write_text(contents, encoding="utf-8")

    response = TestClient(app).post(PATH, json=BODY)

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}
    if contents is None:
        assert not isolated_restaurants_path.exists()
    else:
        assert isolated_restaurants_path.read_text(encoding="utf-8") == contents


def test_add_item_validates_request_before_loading_storage(isolated_restaurants_path):
    isolated_restaurants_path.unlink()

    response = TestClient(app).post(PATH, json={**BODY, "price": -1})

    assert response.status_code == 422
    assert not isolated_restaurants_path.exists()


def test_add_item_failed_save_preserves_file_and_allows_later_request(
    isolated_restaurants_path, menu_data, monkeypatch
):
    before = isolated_restaurants_path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("private storage failure")

    with monkeypatch.context() as patch:
        patch.setattr("app.repositories.restaurant.os.replace", fail_replace)
        response = TestClient(app).post(PATH, json=BODY)

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}
    assert isolated_restaurants_path.read_bytes() == before
    assert list(isolated_restaurants_path.parent.iterdir()) == [isolated_restaurants_path]
    assert TestClient(app).post(PATH, json=BODY).status_code == 201


def test_add_item_retries_id_collision_within_parent(
    isolated_restaurants_path, menu_data, monkeypatch
):
    existing_id = "f20dbbc4-5266-4f7b-bc5d-35cef3632c1c"
    new_id = "a4143258-5314-4576-92b8-8838c5b69c1f"
    menu_data[1]["menu_items"][0]["id"] = existing_id
    # The same item ID under a different parent is allowed by the contract.
    menu_data[0]["menu_items"][0]["id"] = new_id
    isolated_restaurants_path.write_text(json.dumps(menu_data), encoding="utf-8")
    identifiers = iter([UUID(existing_id), UUID(new_id)])
    monkeypatch.setattr("app.services.restaurant.uuid4", lambda: next(identifiers))

    response = TestClient(app).post(PATH, json=BODY)

    assert response.status_code == 201
    assert response.json()["id"] == new_id
    stored = RestaurantRepository(isolated_restaurants_path).load_records()
    assert [item.id for item in stored[1].menu_items] == [existing_id, new_id]
    assert stored[0].model_dump() == menu_data[0]


def test_repeated_adds_preserve_items_with_distinct_stable_ids(menu_data):
    first = TestClient(app).post(PATH, json=BODY)
    second = TestClient(app).post(PATH, json=BODY)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert TestClient(app).get("/restaurants/target/menu").json()["items"] == [
        menu_data[1]["menu_items"][0], first.json(), second.json()
    ]


def test_service_add_item_returns_persisted_model(isolated_restaurants_path, menu_data):
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    item = service.add_menu_item("target", MenuItemCreate(**BODY))

    assert isinstance(item, MenuItem)
    reloaded = RestaurantRepository(isolated_restaurants_path).get_record("target")
    assert reloaded.menu_items[-1] == item
    assert item.model_dump(exclude={"id"}) == BODY


def test_service_add_item_raises_for_unknown_parent(isolated_restaurants_path, menu_data):
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    with pytest.raises(RestaurantNotFoundError):
        service.add_menu_item("missing", MenuItemCreate(**BODY))


def test_service_add_item_propagates_storage_failure(isolated_restaurants_path):
    isolated_restaurants_path.unlink()
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    with pytest.raises(RestaurantDataError):
        service.add_menu_item("target", MenuItemCreate(**BODY))


def test_add_item_openapi_describes_request_parent_and_responses():
    schema = TestClient(app).get("/openapi.json").json()
    operation = schema["paths"]["/restaurants/{restaurant_id}/menu/items"]["post"]

    assert operation["description"]
    parameter = operation["parameters"][0]
    assert parameter["name"] == "restaurant_id"
    assert parameter["in"] == "path"
    assert parameter["required"]
    assert parameter["description"]
    assert operation["requestBody"]["required"]
    request = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request["$ref"] == "#/components/schemas/MenuItemCreate"
    model = schema["components"]["schemas"]["MenuItemCreate"]
    assert set(model["required"]) == {"name", "description", "price"}
    assert set(model["properties"]) == {"name", "description", "price"}
    assert model["additionalProperties"] is False
    assert model["properties"]["price"]["type"] == "string"
    responses = operation["responses"]
    assert set(responses) == {"201", "404", "422", "500"}
    for status, model_name in (("201", "MenuItem"), ("404", "ErrorResponse"),
                               ("500", "ErrorResponse"), ("422", "HTTPValidationError")):
        assert responses[status]["content"]["application/json"]["schema"]["$ref"] == (
            f"#/components/schemas/{model_name}"
        )
