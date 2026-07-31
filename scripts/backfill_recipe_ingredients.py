"""Backfill canonical ingredient data and emit a nutrition-quality report.

Dry-run is the default. Pass ``--apply`` only after reviewing the generated
report. The command never auto-corrects calories or macros because basis and
source provenance must be resolved first.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from backend.database import DBRecipe, SessionLocal
from backend.domain.ingredients import parse_ingredient_lines
from backend.domain.nutrition_validation import validate_recipe_nutrition
from backend.models import Recipe


def _row_to_recipe(row: DBRecipe) -> Recipe:
    ingredients = [str(value) for value in list(row.ingredients or [])]
    parsed = parse_ingredient_lines(ingredients)
    return Recipe(
        id=row.id,
        name=row.name or "Unnamed recipe",
        description=row.description or "",
        image_url=row.image_url,
        ingredients=ingredients,
        ingredient_lines=parsed,
        servings=max(0.01, float(getattr(row, "servings", 1.0) or 1.0)),
        calories=max(0, int(row.calories or 0)),
        macros=dict(row.macros or {}),
        flavor_profile=dict(row.flavor_profile or {}),
        tags=list(row.tags or []),
        cuisine=row.cuisine,
        instructions=list(row.instructions or []),
        estimated_cost=max(0.0, float(row.estimated_cost or 0.0)),
        source_name=getattr(row, "source_name", None),
        source_url=getattr(row, "source_url", None),
        source_version=getattr(row, "source_version", None),
        nutrition_basis=getattr(row, "nutrition_basis", None) or "per_serving",
    )


def run(*, apply: bool, report_path: Path) -> Dict[str, Any]:
    db = SessionLocal()
    reports: List[Dict[str, Any]] = []
    updated = 0
    try:
        rows = db.query(DBRecipe).order_by(DBRecipe.id).all()
        for row in rows:
            recipe = _row_to_recipe(row)
            reports.append(validate_recipe_nutrition(recipe))
            normalized = [line.model_dump(mode="json") for line in recipe.ingredient_lines]
            if normalized != list(getattr(row, "ingredient_data", None) or []):
                updated += 1
                if apply:
                    row.ingredient_data = normalized
                    db.add(row)
        if apply:
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    summary = {
        "mode": "apply" if apply else "dry_run",
        "recipe_count": len(reports),
        "rows_requiring_ingredient_backfill": updated,
        "invalid_recipe_count": sum(1 for item in reports if not item["valid"]),
        "warning_recipe_count": sum(1 for item in reports if item["warnings"]),
        "recipes": reports,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="persist canonical ingredient_data")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/recipe_data_quality.json"),
        help="output JSON report path",
    )
    args = parser.parse_args()
    summary = run(apply=args.apply, report_path=args.report)
    print(
        json.dumps(
            {key: value for key, value in summary.items() if key != "recipes"},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
