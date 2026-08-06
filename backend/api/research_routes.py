from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.database import DBUser
from backend.research.cards import build_dataset_card, build_model_card
from backend.research.capabilities import implementation_status
from backend.research.catalog import get_by_id, get_catalog
from backend.research.drift import DriftReport, numeric_drift_report
from backend.research.manifest import ExperimentRunConfig, create_manifest
from backend.utils.security import get_current_user


router = APIRouter(
    prefix="/api/v1/research",
    tags=["research"],
    dependencies=[Depends(get_current_user)],
)


class NumericDriftRequest(BaseModel):
    reference: List[float] = Field(min_length=10, max_length=10000)
    current: List[float] = Field(min_length=10, max_length=10000)
    psi_threshold: float = Field(default=0.20, ge=0)
    ks_threshold: float = Field(default=0.20, ge=0, le=1)
    mean_shift_threshold: float = Field(default=0.50, ge=0)


@router.get("/catalog")
def catalog():
    value = get_catalog()
    return {
        "catalog": value,
        "summary": value.summary(),
        "implemented_components": implementation_status(),
    }


@router.get("/implemented-components")
def implemented_components():
    return implementation_status()


@router.get("/cards/datasets/{dataset_id}")
def dataset_card(
    dataset_id: str,
    version: str = Query(default="unversioned", max_length=120),
):
    try:
        return build_dataset_card(dataset_id, version=version)
    except StopIteration as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc


@router.get("/cards/models/{model_id}")
def model_card(
    model_id: str,
    version: str = Query(default="unversioned", max_length=120),
):
    try:
        return build_model_card(model_id, version=version)
    except StopIteration as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc


@router.post("/drift/numeric", response_model=DriftReport)
def numeric_drift(
    payload: NumericDriftRequest,
    _: DBUser = Depends(get_current_user),
):
    return numeric_drift_report(
        payload.reference,
        payload.current,
        psi_threshold=payload.psi_threshold,
        ks_threshold=payload.ks_threshold,
        mean_shift_threshold=payload.mean_shift_threshold,
    )


@router.post("/validate-run-config")
def validate_run_config(
    config: ExperimentRunConfig,
    _: DBUser = Depends(get_current_user),
):
    value = get_catalog()
    experiments = {item.id for item in value.experiments}
    models = (
        {item.id for item in value.models}
        | set(implementation_status())
        | {"catalog_validation"}
    )
    if config.experiment_id not in experiments:
        raise HTTPException(status_code=422, detail="Unknown experiment_id")
    if config.baseline not in models:
        raise HTTPException(
            status_code=422,
            detail="Unknown baseline/model identifier",
        )
    return {
        "valid": True,
        "manifest_preview": create_manifest(config),
        "execution": "offline_cli_only",
        "reason": (
            "The API validates configurations but does not execute arbitrary "
            "experiments."
        ),
    }


@router.get("/{collection}")
def collection(
    collection: str,
    readiness: str | None = Query(default=None),
    risk: str | None = Query(default=None),
):
    value = get_catalog()
    if collection not in {"tasks", "datasets", "models", "experiments", "features"}:
        raise HTTPException(status_code=404, detail="Research collection not found")
    items = getattr(value, collection)
    if readiness:
        items = [
            item
            for item in items
            if getattr(item, "readiness", None)
            and item.readiness.value == readiness
        ]
    if risk:
        items = [
            item
            for item in items
            if getattr(item, "risk", None) and item.risk.value == risk
        ]
    return {"collection": collection, "count": len(items), "items": items}


@router.get("/{collection}/{item_id}")
def catalog_item(collection: str, item_id: str):
    try:
        return get_by_id(collection, item_id)
    except (KeyError, LookupError) as exc:
        raise HTTPException(
            status_code=404,
            detail="Research catalog item not found",
        ) from exc
