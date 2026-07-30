"""Sustainability reporting from stored plans, with provenance/status labels."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import DBMealPlan, DBUser, get_db
from backend.models import PlanResponse
from backend.utils.security import get_current_user, require_self


router = APIRouter(prefix="/api/v1/sustainability", tags=["sustainability"])


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


def _require_plan(db: Session, user_id: str) -> PlanResponse:
    plan = _latest_plan(db, user_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="No valid meal plan found")
    return plan


@router.get("/{user_id}")
def get_sustainability_data(
    user_id: str,
    period: str = Query(default="monthly", pattern=r"^(weekly|monthly|yearly)$"),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(user_id, current_user)
    plan = _require_plan(db, user_id)
    values = [
        float(day.total_stats["carbon_footprint_kg"])
        for day in plan.days
        if isinstance(day.total_stats.get("carbon_footprint_kg"), (int, float))
    ]
    return {
        "carbon_saved_kg": 0.0,
        "water_saved_l": 0.0,
        "trees_planted_equivalent": 0.0,
        "sustainable_meals_count": 0,
        "planned_carbon_footprint_kg": round(sum(values), 2) if values else None,
        "period": period,
        "data_status": "unverified_estimate" if values else "unavailable",
        "baseline_status": "not_configured",
    }


@router.get("/carbon-footprint/{user_id}")
def get_carbon_footprint(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(user_id, current_user)
    plan = _require_plan(db, user_id)
    breakdown = [
        {
            "category": f"Plan day {day.day}",
            "value": float(day.total_stats["carbon_footprint_kg"]),
            "status": day.total_stats.get("carbon_data_status", "unknown"),
        }
        for day in plan.days
        if isinstance(day.total_stats.get("carbon_footprint_kg"), (int, float))
    ]
    total = sum(item["value"] for item in breakdown)
    meal_count = sum(len(day.meals) for day in plan.days)
    return {
        "total_footprint": round(total, 2) if breakdown else 0.0,
        "average_meal_footprint": round(total / meal_count, 3) if breakdown and meal_count else 0.0,
        "breakdown": breakdown,
        "data_status": "unverified_estimate" if breakdown else "unavailable",
    }
