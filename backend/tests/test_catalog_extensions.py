from __future__ import annotations

import backend.research.catalog as catalog_module
from backend.research.catalog import get_catalog
from backend.research.catalog_extensions import (
    CURRENT_EXTENDED_VERSION,
    apply_catalog_extensions,
)


def test_catalog_extension_is_loaded_and_validated():
    catalog = get_catalog()
    assert catalog.version == CURRENT_EXTENDED_VERSION == "2026-08-01.3"
    assert [value.id for value in catalog.models].count(
        "exact_preparation_scheduler"
    ) == 1
    assert [value.id for value in catalog.features].count(
        "exact_preparation_benchmark"
    ) == 1
    benchmark = next(
        value
        for value in catalog.experiments
        if value.id == "preparation_scheduler_benchmark"
    )
    assert benchmark.models.count("exact_preparation_scheduler") == 1


def test_applying_catalog_extension_twice_is_idempotent():
    before = get_catalog()
    apply_catalog_extensions()
    after = get_catalog()
    assert after == before
    assert catalog_module.CATALOG.version == CURRENT_EXTENDED_VERSION


def test_effective_catalog_reconstructs_all_reference_checks():
    catalog = get_catalog()
    reconstructed = catalog_module.ResearchCatalog.model_validate(
        catalog.model_dump(mode="json")
    )
    assert reconstructed == catalog
    assert reconstructed.summary()["models"]["total"] == 75
    assert reconstructed.summary()["features"]["total"] == 39
