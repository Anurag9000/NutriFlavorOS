"""Evidence-backed conversions and reviewed storage-policy API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.domain.conversions import (
    ConversionRequest,
    ConversionResult,
    IngredientConversionView,
    StoragePolicyView,
)
from backend.services.conversion_service import (
    convert_quantity,
    list_conversions,
    list_storage_policies,
    seed_official_storage_policies,
)
from backend.utils.security import get_current_user


router = APIRouter(prefix="/api/v1/food-evidence", tags=["food-evidence"])


@router.get("/conversions", response_model=list[IngredientConversionView])
def conversions_route(
    ingredient: str | None = Query(default=None, max_length=240),
    db: Session = Depends(get_db),
    _current_user: DBUser = Depends(get_current_user),
):
    return [
        IngredientConversionView.model_validate(value)
        for value in list_conversions(db, ingredient)
    ]


@router.post("/convert", response_model=ConversionResult)
def convert_route(
    payload: ConversionRequest,
    db: Session = Depends(get_db),
    _current_user: DBUser = Depends(get_current_user),
):
    return convert_quantity(db, payload)


@router.get("/storage-policies", response_model=list[StoragePolicyView])
def storage_policies_route(
    food_category: str | None = Query(default=None, max_length=240),
    storage_state: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
    _current_user: DBUser = Depends(get_current_user),
):
    seed_official_storage_policies(db)
    return [
        StoragePolicyView.model_validate(value)
        for value in list_storage_policies(
            db,
            food_category=food_category,
            storage_state=storage_state,
        )
    ]
