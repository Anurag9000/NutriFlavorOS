from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.research.cards import ModelCard, build_dataset_card, build_model_card
from backend.research.catalog import RiskLevel
from backend.research.drift import (
    categorical_total_variation,
    numeric_drift_report,
    population_stability_index,
    two_sample_ks_statistic,
)
from backend.research.registry import LocalArtifactRegistry, RegistryStage
from backend.research.splits import (
    assert_no_group_leakage,
    group_aware_split,
    temporal_split,
)


def test_cards_derive_catalog_safety_contracts():
    dataset = build_dataset_card("usda_fdc_foundation", version="2026-04")
    assert dataset.license
    model = build_model_card("rgbd_multitask_nutrition", version="0.1")
    assert model.risk == RiskLevel.CLINICAL
    assert "clinical_review" in model.promotion_gates
    assert any("medical" in item.lower() for item in model.prohibited_uses)


def test_registry_integrity_and_candidate_promotion(tmp_path: Path):
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"deterministic artifact")
    registry = LocalArtifactRegistry(tmp_path / "registry")
    card = build_model_card("tfidf_retriever", version="1")
    entry = registry.register_model(card, artifact)
    assert registry.verify_integrity(entry)
    gates = {gate: True for gate in card.promotion_gates}
    candidate = registry.promote(
        card.model_id,
        card.version,
        target_stage=RegistryStage.CANDIDATE,
        gate_results=gates,
        evaluation={"ndcg@10": 0.42},
    )
    assert candidate.stage == RegistryStage.CANDIDATE
    artifact.write_bytes(b"tampered")
    assert not registry.verify_integrity(candidate)
    with pytest.raises(ValueError, match="Promotion blocked"):
        registry.promote(
            card.model_id,
            card.version,
            target_stage=RegistryStage.CHAMPION,
            gate_results=gates,
        )


def test_concurrent_registry_instances_do_not_lose_distinct_entries(tmp_path: Path):
    root = tmp_path / "registry"
    cards = [
        build_dataset_card("usda_fdc_foundation", version="2026-04"),
        build_dataset_card("internal_recipes", version="fixture-v1"),
    ]

    def register(card):
        return LocalArtifactRegistry(root).register_dataset(card)

    with ThreadPoolExecutor(max_workers=2) as executor:
        entries = list(executor.map(register, cards))

    assert {entry.item_id for entry in entries} == {
        "usda_fdc_foundation",
        "internal_recipes",
    }
    persisted = LocalArtifactRegistry(root).list(kind="dataset")
    assert {(entry.item_id, entry.version) for entry in persisted} == {
        ("usda_fdc_foundation", "2026-04"),
        ("internal_recipes", "fixture-v1"),
    }
    assert not list(root.glob(".registry.*.tmp"))
    assert not (root / ".registry.lock").exists()


def test_concurrent_champion_promotions_leave_exactly_one_winner(tmp_path: Path):
    root = tmp_path / "registry"
    registry = LocalArtifactRegistry(root)
    versions = ["1", "2"]
    gates_by_version = {}
    for version in versions:
        artifact = tmp_path / f"model-{version}.bin"
        artifact.write_bytes(f"deterministic artifact {version}".encode())
        card = build_model_card("tfidf_retriever", version=version)
        gates = {gate: True for gate in card.promotion_gates}
        gates_by_version[version] = gates
        registry.register_model(card, artifact)
        registry.promote(
            card.model_id,
            card.version,
            target_stage=RegistryStage.CANDIDATE,
            gate_results=gates,
        )

    def promote(version: str):
        return LocalArtifactRegistry(root).promote(
            "tfidf_retriever",
            version,
            target_stage=RegistryStage.CHAMPION,
            gate_results=gates_by_version[version],
            evaluation={"source": f"worker-{version}"},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        returned = list(executor.map(promote, versions))
    assert all(entry.stage == RegistryStage.CHAMPION for entry in returned)

    final = LocalArtifactRegistry(root).list(kind="model")
    champions = [entry for entry in final if entry.stage == RegistryStage.CHAMPION]
    archived = [entry for entry in final if entry.stage == RegistryStage.ARCHIVED]
    assert len(champions) == 1
    assert len(archived) == 1
    assert {champions[0].version, archived[0].version} == {"1", "2"}


def test_clinical_model_cannot_be_champion_without_validation(tmp_path: Path):
    artifact = tmp_path / "clinical.bin"
    artifact.write_bytes(b"research only")
    registry = LocalArtifactRegistry(tmp_path / "registry")
    card = ModelCard.model_validate(
        build_model_card("rgbd_multitask_nutrition", version="1").model_dump()
    )
    registry.register_model(card, artifact)
    gates = {gate: True for gate in card.promotion_gates}
    registry.promote(
        card.model_id,
        card.version,
        target_stage=RegistryStage.CANDIDATE,
        gate_results=gates,
    )
    with pytest.raises(ValueError, match="clinical validation"):
        registry.promote(
            card.model_id,
            card.version,
            target_stage=RegistryStage.CHAMPION,
            gate_results=gates,
        )


def test_drift_metrics_detect_large_change():
    reference = [0, 0.1, 0.2, 0.3, 0.4] * 20
    shifted = [value + 4 for value in reference]
    assert population_stability_index(reference, list(reference)) < 1e-6
    assert two_sample_ks_statistic(reference, shifted) > 0.9
    assert numeric_drift_report(reference, shifted).drifted
    assert categorical_total_variation(["a", "a", "b"], ["b", "b", "b"]) > 0


def test_group_and_temporal_splits_are_deterministic_and_leakage_safe():
    rows = [f"row-{i}" for i in range(12)]
    groups = [f"group-{i // 2}" for i in range(12)]
    first = group_aware_split(rows, groups, seed=7)
    assert first == group_aware_split(rows, groups, seed=7)
    assert_no_group_leakage(first, dict(zip(rows, groups)))
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    temporal = temporal_split(
        rows, [start + timedelta(days=i) for i in range(12)]
    )
    rank = {"train": 0, "validation": 1, "test": 2}
    ordered = [temporal[row] for row in rows]
    assert [rank[value] for value in ordered] == sorted(
        rank[value] for value in ordered
    )
