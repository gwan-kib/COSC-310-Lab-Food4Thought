from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.repositories.restaurant import RestaurantDataError, RestaurantRepository
from app.schemas.restaurant import ErrorResponse, Restaurant, RestaurantCreate
from app.services.restaurant import RestaurantService

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
