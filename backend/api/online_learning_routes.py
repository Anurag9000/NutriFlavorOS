"""Authenticated feedback capture and explicitly gated prototype endpoints.

Feedback is stored for an offline, reviewed training pipeline. Request handlers
never mutate production model weights. Demo responses that previously fabricated
inventory, predictions, points, ranks, and achievements now return a clear
``501 Not Implemented`` instead of presenting fixtures as user data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import DBFeedback, DBMealPlan, DBUser, get_db
from backend.models import PlanResponse
from backend.utils.security import get_current_user, require_self


router = APIRouter(prefix="/api/v1", tags=["feedback", "grocery", "gamification"])


class TasteFeedback(BaseModel):
    user_id: str
    recipe_id: str = Field(min_length=1, max_length=160)
    rating: float = Field(ge=0.0, le=1.0)
    user_genome: List[float] = Field(min_length=1, max_length=256)
    recipe_profile: List[float] = Field(min_length=1, max_length=256)


class HealthOutcome(BaseModel):
    user_id: str
    actual_weight: float = Field(gt=0, le=500)
    actual_hba1c: Optional[float] = Field(default=None, gt=0, le=30)
    actual_cholesterol: Optional[float] = Field(default=None, gt=0, le=1000)
    meal_history: List[Dict[str, Any]] = Field(default_factory=list, max_length=1000)
    consent_to_store: bool = False


class MealSelection(BaseModel):
    user_id: str
    state: List[float] = Field(min_length=1, max_length=2048)
    selected_recipe_id: int = Field(ge=0)
    reward: float = Field(ge=-1000, le=1000)


class GroceryPurchase(BaseModel):
    user_id: str
    items: List[Dict[str, Any]] = Field(min_length=1, max_length=500)


class GroceryConsumption(BaseModel):
    user_id: str
    item: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0)


class MealImpact(BaseModel):
    user_id: str
    carbon_footprint: float = Field(ge=0)
    health_score: float = Field(ge=0, le=1)
    variety_score: float = Field(ge=0, le=1)
    taste_rating: Optional[float] = Field(default=None, ge=0, le=1)


def _store_feedback(db: Session, user_id: str, feedback_type: str, payload: Dict[str, Any]) -> int:
    event = DBFeedback(user_id=user_id, feedback_type=feedback_type, payload=payload)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event.id


def _not_implemented(feature: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{feature} is not implemented with real user data yet",
    )


def _latest_plan(db: Session, user_id: str) -> Optional[PlanResponse]:
    row = (
        db.query(DBMealPlan)
        .filter(DBMealPlan.user_id == user_id)
        .order_by(DBMealPlan.created_at.desc(), DBMealPlan.id.desc())
        .first()
    )
    if row is None:
        return None
    try:
        return PlanResponse.model_validate(row.plan_data)
    except ValueError:
        return None


@router.post("/feedback/taste", status_code=status.HTTP_202_ACCEPTED)
def log_taste_feedback(
    feedback: TasteFeedback,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(feedback.user_id, current_user)
    event_id = _store_feedback(db, current_user.id, "taste", feedback.model_dump(mode="json"))
    return {
        "status": "accepted",
        "event_id": event_id,
        "message": "Feedback stored for offline review",
        "model_updated": False,
    }


@router.post("/feedback/health", status_code=status.HTTP_202_ACCEPTED)
def log_health_outcome(
    outcome: HealthOutcome,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(outcome.user_id, current_user)
    if not outcome.consent_to_store:
        raise HTTPException(
            status_code=400,
            detail="Explicit consent_to_store=true is required for health outcome data",
        )
    event_id = _store_feedback(db, current_user.id, "health_outcome", outcome.model_dump(mode="json"))
    return {
        "status": "accepted",
        "event_id": event_id,
        "message": "Health outcome stored for offline review",
        "model_updated": False,
    }


@router.post("/feedback/meal_selection", status_code=status.HTTP_202_ACCEPTED)
def log_meal_selection(
    selection: MealSelection,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(selection.user_id, current_user)
    event_id = _store_feedback(db, current_user.id, "meal_selection", selection.model_dump(mode="json"))
    return {
        "status": "accepted",
        "event_id": event_id,
        "message": "Selection stored for offline review",
        "model_updated": False,
    }


@router.get("/models/stats/{model_name}")
def get_model_stats(model_name: str, _: DBUser = Depends(get_current_user)):
    return {
        "model": model_name,
        "status": "disabled",
        "reason": "No validated, versioned production model is configured",
    }


@router.get("/grocery/shopping_list/{user_id}")
def generate_shopping_list(
    user_id: str,
    days_ahead: int = Query(default=7, ge=1, le=31),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(user_id, current_user)
    plan = _latest_plan(db, user_id)
    if plan is None or not plan.shopping_list:
        raise HTTPException(status_code=404, detail="Generate a meal plan before requesting a shopping list")

    items = []
    for category, category_items in plan.shopping_list.items():
        for item_name, item_data in category_items.items():
            count = int(item_data.get("count", 0) or 0)
            items.append(
                {
                    "item": item_name,
                    "predicted_quantity": count,
                    "quantity_label": item_data.get("quantity"),
                    "quantity_status": item_data.get("quantity_status"),
                    "estimated_cost": 0.0,
                    "urgency": 0.0,
                    "category": category,
                }
            )

    return {
        "shopping_list": items,
        "summary": {
            "total_items": len(items),
            "estimated_total_cost": 0.0,
            "days_covered": min(days_ahead, len(plan.days)),
            "urgent_items": 0,
            "cost_status": "unavailable",
        },
    }


@router.post("/grocery/purchase")
def log_grocery_purchase(
    purchase: GroceryPurchase,
    current_user: DBUser = Depends(get_current_user),
):
    require_self(purchase.user_id, current_user)
    _not_implemented("Transactional pantry purchase tracking")


@router.post("/grocery/consume")
def log_grocery_consumption(
    consumption: GroceryConsumption,
    current_user: DBUser = Depends(get_current_user),
):
    require_self(consumption.user_id, current_user)
    _not_implemented("Transactional pantry consumption tracking")


@router.get("/grocery/predict/{user_id}/{item}")
def predict_next_purchase(
    user_id: str,
    item: str,
    current_user: DBUser = Depends(get_current_user),
):
    require_self(user_id, current_user)
    _not_implemented("Validated grocery purchase prediction")


@router.post("/gamification/log_meal")
def log_meal_impact(
    impact: MealImpact,
    current_user: DBUser = Depends(get_current_user),
):
    require_self(impact.user_id, current_user)
    _not_implemented("Transactional gamification scoring")


@router.get("/gamification/leaderboard")
def get_leaderboard(_: DBUser = Depends(get_current_user)):
    _not_implemented("Real leaderboard aggregation")


@router.get("/gamification/rank/{user_id}")
def get_user_rank(user_id: str, current_user: DBUser = Depends(get_current_user)):
    require_self(user_id, current_user)
    _not_implemented("Real user ranking")


@router.get("/gamification/achievements/{user_id}")
def get_user_achievements(user_id: str, current_user: DBUser = Depends(get_current_user)):
    require_self(user_id, current_user)
    _not_implemented("Persisted achievements")


@router.get("/gamification/impact_summary/{user_id}")
def get_monthly_impact_summary(user_id: str, current_user: DBUser = Depends(get_current_user)):
    require_self(user_id, current_user)
    _not_implemented("Verified impact summaries")
