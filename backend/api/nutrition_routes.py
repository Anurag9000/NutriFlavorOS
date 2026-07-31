from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.config import APIConfig
from backend.database import DBUser
from backend.services.base_service import ExternalServiceError
from backend.services.fooddata_central_service import FoodDataCentralService
from backend.utils.security import get_current_user


router = APIRouter(prefix="/api/v1/nutrition-data", tags=["nutrition-data"])


def _service() -> FoodDataCentralService:
    if not APIConfig.ENABLE_FOODDATA_CENTRAL:
        raise HTTPException(status_code=501, detail="FoodData Central adapter is disabled")
    try:
        return FoodDataCentralService()
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/search")
def search_fooddata_central(
    q: str = Query(min_length=2, max_length=200),
    page_size: int = Query(default=25, ge=1, le=100),
    data_type: list[str] | None = Query(default=None),
    _: DBUser = Depends(get_current_user),
):
    try:
        return _service().search(q, page_size=page_size, data_types=data_type)
    except (ExternalServiceError, ValueError) as exc:
        code = status.HTTP_422_UNPROCESSABLE_ENTITY if isinstance(exc, ValueError) else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.get("/foods/{fdc_id}")
def get_fooddata_central_food(
    fdc_id: int,
    _: DBUser = Depends(get_current_user),
):
    try:
        return _service().get_food(fdc_id)
    except (ExternalServiceError, ValueError) as exc:
        code = status.HTTP_422_UNPROCESSABLE_ENTITY if isinstance(exc, ValueError) else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=code, detail=str(exc)) from exc
