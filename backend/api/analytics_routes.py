"""Plan-derived analytics that do not fabricate consumption or health outcomes."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import DBMealPlan, DBUser, get_db
from backend.models import PlanResponse
from backend.utils.security import get_current_user, require_self


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


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


@router.get("/health/{user_id}")
def get_health_insights(
    user_id: str,
    period: str = Query(default="30d", pattern=r"^(7d|30d|90d)$"),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(user_id, current_user)
    plan = _require_plan(db, user_id)
    return [
        {
            "date": f"Plan day {day.day}",
            "score": round(float(day.scores.get("health_match", 0.0)) * 100, 1),
            "metric": "planned_macro_match",
            "period": period,
        }
        for day in plan.days
    ]


@router.get("/taste/{user_id}")
def get_taste_insights(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(user_id, current_user)
    plan = _require_plan(db, user_id)

    totals = defaultdict(float)
    counts = Counter()
    for day in plan.days:
        for recipe in day.meals.values():
            for dimension, value in recipe.flavor_profile.items():
                try:
                    totals[dimension] += float(value)
                    counts[dimension] += 1
                except (TypeError, ValueError):
                    continue

    return [
        {
            "subject": dimension.replace("_", " ").title(),
            "A": round(totals[dimension] / counts[dimension] * 100, 1),
            "fullMark": 100,
            "metric": "average_planned_recipe_profile",
        }
        for dimension in sorted(counts)
        if counts[dimension]
    ]


@router.get("/variety/{user_id}")
def get_variety_insights(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(user_id, current_user)
    plan = _require_plan(db, user_id)
    cuisines = Counter(
        recipe.cuisine or "Unknown"
        for day in plan.days
        for recipe in day.meals.values()
    )
    total = sum(cuisines.values())
    return [
        {
            "name": cuisine,
            "value": round(count / total * 100, 1) if total else 0.0,
            "count": count,
            "metric": "planned_meal_share",
        }
        for cuisine, count in sorted(cuisines.items())
    ]


@router.post("/predict_health")
def predict_health(_: DBUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Health outcome prediction is disabled until a clinically validated model is available",
    )


@router.get("/insights/{user_id}")
def get_plan_insight(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_self(user_id, current_user)
    plan = _require_plan(db, user_id)
    stats = plan.overall_stats or {}
    health = float(stats.get("average_health_match", 0.0) or 0.0)
    variety = float(stats.get("average_variety", 0.0) or 0.0)

    if health < 0.7:
        insight = "The generated plan has a low macro-target match. Regenerate it after reviewing profile targets and recipe coverage."
        priority = "high"
    elif variety < 0.5:
        insight = "The generated plan repeats many ingredients. Add more compliant recipes or broaden non-safety preferences."
        priority = "medium"
    else:
        insight = "The generated plan has acceptable macro and variety scores. These scores describe planned meals, not consumed food or health outcomes."
        priority = "low"

    return {"insight": insight, "category": "plan_quality", "priority": priority}
