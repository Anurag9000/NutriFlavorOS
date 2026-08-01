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
    StoragePolicyVersionInput,
)
from backend.domain.evidence_lifecycle import (
    EvidenceLifecycleAction,
    EvidenceLifecycleBatchDocument,
    EvidenceLifecycleRequest,
    EvidenceTargetKind,
)
from backend.services.evidence_history_service import (
    register_conversion_version,
    register_storage_policy_version,
)
from backend.services.evidence_lifecycle_service import (
    apply_evidence_lifecycle_batch,
)
from backend.utils.security import get_current_user


def _client() -> tuple[TestClient, int, int]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        reviewed_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        conversion = register_conversion_version(
            db,
            IngredientConversionVersionInput(
                canonical_name="cooked rice",
                from_unit="cup",
                to_unit="g",
                record_version="api-v1",
                multiplier_min=120,
                multiplier_max=125,
                source_name="API fixture",
                source_url="https://example.test/conversion",
                source_version="api-v1",
                evidence_status=EvidenceRecordStatus.REVIEWED,
                reviewed_at=reviewed_at,
                reviewed_by="API reviewer",
                active=True,
            ),
        )
        policy = register_storage_policy_version(
            db,
            StoragePolicyVersionInput(
                policy_key="rice_refrigerated",
                policy_version="api-v1",
                food_category="cooked rice",
                storage_state="refrigerated",
                duration_min_hours=72,
                duration_max_hours=96,
                maximum_temperature_c=4,
                source_name="API fixture",
                source_url="https://example.test/policy",
                source_version="api-v1",
                evidence_status=EvidenceRecordStatus.REVIEWED,
                reviewed_at=reviewed_at,
                reviewed_by="API reviewer",
                safety_scope="test_only",
                active=True,
            ),
        )
        apply_evidence_lifecycle_batch(
            db,
            EvidenceLifecycleBatchDocument(
                actions=[
                    EvidenceLifecycleRequest(
                        target_kind=EvidenceTargetKind.CONVERSION,
                        target_id=conversion.id,
                        action=EvidenceLifecycleAction.DEACTIVATED,
                        actor="API operator",
                        reason="Withdraw conversion from future automatic use",
                        idempotency_key="api-lifecycle-conversion-v1",
                        metadata={"ticket": "API-1"},
                    ),
                    EvidenceLifecycleRequest(
                        target_kind=EvidenceTargetKind.STORAGE_POLICY,
                        target_id=policy.id,
                        action=EvidenceLifecycleAction.REJECTED,
                        actor="API operator",
                        reason="Reject storage policy after evidence review",
                        idempotency_key="api-lifecycle-policy-v1",
                        metadata={"ticket": "API-2"},
                    ),
                ]
            ),
        )

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
    return TestClient(app), conversion.id, policy.id


def test_authenticated_reader_can_list_exact_lifecycle_history():
    client, conversion_id, policy_id = _client()
    response = client.get("/api/v1/food-evidence/history/lifecycle-events")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {value["target_kind"] for value in body} == {
        "conversion",
        "storage_policy",
    }
    assert {value["target_id"] for value in body} == {
        conversion_id,
        policy_id,
    }
    assert all(len(value["request_fingerprint"]) == 64 for value in body)
    assert all(len(value["target_content_hash"]) == 64 for value in body)
    assert {value["actor"] for value in body} == {"API operator"}


def test_lifecycle_history_can_be_filtered_to_one_exact_target():
    client, conversion_id, _ = _client()
    response = client.get(
        "/api/v1/food-evidence/history/lifecycle-events",
        params={"target_kind": "conversion", "target_id": conversion_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["target_kind"] == "conversion"
    assert body[0]["target_id"] == conversion_id
    assert body[0]["action"] == "deactivated"
    assert body[0]["metadata"] == {"ticket": "API-1"}


def test_target_id_requires_target_kind():
    client, conversion_id, _ = _client()
    response = client.get(
        "/api/v1/food-evidence/history/lifecycle-events",
        params={"target_id": conversion_id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "lifecycle_target_kind_required"


def test_product_router_exposes_lifecycle_history_as_get_only():
    client, _, _ = _client()
    document = client.app.openapi()
    methods = {
        value.lower()
        for value in document["paths"][
            "/api/v1/food-evidence/history/lifecycle-events"
        ]
        if value.lower() in {"get", "post", "put", "patch", "delete"}
    }
    assert methods == {"get"}
