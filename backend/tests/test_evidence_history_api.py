from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import evidence_history_routes
from backend.database import Base, get_db
from backend.domain.evidence_history import (
    EvidenceRecordStatus,
    IngredientConversionVersionInput,
)
from backend.services.evidence_history_service import register_conversion_version
from backend.services.official_evidence_history import seed_official_storage_policy_versions
from backend.utils.security import get_current_user


def _client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        register_conversion_version(
            db,
            IngredientConversionVersionInput(
                canonical_name="cooked rice",
                from_unit="cup",
                to_unit="g",
                record_version="reviewed-v1",
                multiplier_min=120,
                multiplier_max=125,
                source_name="API fixture",
                source_url="https://example.test/rice",
                source_version="source-v1",
                evidence_status=EvidenceRecordStatus.REVIEWED,
                reviewed_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
                reviewed_by="API reviewer",
                active=True,
            ),
        )
        seed_official_storage_policy_versions(db)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(evidence_history_routes.router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="reader@example.test"
    )
    return TestClient(app)


def test_immutable_evidence_routes_return_versions_hashes_and_reviewers():
    client = _client()
    conversions = client.get(
        "/api/v1/food-evidence/history/conversions",
        params={"reviewed_only": True},
    )
    assert conversions.status_code == 200
    conversion = conversions.json()[0]
    assert conversion["record_version"] == "reviewed-v1"
    assert conversion["reviewed_by"] == "API reviewer"
    assert len(conversion["content_hash"]) == 64

    policies = client.get(
        "/api/v1/food-evidence/history/storage-policies",
        params={"reviewed_only": True},
    )
    assert policies.status_code == 200
    assert policies.json()
    assert all(len(value["content_hash"]) == 64 for value in policies.json())

    detail = client.get(
        "/api/v1/food-evidence/history/storage-policies/pizza_refrigerated/active-reviewed"
    )
    assert detail.status_code == 200
    assert detail.json()["policy_key"] == "pizza_refrigerated"
    assert detail.json()["active"] is True


def test_reviewed_conversion_route_applies_exact_evidence_interval():
    client = _client()
    response = client.post(
        "/api/v1/food-evidence/history/convert-reviewed",
        json={
            "canonical_name": "Cooked Rice",
            "quantity_min": 1,
            "quantity_max": 2,
            "from_unit": "cup",
            "to_unit": "g",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["output_quantity_min"] == 120
    assert body["output_quantity_max"] == 250
    assert body["conversion_record_version"] == "reviewed-v1"
    assert len(body["conversion_content_hash"]) == 64


def test_api_exposes_no_evidence_mutation_route():
    client = _client()
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert not any("register" in path or "upsert" in path for path in paths)
    assert set(paths["/api/v1/food-evidence/history/conversions"]) == {"get"}
    assert set(paths["/api/v1/food-evidence/history/storage-policies"]) == {"get"}
