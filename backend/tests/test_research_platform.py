import pytest

from backend.research.baselines import (
    CrostonForecaster,
    MovingAverageForecaster,
    RidgeRegressor,
    TfidfRetriever,
)
from backend.research.capabilities import (
    assert_core_capabilities_valid,
    implementation_status,
)
from backend.research.catalog import CATALOG, Readiness, get_by_id
from backend.research.evaluation import (
    brier_score,
    expected_calibration_error,
    mae,
    mean_iou,
    ndcg_at_k,
    recall_at_k,
    rmse,
)
from backend.research.manifest import (
    ExperimentRunConfig,
    create_manifest,
    fingerprint_json,
)


def test_catalog_is_referentially_valid_and_explicit():
    assert len(CATALOG.tasks) >= 25
    assert len(CATALOG.datasets) >= 20
    assert len(CATALOG.models) >= 50
    assert len(CATALOG.experiments) >= 20
    assert get_by_id("models", "rgbd_multitask_nutrition").default_enabled is False
    assert (
        get_by_id("models", "rgbd_multitask_nutrition").readiness
        == Readiness.RESEARCH_ONLY
    )
    assert get_by_id("datasets", "dishseg24k").readiness == Readiness.ANNOUNCED


def test_declared_core_capabilities_import_the_registered_callable():
    assert_core_capabilities_valid()
    statuses = implementation_status()
    assert statuses
    for identifier, value in statuses.items():
        assert value["symbol"]
        assert value["runtime_enabled"] is False
        if value["dependency"] == "core":
            assert value["implementation_valid"] is True, (identifier, value)
            assert value["runtime_available"] is True, (identifier, value)
            assert value["status"] != "broken_registration"
        else:
            assert value["implementation_valid"] is True, (identifier, value)
            assert value["runtime_available"] is value["dependency_installed"]
            if not value["dependency_installed"]:
                assert value["status"] == "optional_dependency_missing"


def test_tfidf_retrieval_is_deterministic():
    documents = [
        ("a", "chickpea tomato salad"),
        ("b", "chocolate cake"),
        ("c", "tomato pasta"),
    ]
    first = TfidfRetriever().fit(documents).rank("tomato chickpea", k=3)
    second = TfidfRetriever().fit(documents).rank("tomato chickpea", k=3)
    assert first == second
    assert first[0].item_id == "a"
    ids = [item.item_id for item in first]
    assert recall_at_k({"a"}, ids, 1) == 1
    assert ndcg_at_k({"a": 2, "c": 1}, ids, 3) > 0.9


def test_forecast_and_regression_baselines():
    assert MovingAverageForecaster(window=2).fit([1, 3, 5]).predict(2) == pytest.approx(
        [4, 4.5]
    )
    assert CrostonForecaster(alpha=0.2).fit([0, 0, 2, 0, 0, 2]).predict(3)[0] >= 0
    model = RidgeRegressor(alpha=0).fit([[0], [1], [2]], [1, 3, 5])
    assert model.predict([[3]])[0] == pytest.approx(7, abs=1e-6)


def test_metrics_handle_calibration_and_segmentation():
    assert mae([1, 2], [1, 4]) == 1
    assert rmse([1, 2], [1, 4]) == pytest.approx(2**0.5)
    assert brier_score([0, 1], [0.1, 0.9]) == pytest.approx(0.01)
    assert 0 <= expected_calibration_error([0, 1], [0.1, 0.9], bins=5) <= 1
    assert mean_iou([[0, 1], [1, 1]], [[0, 1], [0, 1]]) == pytest.approx(
        (1 / 2 + 2 / 3) / 2
    )


def test_manifest_rejects_accidental_user_data_and_is_reproducible():
    with pytest.raises(ValueError):
        ExperimentRunConfig(
            experiment_id="demand_baselines",
            baseline="moving_average",
            dataset_path="nutriflavor.db",
        )
    manifest = create_manifest(
        ExperimentRunConfig(
            experiment_id="retrieval_sparse_baseline",
            baseline="tfidf_retriever",
            seed=7,
        )
    )
    assert manifest.status == "created"
    assert manifest.seed == 7
    assert fingerprint_json({"b": 2, "a": 1}) == fingerprint_json({"a": 1, "b": 2})
