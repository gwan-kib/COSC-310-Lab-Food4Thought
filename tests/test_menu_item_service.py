# Test Food4Thought's menu-item update rules independently of HTTP and file
# persistence. A repository mock executes the real mutation callback against
# controlled records, checking parent-scoped lookups and preserved fields rather
# than merely returning a canned result.

from unittest.mock import Mock

import pytest

from app.repositories.restaurant import RestaurantDataError, RestaurantRepository
from app.schemas.restaurant import MenuItemUpdate, RestaurantRecord
from app.services.restaurant import (
    MenuItemNotFoundError,
    RestaurantNotFoundError,
    RestaurantService,
)


@pytest.fixture
def records():
    return [
        RestaurantRecord(
            id=identifier,
            name=f"Restaurant {identifier}",
            cuisine="Fusion",
            description="Test kitchen",
            menu_items=[
                {"id": "first", "name": "Bread", "description": "Fresh", "price": "2.00"},
                {"id": "shared", "name": "Soup", "description": "Hot", "price": "4.50"},
            ],
        )
        for identifier in ("other", "target")
    ]


@pytest.fixture
def repository(records):
    repository = Mock(spec=RestaurantRepository)

    def mutate(change):
        # Execute the real service callback against controlled in-memory state.
        change(records)
        return records

    repository.mutate_records.side_effect = mutate
    return repository


@pytest.mark.parametrize(
    "changes, expected_changes",
    [
        ({"name": "Stew"}, {"name": "Stew"}),
        ({"description": "Seasonal"}, {"description": "Seasonal"}),
        ({"price": "7.50"}, {"price": "7.50"}),
    ],
)
def test_update_changes_only_supplied_fields_in_selected_parent(
    records, repository, changes, expected_changes
):
    before = [record.model_dump() for record in records]
    expected_item = {
        "id": "shared", "name": "Soup", "description": "Hot", "price": "4.50",
        **expected_changes,
    }

    result = RestaurantService(repository).update_menu_item(
        "target", "shared", MenuItemUpdate(**changes)
    )

    assert result.model_dump() == expected_item
    before[1]["menu_items"][1] = expected_item
    assert [record.model_dump() for record in records] == before


@pytest.mark.parametrize(
    "parent_id, item_id, expected_error",
    [
        ("missing", "shared", RestaurantNotFoundError),
        ("target", "missing", MenuItemNotFoundError),
        ("target", "other-only", MenuItemNotFoundError),
    ],
)
def test_update_missing_parent_or_scoped_item_raises_without_changes(
    records, repository, parent_id, item_id, expected_error
):
    records[0].menu_items[0].id = "other-only"
    before = [record.model_dump() for record in records]

    with pytest.raises(expected_error):
        RestaurantService(repository).update_menu_item(
            parent_id, item_id, MenuItemUpdate(price="7.50")
        )

    assert [record.model_dump() for record in records] == before


def test_update_propagates_repository_failure(repository):
    repository.mutate_records.side_effect = RestaurantDataError("Storage unavailable")

    with pytest.raises(RestaurantDataError):
        RestaurantService(repository).update_menu_item(
            "target", "shared", MenuItemUpdate(price="7.50")
        )
