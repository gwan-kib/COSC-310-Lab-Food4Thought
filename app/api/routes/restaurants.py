# Translate Food4Thought's restaurant and menu operations between HTTP requests and
# RestaurantService. FastAPI and request models validate input, while these routes
# build the service/repository dependency and map missing resources to 404 or
# storage failures to a generic 500.

from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import StringConstraints

from app.api.auth import authentication_required, require_administrator, require_restaurant_user
from app.repositories.staff import StaffDataError
from app.schemas.customer import Principal
from app.repositories.restaurant import RestaurantDataError, RestaurantRepository
from app.schemas.restaurant import (
    ErrorResponse,
    Menu,
    MenuItem,
    MenuItemCreate,
    MenuItemUpdate,
    Restaurant,
    RestaurantCreate,
    RestaurantUpdate,
)
from app.services.restaurant import (
    AuthenticationRequired,
    PermissionDenied,
    MenuItemNotFoundError,
    RestaurantNotFoundError,
    RestaurantService,
)

router = APIRouter()

MANAGEMENT_PERMISSION_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Management writes require authentication"},
    403: {"model": ErrorResponse, "description": "Caller lacks the required role or restaurant assignment"},
    500: {"model": ErrorResponse, "description": "Restaurant or authentication data is unavailable"},
}

# A supplied filter must contain more than whitespace; blank values are a 422.
CuisineFilter = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def get_restaurant_service() -> RestaurantService:
    # Resolve configuration per request so isolated storage can be injected.
    return RestaurantService(RestaurantRepository())


def get_manager_service(
    principal: Annotated[Principal, Depends(require_restaurant_user)],
) -> RestaurantService:
    return RestaurantService(RestaurantRepository(), principal=principal)


def get_admin_service(
    principal: Annotated[Principal, Depends(require_administrator)],
) -> RestaurantService:
    return RestaurantService(RestaurantRepository(), principal=principal)


@contextmanager
def management_errors():
    """Translate write failures consistently for all restaurant management routes."""
    try:
        yield
    except StaffDataError as exc:
        raise HTTPException(500, "Authentication data is unavailable") from exc
    except AuthenticationRequired as exc:
        raise authentication_required() from exc
    except PermissionDenied as exc:
        raise HTTPException(403, "Operation not permitted") from exc
    except RestaurantNotFoundError as exc:
        raise HTTPException(404, "Restaurant not found") from exc
    except MenuItemNotFoundError as exc:
        raise HTTPException(404, "Menu item not found") from exc
    except RestaurantDataError as exc:
        raise HTTPException(500, "Restaurant data is unavailable") from exc


@router.get(
    "/restaurants",
    summary="List restaurants",
    description=(
        "Return the persisted restaurant list in stored order. Supply `cuisine` to "
        "return only restaurants whose whole cuisine matches, ignoring case and "
        "surrounding whitespace; no match returns an empty list."
    ),
    response_model=list[Restaurant],
    responses={
        500: {"model": ErrorResponse, "description": "Restaurant data is unavailable"}
    },
)
def list_restaurants(
    service: Annotated[RestaurantService, Depends(get_restaurant_service)],
    cuisine: Annotated[
        CuisineFilter | None,
        Query(
            description=(
                "Optional exact cuisine filter, case-insensitive, for example "
                "`Japanese`. Empty or whitespace-only values are rejected."
            ),
        ),
    ] = None,
) -> list[Restaurant]:
    try:
        return service.list_restaurants(cuisine)
    except RestaurantDataError as exc:
        raise HTTPException(
            status_code=500, detail="Restaurant data is unavailable"
        ) from exc


@router.post(
    "/restaurants",
    summary="Create a restaurant",
    description=(
        "An administrator can create and persist a restaurant with a server-generated stable ID "
        "and an empty menu."
    ),
    response_model=Restaurant,
    status_code=201,
    responses={
        **MANAGEMENT_PERMISSION_RESPONSES,
    },
)
def create_restaurant(
    request: RestaurantCreate,
    service: Annotated[RestaurantService, Depends(get_admin_service)],
) -> Restaurant:
    with management_errors():
        return service.create_restaurant(request)


