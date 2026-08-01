from __future__ import annotations

from backend.database import Base

# Import side effects intentionally register tables on the shared declarative Base.
from backend import evidence_history_models as _evidence_history_models  # noqa: F401,E402
from backend import preparation_models as _preparation_models  # noqa: F401,E402
from backend import preparation_operations_models as _preparation_operations_models  # noqa: F401,E402


def test_extended_models_are_registered_on_shared_metadata():
    assert {
        "recipe_preparation_profiles",
        "ingredient_conversion_versions",
        "storage_policy_versions",
        "leftover_storage_policy_evidence",
        "evidence_lifecycle_events",
        "resource_calendar_versions",
        "household_preparation_resources",
        "persisted_preparation_schedules",
        "preparation_schedule_events",
    } <= set(Base.metadata.tables)
