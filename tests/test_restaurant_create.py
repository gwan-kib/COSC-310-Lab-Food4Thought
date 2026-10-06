import json
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.restaurant import RestaurantDataError, RestaurantRepository


def _record(identifier: str, name: str) -> dict[str, object]:
    return {
        "id": identifier,
        "name": name,
        "cuisine": "Japanese",
        "description": "Rice and noodles",
    }


def test_create_restaurant_persists_and_preserves_existing_menu(isolated_restaurants_path):
    existing = _record("restaurant-001", "Cedar Bowl")
    existing["menu_items"] = [
        {
            "id": "item-001",
            "name": "Vegetable bowl",
            "description": "Rice and vegetables",
            "price": "12.50",
        }
    ]
    isolated_restaurants_path.write_text(json.dumps([existing]), encoding="utf-8")

    response = TestClient(app).post(
        "/restaurants",
        json={
            "name": "  New Cafe  ",
            "cuisine": "  Cafe ",
            "description": "  Fresh food  ",
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created == {
        "id": created["id"],
        "name": "New Cafe",
        "cuisine": "Cafe",
        "description": "Fresh food",
    }
    assert str(UUID(created["id"], version=4)) == created["id"]
    assert created["id"] != existing["id"]

    stored = json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))
    assert stored[0] == existing
    assert stored[1] == {**created, "menu_items": []}
    reloaded = RestaurantRepository(isolated_restaurants_path).load_records()
    assert [item.id for item in reloaded[0].menu_items] == ["item-001"]
    listed = TestClient(app).get("/restaurants")
    assert listed.status_code == 200
    assert listed.json() == [
        {key: value for key, value in existing.items() if key != "menu_items"},
        created,
    ]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "", "cuisine": "Cafe", "description": "Food"},
        {"name": "   ", "cuisine": "Cafe", "description": "Food"},
        {"name": 4, "cuisine": "Cafe", "description": "Food"},
        {"name": "Cafe", "cuisine": "Cafe", "description": None},
        {"name": "Cafe", "cuisine": "Cafe", "description": "Food", "id": "chosen"},
        {"name": "Cafe", "cuisine": "Cafe", "description": "Food", "menu_items": []},
    ],
)
def test_create_rejects_invalid_body_without_writing(isolated_restaurants_path, body):
    original = isolated_restaurants_path.read_bytes()

    response = TestClient(app).post("/restaurants", json=body)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert isolated_restaurants_path.read_bytes() == original


