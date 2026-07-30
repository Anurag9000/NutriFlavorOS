"""Recipe retrieval from the canonical local SQLAlchemy store."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.database import DBRecipe, get_db
from backend.models import Recipe


router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])


def _to_recipe(row: DBRecipe) -> Recipe:
    return Recipe(
        id=row.id,
        name=row.name or "Unnamed recipe",
        description=row.description or "",
        image_url=row.image_url,
        ingredients=list(row.ingredients or []),
        calories=max(0, int(row.calories or 0)),
        macros=dict(row.macros or {}),
        flavor_profile=dict(row.flavor_profile or {}),
        tags=list(row.tags or []),
        cuisine=row.cuisine,
        instructions=list(row.instructions or []),
        estimated_cost=max(0.0, float(row.estimated_cost or 0.0)),
    )


@router.get("/search", response_model=List[Recipe])
def search_recipes(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    tags: Optional[str] = Query(default=None, max_length=300),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[Recipe]:
    query = db.query(DBRecipe)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                DBRecipe.name.ilike(pattern),
                DBRecipe.description.ilike(pattern),
                DBRecipe.cuisine.ilike(pattern),
            )
        )

    requested_tags = {
        tag.strip().lower()
        for tag in (tags or "").split(",")
        if tag.strip()
    }

    candidate_limit = min(max(limit * 5, limit), 500) if requested_tags else limit
    rows = query.order_by(DBRecipe.name.asc()).limit(candidate_limit).all()
    recipes = [_to_recipe(row) for row in rows]
    if requested_tags:
        recipes = [
            recipe
            for recipe in recipes
            if requested_tags.issubset({tag.lower() for tag in recipe.tags})
        ]
    return recipes[:limit]


@router.get("/{recipe_id}", response_model=Recipe)
def get_recipe_details(recipe_id: str, db: Session = Depends(get_db)) -> Recipe:
    row = db.query(DBRecipe).filter(DBRecipe.id == recipe_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _to_recipe(row)
