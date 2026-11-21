"""Check Food4Thought's cart repository against isolated JSON storage (#85/#86).
It must create one active cart per customer, keep stable IDs across reloads, reject
inconsistent data, and leave the previous file intact when a save fails.
"""

import json

import pytest

from app.repositories.cart import CartDataError, CartRepository
from app.schemas.cart import CartItem, CartRecord


def _stored(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_create_cart_is_idempotent_and_survives_a_fresh_repository(m2_store_paths):
    path = m2_store_paths["carts"]
    cart, created = CartRepository().create_cart("customer-001")

    assert created is True
    assert (cart.customer_id, cart.revision, cart.restaurant_id, cart.items) == (
        "customer-001", 0, None, [])
    again, created_again = CartRepository().create_cart("customer-001")
    assert created_again is False
    assert again == cart
    assert CartRepository(path).get_cart("customer-001") == cart
    assert len(_stored(path)) == 1


def test_each_customer_gets_their_own_cart_and_reads_never_write(m2_store_paths):
    repository = CartRepository()
    first, _ = repository.create_cart("customer-001")
    second, _ = repository.create_cart("customer-002")
    before = m2_store_paths["carts"].read_bytes()

    assert first.id != second.id
    assert repository.get_cart("customer-003") is None
    assert m2_store_paths["carts"].read_bytes() == before


def test_save_cart_replaces_only_that_cart(m2_store_paths):
    repository = CartRepository()
    cart, _ = repository.create_cart("customer-001")
    other, _ = repository.create_cart("customer-002")
    changed = cart.model_copy(update={
        "revision": 1, "restaurant_id": "restaurant-001",
        "items": [CartItem(item_id="item-001", quantity=2)],
    })

    repository.save_cart(changed)

    assert CartRepository().get_cart("customer-001") == changed
    assert CartRepository().get_cart("customer-002") == other


def test_failed_save_keeps_the_previous_file(m2_store_paths, monkeypatch):
    repository = CartRepository()
    cart, _ = repository.create_cart("customer-001")
    before = m2_store_paths["carts"].read_bytes()

    def broken_replace(*_args):
        raise OSError("disk full")

    monkeypatch.setattr("app.repositories.cart.os.replace", broken_replace)
    with pytest.raises(CartDataError):
        repository.save_cart(cart.model_copy(update={"revision": 1, "restaurant_id": "restaurant-001",
                                                     "items": [CartItem(item_id="item-001", quantity=1)]}))

    assert m2_store_paths["carts"].read_bytes() == before
    assert not list(m2_store_paths["carts"].parent.glob(".carts.json.*.tmp"))


@pytest.mark.parametrize("content", [
    "{not json",
    '{"id": "cart-1"}',
    json.dumps([{"id": "c1", "customer_id": "customer-001", "revision": 0,
                 "restaurant_id": "restaurant-001", "items": []}]),
    json.dumps([{"id": "c1", "customer_id": "customer-001", "revision": 0, "restaurant_id": None, "items": []},
                {"id": "c2", "customer_id": "customer-001", "revision": 0, "restaurant_id": None, "items": []}]),
    json.dumps([{"id": "c1", "customer_id": "customer-001", "revision": 0, "restaurant_id": None, "items": []},
                {"id": "c1", "customer_id": "customer-002", "revision": 0, "restaurant_id": None, "items": []}]),
])
def test_corrupt_or_inconsistent_data_is_an_error_not_an_empty_cart(m2_store_paths, content):
    m2_store_paths["carts"].write_text(content, encoding="utf-8")

    with pytest.raises(CartDataError):
        CartRepository().get_cart("customer-001")


def test_reset_after_order_clears_only_the_matching_revision(m2_store_paths):
    repository = CartRepository()
    cart, _ = repository.create_cart("customer-001")
    filled = CartRecord(id=cart.id, customer_id="customer-001", revision=3,
                        restaurant_id="restaurant-001", items=[CartItem(item_id="item-001", quantity=1)])
    repository.save_cart(filled)

    assert repository.reset_after_order("customer-001", cart.id, 2) is False
    assert repository.get_cart("customer-001") == filled
    assert repository.reset_after_order("customer-001", cart.id, 3) is True
    reset = repository.get_cart("customer-001")
    assert (reset.id, reset.revision, reset.restaurant_id, reset.items) == (cart.id, 4, None, [])
    assert repository.reset_after_order("customer-001", cart.id, 3) is False


def test_serialization_failure_is_a_cart_data_error_with_no_temporary_file(m2_store_paths, monkeypatch):
    repository = CartRepository()
    cart, _ = repository.create_cart("customer-001")
    before = m2_store_paths["carts"].read_bytes()

    def broken_dump(*_args, **_kwargs):
        raise ValueError("cannot serialize")

    monkeypatch.setattr("app.repositories.cart._carts.dump_json", broken_dump)
    with pytest.raises(CartDataError):
        repository.save_cart(cart.model_copy(update={"revision": 1, "restaurant_id": "restaurant-001",
                                                     "items": [CartItem(item_id="item-001", quantity=1)]}))

    assert m2_store_paths["carts"].read_bytes() == before
    assert not list(m2_store_paths["carts"].parent.glob(".carts.json.*.tmp"))
