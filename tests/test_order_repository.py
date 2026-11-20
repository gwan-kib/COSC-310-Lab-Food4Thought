"""Check that purchased orders remain valid, unique and readable after restart.
All mutations target a disposable orders.json, including failed writes.
"""

import json
from pathlib import Path

import pytest

from app.repositories.order import OrderDataError, OrderRepository
from app.schemas.order import Order


@pytest.fixture
def record():
    examples = Path(__file__).resolve().parents[1] / "docs/examples/m2.json"
    return json.loads(examples.read_text(encoding="utf-8"))["checkout_response"]["order"]


def test_reload_by_id_attempt_and_customer(m2_store_paths, record):
    order = Order.model_validate(record)
    writer = OrderRepository()
    writer.save_order(order)
    for number, owner in [(2, "other"), (3, order.customer_id)]:
        writer.save_order(Order.model_validate(dict(record, id=str(number),
                                                    customer_id=owner, source_cart_id=str(number))))
    reader = OrderRepository(m2_store_paths["orders"])
    assert reader.get_order(order.id) == reader.find_for_cart("cart-001", 2) == order
    assert reader.find_for_cart("cart-001", 3) is None
    assert reader.get_order("missing") is None
    assert [o.id for o in reader.list_for_customer(order.customer_id)] == [order.id, "3"]


@pytest.mark.parametrize("change", [{"id": "other"}, {"source_cart_id": "other"}])
def test_reject_duplicate_attempt_or_id_without_overwriting(m2_store_paths, record, change):
    repo = OrderRepository()
    repo.save_order(Order.model_validate(record))
    before = m2_store_paths["orders"].read_bytes()
    with pytest.raises(OrderDataError):
        repo.save_order(Order.model_validate(record | change))
    assert m2_store_paths["orders"].read_bytes() == before


@pytest.mark.parametrize("damage", ["missing", "bad-json", "duplicate", "shape", "subtotal",
                                    "line_total", "quantity", "unit_price", "duplicate-line"])
def test_corrupt_or_missing_store_blocks_reads_and_writes(m2_store_paths, record, damage):
    path = m2_store_paths["orders"]
    clean = Order.model_validate(record)
    if damage == "missing":
        path.unlink()
    elif damage == "bad-json":
        path.write_text("{")
    else:
        records = [record]
        if damage == "duplicate":
            records.append(dict(record, id="different"))
        elif damage == "shape":
            records = {}
        elif damage == "subtotal":
            record["subtotal"] = "0.00"
        elif damage == "duplicate-line":
            record["items"].append(record["items"][0])
        else:
            record["items"][0][damage] = {"line_total": "1.00", "quantity": True,
                                           "unit_price": "1000.00"}[damage]
        path.write_text(json.dumps(records))
    before = path.read_bytes() if path.exists() else None
    with pytest.raises(OrderDataError):
        OrderRepository().get_order("absent")
    with pytest.raises(OrderDataError):
        OrderRepository().save_order(clean)
    assert (path.read_bytes() if path.exists() else None) == before


def test_failed_replace_preserves_previous_order_file(m2_store_paths, record, monkeypatch):
    def fail(*args):
        raise OSError("injected replacement failure")

    path = m2_store_paths["orders"]
    before = path.read_bytes()
    monkeypatch.setattr("app.repositories.order.os.replace", fail)
    with pytest.raises(OrderDataError):
        OrderRepository().save_order(Order.model_validate(record))
    assert path.read_bytes() == before
    assert not list(path.parent.glob(f".{path.name}.*"))


def test_saved_snapshot_cannot_lose_a_line_in_memory(m2_store_paths, record):
    order = Order.model_validate(record)
    OrderRepository().save_order(order)
    for snapshot in (order, OrderRepository().get_order(order.id)):
        with pytest.raises(AttributeError):
            snapshot.items.clear()
        assert snapshot.model_dump(mode="json") == record


def test_default_repository_uses_disposable_order_store_in_every_test(tmp_path):
    repo = OrderRepository()
    assert repo.path.parent == tmp_path
    with pytest.raises(OrderDataError):
        repo.list_for_customer("buyer")
    assert not repo.path.exists()