def test_create_reports_storage_failure_without_exposing_details(isolated_restaurants_path):
    isolated_restaurants_path.unlink()

    response = TestClient(app).post(
        "/restaurants",
        json={"name": "Cafe", "cuisine": "Cafe", "description": "Food"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}


def test_create_save_failure_keeps_existing_file_and_removes_temp_file(
    isolated_restaurants_path, monkeypatch
):
    original = isolated_restaurants_path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("private write failure")

    monkeypatch.setattr("app.repositories.restaurant.os.replace", fail_replace)
    response = TestClient(app).post(
        "/restaurants",
        json={"name": "Cafe", "cuisine": "Cafe", "description": "Food"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}
    assert isolated_restaurants_path.read_bytes() == original
    assert list(isolated_restaurants_path.parent.iterdir()) == [isolated_restaurants_path]


def test_create_openapi_describes_contract():
    operation = TestClient(app).get("/openapi.json").json()["paths"]["/restaurants"]["post"]

    assert operation["description"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    response_schema = operation["responses"]["201"]["content"]["application/json"]["schema"]
    assert request_schema["$ref"] == "#/components/schemas/RestaurantCreate"
    assert response_schema["$ref"] == "#/components/schemas/Restaurant"
    assert "422" in operation["responses"]
    assert "500" in operation["responses"]


def test_repository_rejects_corrupt_menu_and_duplicate_ids(isolated_restaurants_path):
    cases = [
        [_record("same", "First"), _record("same", "Second")],
        [{**_record("one", "First"), "menu_items": None}],
        [{**_record("one", "First"), "menu_items": [{"id": "bad"}]}],
        [{**_record("one", "First"), "menu_items": [
            {"id": "same", "name": "A", "description": "A", "price": "1.00"},
            {"id": "same", "name": "B", "description": "B", "price": "2.00"},
        ]}],
    ]
    for records in cases:
        isolated_restaurants_path.write_text(json.dumps(records), encoding="utf-8")
        with pytest.raises(RestaurantDataError):
            RestaurantRepository(isolated_restaurants_path).list_restaurants()


def test_legacy_record_loads_with_empty_menu_without_rewriting(isolated_restaurants_path):
    # Committed data now has menus, so write M0-style records without menu_items.
    isolated_restaurants_path.write_text(
        json.dumps([_record("restaurant-001", "Cedar Bowl")]), encoding="utf-8"
    )
    original = isolated_restaurants_path.read_bytes()

    records = RestaurantRepository(isolated_restaurants_path).load_records()

    assert all(record.menu_items == [] for record in records)
    assert isolated_restaurants_path.read_bytes() == original


def test_create_preserves_unrecognized_legacy_restaurant_fields(isolated_restaurants_path):
    existing = {**_record("legacy", "Existing"), "legacy_note": "Keep this value"}
    isolated_restaurants_path.write_text(json.dumps([existing]), encoding="utf-8")

    response = TestClient(app).post(
        "/restaurants",
        json={"name": "New", "cuisine": "Cafe", "description": "Food"},
    )

    assert response.status_code == 201
    stored = json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))
    assert stored[0]["legacy_note"] == "Keep this value"
    listed = TestClient(app).get("/restaurants")
    assert listed.status_code == 200
    assert "legacy_note" not in listed.json()[0]


@pytest.mark.parametrize("price", [12.5, "-1", "1.234", " 1.00", "NaN", "1e2"])
def test_menu_item_rejects_invalid_price(price):
    from pydantic import ValidationError

    from app.schemas.restaurant import MenuItem

    with pytest.raises(ValidationError):
        MenuItem(id="item-001", name="Soup", description="Hot soup", price=price)


def test_menu_item_normalizes_price():
    from app.schemas.restaurant import MenuItem

    item = MenuItem(id="item-001", name="Soup", description="Hot soup", price="12.5")

    assert item.price == "12.50"


def test_create_retries_generated_id_collision(isolated_restaurants_path, monkeypatch):
    existing_id = "f20dbbc4-5266-4f7b-bc5d-35cef3632c1c"
    new_id = "a4143258-5314-4576-92b8-8838c5b69c1f"
    isolated_restaurants_path.write_text(
        json.dumps([_record(existing_id, "Existing")]), encoding="utf-8"
    )
    identifiers = iter([UUID(existing_id), UUID(new_id)])
    monkeypatch.setattr("app.services.restaurant.uuid4", lambda: next(identifiers))

    response = TestClient(app).post(
        "/restaurants",
        json={"name": "New", "cuisine": "Cafe", "description": "Food"},
    )

    assert response.status_code == 201
    assert response.json()["id"] == new_id
    reloaded = RestaurantRepository(isolated_restaurants_path).load_records()
    assert [record.id for record in reloaded] == [existing_id, new_id]


def test_invalid_mutated_collection_is_not_saved(isolated_restaurants_path):
    original = isolated_restaurants_path.read_bytes()

    def corrupt(records):
        records[0].name = ""

    with pytest.raises(RestaurantDataError):
        RestaurantRepository(isolated_restaurants_path).mutate_records(corrupt)

    assert isolated_restaurants_path.read_bytes() == original


def test_mutation_returns_normalized_persisted_records(isolated_restaurants_path):
    existing = {
        **_record("restaurant-001", "Cedar Bowl"),
        "menu_items": [
            {
                "id": "item-001",
                "name": "Soup",
                "description": "Hot soup",
                "price": "12.50",
            }
        ],
    }
    isolated_restaurants_path.write_text(json.dumps([existing]), encoding="utf-8")
    repository = RestaurantRepository(isolated_restaurants_path)

    def change(records):
        records[0].menu_items[0].price = "7.5"

    saved = repository.mutate_records(change)

    assert saved[0].menu_items[0].price == "7.50"
    assert RestaurantRepository(isolated_restaurants_path).load_records()[0].menu_items[
        0
    ].price == "7.50"


def test_independent_repositories_serialize_overlapping_mutations(
    isolated_restaurants_path, monkeypatch
):
    import app.repositories.restaurant as repository_module
    from app.schemas.restaurant import RestaurantRecord

    isolated_restaurants_path.write_text("[]", encoding="utf-8")
    first = RestaurantRepository(isolated_restaurants_path)
    second = RestaurantRepository(isolated_restaurants_path)
    first_entered = threading.Event()
    second_attempted_lock = threading.Event()

    class ObservedLock:
        def __init__(self):
            self.lock = threading.Lock()
            self.counter_lock = threading.Lock()
            self.attempts = 0

        def __enter__(self):
            with self.counter_lock:
                self.attempts += 1
                if self.attempts == 2:
                    second_attempted_lock.set()
            self.lock.acquire()
            return self

        def __exit__(self, _type, _value, _traceback):
            self.lock.release()

    monkeypatch.setattr(repository_module, "_mutation_lock", ObservedLock())

    def add_first(records):
        first_entered.set()
        assert second_attempted_lock.wait(2)
        records.append(RestaurantRecord(**_record("first", "First")))

    def add_second(records):
        records.append(RestaurantRecord(**_record("second", "Second")))

    with ThreadPoolExecutor(max_workers=2) as pool:
        task_one = pool.submit(first.mutate_records, add_first)
        assert first_entered.wait(2)
        task_two = pool.submit(second.mutate_records, add_second)
        task_one.result(timeout=3)
        task_two.result(timeout=3)

    reloaded = RestaurantRepository(isolated_restaurants_path).load_records()
    assert [record.id for record in reloaded] == ["first", "second"]


def test_failed_mutation_releases_shared_lock(isolated_restaurants_path):
    repository = RestaurantRepository(isolated_restaurants_path)

    def fail(_records):
        raise ValueError("change rejected")

    with pytest.raises(ValueError, match="change rejected"):
        repository.mutate_records(fail)

    outcome = []
    def next_mutation():
        other = RestaurantRepository(isolated_restaurants_path)
        outcome.append(len(other.mutate_records(lambda records: None)))

    thread = threading.Thread(target=next_mutation, daemon=True)
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert outcome == [2]
