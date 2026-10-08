from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.repositories.restaurant import RestaurantDataError, RestaurantRepository
from app.schemas.restaurant import (
    ErrorResponse,
    Menu,
    MenuItem,
    MenuItemCreate,
    Restaurant,
    RestaurantCreate,
    RestaurantUpdate,
)
from app.services.restaurant import RestaurantNotFoundError, RestaurantService

router = APIRouter()


def get_restaurant_service() -> RestaurantService:
    # Resolve configuration per request so isolated storage can be injected.
    return RestaurantService(RestaurantRepository())


@router.get(
    "/restaurants",
    summary="List restaurants",
    description="Return the persisted restaurant list in stored order.",
    response_model=list[Restaurant],
    responses={
        500: {"model": ErrorResponse, "description": "Restaurant data is unavailable"}
    },
)
def list_restaurants(
    service: Annotated[RestaurantService, Depends(get_restaurant_service)],
) -> list[Restaurant]:
    try:
        return service.list_restaurants()
    except RestaurantDataError as exc:
        raise HTTPException(
            status_code=500, detail="Restaurant data is unavailable"
        ) from exc


@router.post(
    "/restaurants",
    summary="Create a restaurant",
    description=(
        "Create and persist a restaurant with a server-generated stable ID "
        "and an empty menu."
    ),
    response_model=Restaurant,
    status_code=201,
    responses={
        500: {"model": ErrorResponse, "description": "Restaurant data is unavailable"}
    },
)
def create_restaurant(
    request: RestaurantCreate,
    service: Annotated[RestaurantService, Depends(get_restaurant_service)],
) -> Restaurant:
    try:
        return service.create_restaurant(request)
    except RestaurantDataError as exc:
        raise HTTPException(
            status_code=500, detail="Restaurant data is unavailable"
        ) from exc


@router.patch(
    "/restaurants/{restaurant_id}",
    summary="Update a restaurant",
    description=(
        "Persist a partial update to name, cuisine, or description. Supply at least "
        "one non-null, nonblank string; surrounding whitespace is trimmed. Omitted "
        "fields, the stable ID, and menu items are preserved. Unsupported fields "
        "are rejected. Returns the complete restaurant only after saving."
    ),
    response_model=Restaurant,
    responses={
        404: {"model": ErrorResponse, "description": "Restaurant not found"},
        500: {"model": ErrorResponse, "description": "Restaurant data is unavailable"},
    },
)
def update_restaurant(
    restaurant_id: Annotated[
        str,
        Path(description="Stable restaurant identifier, for example `restaurant-001`."),
    ],
    request: RestaurantUpdate,
    service: Annotated[RestaurantService, Depends(get_restaurant_service)],
) -> Restaurant:
    try:
        return service.update_restaurant(restaurant_id, request)
    except RestaurantNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Restaurant not found") from exc
    except RestaurantDataError as exc:
        raise HTTPException(
            status_code=500, detail="Restaurant data is unavailable"
        ) from exc


@router.get(
    "/restaurants/{restaurant_id}/menu",
    summary="Get a restaurant's menu",
    description=(
        "Return the menu and all of its items for one restaurant. A restaurant "
        "with no menu items returns an empty `items` list."
    ),
    response_model=Menu,
    responses={
        404: {"model": ErrorResponse, "description": "Restaurant not found"},
        500: {"model": ErrorResponse, "description": "Restaurant data is unavailable"},
    },
)
def get_menu(
    restaurant_id: Annotated[
        str,
        Path(description="Stable restaurant identifier, for example `restaurant-001`."),
    ],
    service: Annotated[RestaurantService, Depends(get_restaurant_service)],
) -> Menu:
    try:
        return service.get_menu(restaurant_id)
    except RestaurantNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Restaurant not found") from exc
    except RestaurantDataError as exc:
        raise HTTPException(
            status_code=500, detail="Restaurant data is unavailable"
        ) from exc


@router.post(
    "/restaurants/{restaurant_id}/menu/items",
    summary="Add a menu item",
    description=(
        "Add and persist an item under an existing restaurant with a server-generated "
        "stable ID. Supply name, description, and a nonnegative decimal-string price "
        "with at most two fractional digits. The saved price has two fractional digits."
    ),
    response_model=MenuItem,
    status_code=201,
    responses={
        404: {"model": ErrorResponse, "description": "Restaurant not found"},
        500: {"model": ErrorResponse, "description": "Restaurant data is unavailable"},
    },
)
def add_menu_item(
    restaurant_id: Annotated[
        str,
        Path(description="Stable restaurant identifier, for example `restaurant-001`."),
    ],
    request: MenuItemCreate,
    service: Annotated[RestaurantService, Depends(get_restaurant_service)],
) -> MenuItem:
    try:
        return service.add_menu_item(restaurant_id, request)
    except RestaurantNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Restaurant not found") from exc
    except RestaurantDataError as exc:
        raise HTTPException(
            status_code=500, detail="Restaurant data is unavailable"
        ) from exc