@router.get(
    "/restaurants/{restaurant_id}",
    summary="Get restaurant details",
    description=(
        "Return one restaurant by its stable ID, with the same four fields as the "
        "list. Menu items are returned by the menu operation."
    ),
    response_model=Restaurant,
    responses={
        404: {"model": ErrorResponse, "description": "Restaurant not found"},
        500: {"model": ErrorResponse, "description": "Restaurant data is unavailable"},
    },
)
def get_restaurant(
    restaurant_id: Annotated[
        str,
        Path(description="Stable restaurant identifier, for example `restaurant-001`."),
    ],
    service: Annotated[RestaurantService, Depends(get_restaurant_service)],
) -> Restaurant:
    try:
        return service.get_restaurant(restaurant_id)
    except RestaurantNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Restaurant not found") from exc
    except RestaurantDataError as exc:
        raise HTTPException(
            status_code=500, detail="Restaurant data is unavailable"
        ) from exc


@router.patch(
    "/restaurants/{restaurant_id}",
    summary="Update a restaurant",
    description=(
        "The assigned restaurant manager can persist a partial update to name, cuisine, or description. Supply at least "
        "one non-null, nonblank string; surrounding whitespace is trimmed. Omitted "
        "fields, the stable ID, and menu items are preserved. Unsupported fields "
        "are rejected. Returns the complete restaurant only after saving."
    ),
    response_model=Restaurant,
    responses={
        **MANAGEMENT_PERMISSION_RESPONSES,
        404: {"model": ErrorResponse, "description": "Restaurant not found"},
    },
)
def update_restaurant(
    restaurant_id: Annotated[
        str,
        Path(description="Stable restaurant identifier, for example `restaurant-001`."),
    ],
    request: RestaurantUpdate,
    service: Annotated[RestaurantService, Depends(get_manager_service)],
) -> Restaurant:
    with management_errors():
        return service.update_restaurant(restaurant_id, request)


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
        "no greater than 999.00, with at most two fractional digits. "
        "Availability defaults to true. Writing menu items requires the assigned restaurant manager. "
        "The saved price has two fractional digits."
    ),
    response_model=MenuItem,
    status_code=201,
    responses={
        **MANAGEMENT_PERMISSION_RESPONSES,
        404: {"model": ErrorResponse, "description": "Restaurant not found"},
    },
)
def add_menu_item(
    restaurant_id: Annotated[
        str,
        Path(description="Stable restaurant identifier, for example `restaurant-001`."),
    ],
    request: MenuItemCreate,
    service: Annotated[RestaurantService, Depends(get_manager_service)],
) -> MenuItem:
    with management_errors():
        return service.add_menu_item(restaurant_id, request)


@router.patch(
    "/restaurants/{restaurant_id}/menu/items/{item_id}",
    summary="Update a menu item",
    description=(
        "Persist a partial update to name, description, price, or availability under the specified "
        "restaurant. Writing menu items requires the assigned restaurant manager. Supply at least "
        "one non-null field. Text must be nonblank; "
        "price must be a nonnegative decimal string no greater than 999.00, with "
        "at most two fractional digits. Omitted fields, IDs, parent relationships, "
        "and unrelated items "
        "are preserved. Unsupported fields are rejected. Returns the complete item "
        "with a two-decimal price only after saving."
    ),
    response_model=MenuItem,
    responses={
        **MANAGEMENT_PERMISSION_RESPONSES,
        404: {
            "model": ErrorResponse,
            "description": "Restaurant not found, or menu item not found under that restaurant",
        },
    },
)
def update_menu_item(
    restaurant_id: Annotated[
        str,
        Path(description="Stable restaurant identifier, for example `restaurant-001`."),
    ],
    item_id: Annotated[
        str,
        Path(description="Stable item identifier from this restaurant's menu response."),
    ],
    request: MenuItemUpdate,
    service: Annotated[RestaurantService, Depends(get_manager_service)],
) -> MenuItem:
    with management_errors():
        return service.update_menu_item(restaurant_id, item_id, request)
