from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.repositories.restaurant import RestaurantDataError, RestaurantRepository
from app.schemas.restaurant import Restaurant
from app.services.restaurant import RestaurantService

router = APIRouter()


def get_restaurant_service() -> RestaurantService:
    # Resolve configuration per request so isolated storage can be injected.
    return RestaurantService(RestaurantRepository())


@router.get(
    "/restaurants",
    response_model=list[Restaurant],
    responses={500: {"description": "Restaurant data is unavailable"}},
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
