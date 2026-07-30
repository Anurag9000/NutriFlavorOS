from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.engines.health_engine import HealthEngine
from backend.models import UserProfile
from backend.services.dietrxdb_service import DietRxDBService
from backend.utils.security import get_current_user, require_self
from backend.utils.user_profiles import apply_profile, db_user_to_profile


router = APIRouter(prefix="/api/v1/user", tags=["user"])
dietrx_service = DietRxDBService()
health_engine = HealthEngine()


class HealthConditionPayload(BaseModel):
    condition: str = Field(min_length=1, max_length=160)


class MedicationPayload(BaseModel):
    medication: str = Field(min_length=1, max_length=160)


def _clean_label(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise HTTPException(status_code=422, detail="A non-empty value is required")
    return cleaned


@router.get("/{user_id}", response_model=UserProfile)
def get_user_profile(
    user_id: str,
    current_user: DBUser = Depends(get_current_user),
) -> UserProfile:
    require_self(user_id, current_user)
    return db_user_to_profile(current_user)


@router.put("/{user_id}", response_model=UserProfile)
def update_user_profile(
    user_id: str,
    profile: UserProfile,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> UserProfile:
    require_self(user_id, current_user)

    if profile.target_calories is None:
        targets = health_engine.calculate_targets(profile)
        profile.target_calories = targets.calories
        profile.target_protein_g = targets.protein_g
        profile.target_carbs_g = targets.carbs_g
        profile.target_fat_g = targets.fat_g

    apply_profile(current_user, profile)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return db_user_to_profile(current_user)


@router.post("/{user_id}/health_condition")
def add_health_condition(
    user_id: str,
    payload: HealthConditionPayload,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(user_id, current_user)
    condition = _clean_label(payload.condition)

    try:
        disease_info = dietrx_service.get_disease_info(condition)
        reference_data_found = bool(disease_info)
    except Exception:
        reference_data_found = False

    conditions = list(current_user.health_conditions or [])
    if condition not in conditions:
        conditions.append(condition)
        current_user.health_conditions = conditions
        db.add(current_user)
        db.commit()

    return {
        "status": "success",
        "message": f"Added condition: {condition}",
        "dataset_verified": reference_data_found,
    }


@router.post("/{user_id}/medication")
def add_medication(
    user_id: str,
    payload: MedicationPayload,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(user_id, current_user)
    medication = _clean_label(payload.medication)

    medications = list(current_user.medications or [])
    if medication not in medications:
        medications.append(medication)
        current_user.medications = medications
        db.add(current_user)
        db.commit()

    return {"status": "success", "message": f"Added medication: {medication}"}
