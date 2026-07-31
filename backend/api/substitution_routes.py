from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import DBPantryItem, DBUser, get_db
from backend.domain.substitutions import SubstitutionCandidate, suggest_substitutions
from backend.utils.security import get_current_user


router = APIRouter(prefix="/api/v1/substitutions", tags=["substitutions"])


class SubstitutionRequest(BaseModel):
    ingredient: str = Field(min_length=1, max_length=240)
    household_id: str | None = None
    allergies: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=20)


@router.post("/suggest", response_model=list[SubstitutionCandidate])
def substitutions(
    payload: SubstitutionRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    pantry: list[str] = []
    if payload.household_id:
        from backend.services.inventory_service import require_household_owner

        require_household_owner(db, payload.household_id, current_user.id)
        pantry = [
            row[0]
            for row in db.query(DBPantryItem.canonical_name)
            .filter(
                DBPantryItem.household_id == payload.household_id,
                DBPantryItem.quantity_max > 0,
            )
            .all()
        ]
    allergies = sorted(set(payload.allergies) | set(current_user.allergies or []))
    restrictions = sorted(
        set(payload.dietary_restrictions) | set(current_user.dietary_restrictions or [])
    )
    return suggest_substitutions(
        payload.ingredient,
        allergies=allergies,
        dietary_restrictions=restrictions,
        pantry_ingredients=pantry,
        limit=payload.limit,
    )
