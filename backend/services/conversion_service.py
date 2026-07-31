"""Evidence-backed ingredient conversion and reviewed storage-policy services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import DBIngredientConversion, DBStoragePolicy
from backend.domain.conversions import (
    ConversionRequest,
    ConversionResult,
    IngredientConversionCreate,
    IngredientConversionView,
)
from backend.domain.ingredients import canonicalize_ingredient_name


_EPSILON = 1e-12

OFFICIAL_STORAGE_POLICIES: tuple[dict[str, Any], ...] = (
    {
        "policy_key": "cooked_leftovers_refrigerated_general",
        "food_category": "cooked leftovers",
        "storage_state": "refrigerated",
        "duration_min_hours": 72.0,
        "duration_max_hours": 96.0,
        "maximum_temperature_c": 4.0,
        "source_name": "USDA Food Safety and Inspection Service",
        "source_url": (
            "https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/"
            "food-safety-basics/leftovers-and-food-safety"
        ),
        "reviewed_at": datetime(2026, 7, 31, tzinfo=timezone.utc),
        "safety_scope": "general_home_storage",
        "notes": (
            "General cooked-leftover guidance only. Refrigerate promptly in shallow "
            "containers. Recipe, packaging, contamination, appliance temperature, "
            "power loss, and vulnerable-person considerations can require earlier disposal."
        ),
    },
    {
        "policy_key": "soups_stews_refrigerated",
        "food_category": "soups and stews",
        "storage_state": "refrigerated",
        "duration_min_hours": 72.0,
        "duration_max_hours": 96.0,
        "maximum_temperature_c": 4.0,
        "source_name": "FoodSafety.gov Cold Food Storage Chart",
        "source_url": "https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts",
        "reviewed_at": datetime(2026, 7, 31, tzinfo=timezone.utc),
        "safety_scope": "general_home_storage",
        "notes": "Vegetable or meat soups/stews; prompt chilling and cold-chain assumptions apply.",
    },
    {
        "policy_key": "pizza_refrigerated",
        "food_category": "pizza",
        "storage_state": "refrigerated",
        "duration_min_hours": 72.0,
        "duration_max_hours": 96.0,
        "maximum_temperature_c": 4.0,
        "source_name": "FoodSafety.gov Cold Food Storage Chart",
        "source_url": "https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts",
        "reviewed_at": datetime(2026, 7, 31, tzinfo=timezone.utc),
        "safety_scope": "general_home_storage",
        "notes": "Prompt chilling and cold-chain assumptions apply.",
    },
    {
        "policy_key": "cooked_meat_poultry_refrigerated",
        "food_category": "cooked meat or poultry",
        "storage_state": "refrigerated",
        "duration_min_hours": 72.0,
        "duration_max_hours": 96.0,
        "maximum_temperature_c": 4.0,
        "source_name": "FoodSafety.gov Cold Food Storage Chart",
        "source_url": "https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts",
        "reviewed_at": datetime(2026, 7, 31, tzinfo=timezone.utc),
        "safety_scope": "general_home_storage",
        "notes": "Prompt chilling and cold-chain assumptions apply.",
    },
    {
        "policy_key": "cooked_leftovers_frozen_quality",
        "food_category": "cooked leftovers",
        "storage_state": "frozen",
        "duration_min_hours": 24.0 * 30.0 * 3.0,
        "duration_max_hours": 24.0 * 30.0 * 4.0,
        "maximum_temperature_c": -18.0,
        "source_name": "USDA Food Safety and Inspection Service",
        "source_url": (
            "https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/"
            "food-safety-basics/leftovers-and-food-safety"
        ),
        "reviewed_at": datetime(2026, 7, 31, tzinfo=timezone.utc),
        "safety_scope": "quality_guidance",
        "notes": (
            "Frozen duration is quality guidance, not a universal safety expiry. "
            "Continuous freezing at or below the stated temperature is assumed."
        ),
    },
)


def _apply_storage_policy(value: DBStoragePolicy, raw: Dict[str, Any]) -> None:
    for key, item in raw.items():
        setattr(value, key, item)
    value.active = True


def seed_official_storage_policies(db: Session) -> int:
    created = 0
    for raw in OFFICIAL_STORAGE_POLICIES:
        existing = (
            db.query(DBStoragePolicy)
            .filter(DBStoragePolicy.policy_key == raw["policy_key"])
            .with_for_update()
            .first()
        )
        if existing is None:
            db.add(DBStoragePolicy(**raw))
            created += 1
        else:
            _apply_storage_policy(existing, raw)
            db.add(existing)
    try:
        db.commit()
    except IntegrityError:
        # Another process may have inserted a policy after our non-existent-row
        # check. Resolve every row by its database-enforced policy key.
        db.rollback()
        created = 0
        for raw in OFFICIAL_STORAGE_POLICIES:
            existing = (
                db.query(DBStoragePolicy)
                .filter(DBStoragePolicy.policy_key == raw["policy_key"])
                .with_for_update()
                .one()
            )
            _apply_storage_policy(existing, raw)
            db.add(existing)
        db.commit()
    return created


def list_storage_policies(
    db: Session,
    *,
    food_category: Optional[str] = None,
    storage_state: Optional[str] = None,
) -> List[DBStoragePolicy]:
    query = db.query(DBStoragePolicy).filter(DBStoragePolicy.active.is_(True))
    if food_category:
        query = query.filter(
            DBStoragePolicy.food_category.ilike(f"%{food_category.strip()}%")
        )
    if storage_state:
        query = query.filter(DBStoragePolicy.storage_state == storage_state.strip().lower())
    return query.order_by(
        DBStoragePolicy.food_category,
        DBStoragePolicy.storage_state,
        DBStoragePolicy.policy_key,
    ).all()


def _conversion_query(
    db: Session,
    *,
    canonical_name: str,
    from_unit: str,
    to_unit: str,
    source_name: str,
    source_version: str,
):
    return db.query(DBIngredientConversion).filter(
        DBIngredientConversion.canonical_name == canonical_name,
        DBIngredientConversion.from_unit == from_unit,
        DBIngredientConversion.to_unit == to_unit,
        DBIngredientConversion.source_name == source_name,
        DBIngredientConversion.source_version == source_version,
    )


def _normalized_conversion_payload(
    payload: IngredientConversionCreate,
) -> Dict[str, Any]:
    canonical_name = canonicalize_ingredient_name(payload.canonical_name)
    if not canonical_name:
        raise HTTPException(
            status_code=422, detail="Ingredient name could not be normalized"
        )
    raw = payload.model_dump()
    raw["canonical_name"] = canonical_name
    raw["from_unit"] = payload.from_unit.strip().lower()
    raw["to_unit"] = payload.to_unit.strip().lower()
    raw["source_name"] = payload.source_name.strip()
    raw["source_url"] = payload.source_url.strip()
    raw["source_version"] = payload.source_version.strip()
    return raw


def _same_conversion_evidence(
    value: DBIngredientConversion, raw: Dict[str, Any]
) -> bool:
    return (
        abs(float(value.multiplier_min) - float(raw["multiplier_min"])) <= _EPSILON
        and abs(float(value.multiplier_max) - float(raw["multiplier_max"]))
        <= _EPSILON
        and value.source_url == raw["source_url"]
        and value.evidence_status == raw["evidence_status"]
        and value.reviewed_at == raw["reviewed_at"]
        and value.notes == raw["notes"]
    )


def _conversion_conflict(value: DBIngredientConversion) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "conversion_evidence_conflict",
            "message": (
                "The same ingredient/unit/source/version key already contains "
                "different evidence. Register a new source version after review."
            ),
            "existing_conversion_id": value.id,
        },
    )


def _resolve_existing_conversion(
    value: DBIngredientConversion, raw: Dict[str, Any]
) -> DBIngredientConversion:
    if not _same_conversion_evidence(value, raw):
        raise _conversion_conflict(value)
    return value


def register_conversion(
    db: Session, payload: IngredientConversionCreate
) -> DBIngredientConversion:
    raw = _normalized_conversion_payload(payload)
    query = _conversion_query(
        db,
        canonical_name=raw["canonical_name"],
        from_unit=raw["from_unit"],
        to_unit=raw["to_unit"],
        source_name=raw["source_name"],
        source_version=raw["source_version"],
    )
    value = query.with_for_update().first()
    if value is not None:
        value = _resolve_existing_conversion(value, raw)
        if not value.active:
            value.active = True
            db.add(value)
            db.commit()
            db.refresh(value)
        return value

    value = DBIngredientConversion(**raw, active=True)
    db.add(value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = query.with_for_update().one()
        return _resolve_existing_conversion(existing, raw)
    db.refresh(value)
    return value


def list_conversions(
    db: Session, canonical_name: Optional[str] = None
) -> List[DBIngredientConversion]:
    query = db.query(DBIngredientConversion).filter(
        DBIngredientConversion.active.is_(True)
    )
    if canonical_name:
        query = query.filter(
            DBIngredientConversion.canonical_name
            == canonicalize_ingredient_name(canonical_name)
        )
    return query.order_by(
        DBIngredientConversion.canonical_name,
        DBIngredientConversion.from_unit,
        DBIngredientConversion.to_unit,
        DBIngredientConversion.id,
    ).all()


def convert_quantity(db: Session, payload: ConversionRequest) -> ConversionResult:
    canonical_name = canonicalize_ingredient_name(payload.canonical_name)
    from_unit = payload.from_unit.strip().lower()
    to_unit = payload.to_unit.strip().lower()
    candidates = (
        db.query(DBIngredientConversion)
        .filter(
            DBIngredientConversion.canonical_name == canonical_name,
            DBIngredientConversion.from_unit == from_unit,
            DBIngredientConversion.to_unit == to_unit,
            DBIngredientConversion.active.is_(True),
        )
        .order_by(
            DBIngredientConversion.reviewed_at.is_(None),
            DBIngredientConversion.reviewed_at.desc(),
            DBIngredientConversion.id,
        )
        .all()
    )
    if not candidates:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "conversion_evidence_unavailable",
                "message": (
                    "No ingredient-specific evidence-backed conversion exists. "
                    "The system will not guess a density or package size."
                ),
                "canonical_name": canonical_name,
                "from_unit": from_unit,
                "to_unit": to_unit,
            },
        )
    evidence = candidates[0]
    output_min = payload.quantity_min * evidence.multiplier_min
    output_max = payload.quantity_max * evidence.multiplier_max
    warnings = []
    if evidence.evidence_status != "reviewed_external":
        warnings.append(
            "This conversion has not completed reviewed-external evidence validation."
        )
    return ConversionResult(
        canonical_name=canonical_name,
        input_quantity_min=payload.quantity_min,
        input_quantity_max=payload.quantity_max,
        input_unit=from_unit,
        output_quantity_min=round(output_min, 8),
        output_quantity_max=round(output_max, 8),
        output_unit=to_unit,
        evidence=IngredientConversionView.model_validate(evidence),
        warnings=warnings,
    )


def import_fdc_portions(
    db: Session,
    *,
    canonical_name: str,
    fdc_id: int,
    portions: Iterable[Dict[str, Any]],
    source_version: str,
) -> int:
    """Import exact FoodData Central gram weights as food-specific rules."""

    canonical = canonicalize_ingredient_name(canonical_name)
    if not canonical:
        raise ValueError("canonical_name could not be normalized")
    evidence_version = f"{source_version.strip()}:fdc:{fdc_id}"
    created = 0
    for portion in portions:
        amount = portion.get("amount")
        gram_weight = portion.get("gramWeight")
        measure = portion.get("measureUnit") or {}
        modifier = str(portion.get("modifier") or "").strip()
        measure_name = str(
            measure.get("abbreviation") or measure.get("name") or ""
        ).strip()
        unit_name = modifier or measure_name
        try:
            amount_value = float(amount)
            grams_value = float(gram_weight)
        except (TypeError, ValueError):
            continue
        if amount_value <= 0 or grams_value <= 0 or not unit_name:
            continue
        multiplier = grams_value / amount_value
        payload = IngredientConversionCreate(
            canonical_name=canonical,
            from_unit=unit_name.lower(),
            to_unit="g",
            multiplier_min=multiplier,
            multiplier_max=multiplier,
            source_name="USDA FoodData Central",
            source_url=(
                f"https://fdc.nal.usda.gov/fdc-app.html#/food-details/"
                f"{fdc_id}/nutrients"
            ),
            source_version=evidence_version,
            evidence_status="external_unverified",
            reviewed_at=None,
            notes=(
                f"Imported from FoodData Central food portion record for FDC ID {fdc_id}; "
                "requires human verification that the food identity and measure label match."
            ),
        )
        before = (
            _conversion_query(
                db,
                canonical_name=canonical,
                from_unit=payload.from_unit,
                to_unit="g",
                source_name="USDA FoodData Central",
                source_version=evidence_version,
            )
            .first()
        )
        register_conversion(db, payload)
        if before is None:
            created += 1
    return created
