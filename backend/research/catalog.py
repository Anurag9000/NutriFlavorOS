"""Validated registry of research tasks, datasets, models, experiments, and features.

Catalog entries are evaluation contracts. They never claim that a dataset was
downloaded, a model was trained, an artifact was promoted, or a capability is
safe to enable in the product.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Iterable, List

from pydantic import BaseModel, Field, model_validator


class Readiness(str, Enum):
    IMPLEMENTED = "implemented"
    BASELINE_AVAILABLE = "baseline_available"
    ADAPTER_AVAILABLE = "adapter_available"
    RESEARCH_ONLY = "research_only"
    BLOCKED_DATA = "blocked_data"
    BLOCKED_VALIDATION = "blocked_validation"
    ANNOUNCED = "announced"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CLINICAL = "clinical"


class TaskSpec(BaseModel):
    id: str
    category: str
    name: str
    description: str
    primary_metrics: List[str] = Field(default_factory=list)
    safety_critical: bool = False


class DatasetSpec(BaseModel):
    id: str
    name: str
    source_url: str
    modalities: List[str]
    tasks: List[str]
    license: str
    readiness: Readiness
    download_policy: str = "manual_or_explicit_adapter"
    contains_personal_data: bool = False
    notes: str = ""


class ModelSpec(BaseModel):
    id: str
    name: str
    family: str
    tasks: List[str]
    readiness: Readiness
    risk: RiskLevel
    default_enabled: bool = False
    prerequisites: List[str] = Field(default_factory=list)
    notes: str = ""


class ExperimentSpec(BaseModel):
    id: str
    name: str
    tasks: List[str]
    datasets: List[str]
    models: List[str]
    split_strategy: str
    primary_metrics: List[str]
    readiness: Readiness
    risk: RiskLevel
    required_gates: List[str] = Field(default_factory=list)


class FeatureSpec(BaseModel):
    id: str
    category: str
    name: str
    readiness: Readiness
    risk: RiskLevel
    dependencies: List[str] = Field(default_factory=list)
    safety_notes: str = ""


class ResearchCatalog(BaseModel):
    version: str
    tasks: List[TaskSpec]
    datasets: List[DatasetSpec]
    models: List[ModelSpec]
    experiments: List[ExperimentSpec]
    features: List[FeatureSpec]

    @model_validator(mode="after")
    def validate_refs(self):
        collections = {
            "tasks": self.tasks,
            "datasets": self.datasets,
            "models": self.models,
            "experiments": self.experiments,
            "features": self.features,
        }
        for name, values in collections.items():
            identifiers = [value.id for value in values]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"Duplicate identifiers in {name}")

        task_ids = {value.id for value in self.tasks}
        dataset_ids = {value.id for value in self.datasets}
        model_ids = {value.id for value in self.models}
        feature_ids = {value.id for value in self.features}
        known_dependencies = task_ids | dataset_ids | model_ids | feature_ids

        for value in self.datasets:
            unknown = set(value.tasks) - task_ids
            if unknown:
                raise ValueError(
                    f"Dataset {value.id} references unknown tasks: {sorted(unknown)}"
                )
        for value in self.models:
            unknown = set(value.tasks) - task_ids
            if unknown:
                raise ValueError(
                    f"Model {value.id} references unknown tasks: {sorted(unknown)}"
                )
            if value.default_enabled and value.risk in {
                RiskLevel.HIGH,
                RiskLevel.CLINICAL,
            }:
                raise ValueError(
                    f"High-risk model {value.id} cannot be default-enabled"
                )
        for value in self.experiments:
            unknown_tasks = set(value.tasks) - task_ids
            unknown_datasets = set(value.datasets) - dataset_ids
            unknown_models = set(value.models) - model_ids
            if unknown_tasks or unknown_datasets or unknown_models:
                raise ValueError(
                    f"Experiment {value.id} has unknown references"
                )
            required = {"data_provenance", "reproducibility"}
            if not required.issubset(value.required_gates):
                raise ValueError(
                    f"Experiment {value.id} is missing mandatory gates"
                )
            if value.risk in {RiskLevel.HIGH, RiskLevel.CLINICAL} and (
                "human_review" not in value.required_gates
            ):
                raise ValueError(
                    f"High-risk experiment {value.id} requires human_review"
                )
        for value in self.features:
            unknown = set(value.dependencies) - known_dependencies
            if unknown:
                raise ValueError(
                    f"Feature {value.id} has unknown dependencies: {sorted(unknown)}"
                )
        return self

    def summary(self) -> Dict[str, Dict[str, int]]:
        result: Dict[str, Dict[str, int]] = {}
        for name in ("tasks", "datasets", "models", "experiments", "features"):
            values = getattr(self, name)
            counts = {"total": len(values)}
            for value in values:
                readiness = getattr(value, "readiness", None)
                if readiness:
                    counts[readiness.value] = counts.get(readiness.value, 0) + 1
            result[name] = counts
        return result


def _title(value: str) -> str:
    return value.replace("_", " ").title()


def _task(
    identifier: str,
    category: str,
    metrics: Iterable[str],
    *,
    safety: bool = False,
    description: str | None = None,
) -> TaskSpec:
    return TaskSpec(
        id=identifier,
        category=category,
        name=_title(identifier),
        description=description
        or f"Evaluate {_title(identifier).lower()} with explicit contracts.",
        primary_metrics=list(metrics),
        safety_critical=safety,
    )


TASK_ROWS = [
    ("recipe_search", "retrieval", ["ndcg_at_k", "recall_at_k"]),
    ("image_recipe_retrieval", "multimodal", ["recall_at_k", "median_rank"]),
    ("personalized_ranking", "recommendation", ["ndcg_at_k", "map_at_k"]),
    ("ranking_diversification", "recommendation", ["intra_list_diversity", "ndcg_at_k"]),
    ("sequential_recommendation", "recommendation", ["hit_rate_at_k", "ndcg_at_k"]),
    ("cold_start", "recommendation", ["ndcg_at_k", "coverage"]),
    ("food_classification", "vision", ["macro_f1", "balanced_accuracy"]),
    ("food_detection", "vision", ["map_50_95", "recall"]),
    ("food_segmentation", "vision", ["mean_iou", "dice"]),
    ("portion_estimation", "vision", ["mae_grams", "mape"]),
    ("nutrition_estimation", "safety", ["mae", "coverage", "calibration_error"]),
    ("ingredient_extraction", "language", ["span_f1", "quantity_parse_rate"]),
    ("instruction_structuring", "language", ["edge_f1", "dag_validity_rate"]),
    ("recipe_generation", "safety", ["constraint_violation_rate", "human_acceptance"]),
    ("substitution", "safety", ["constraint_violation_rate", "expert_acceptance"]),
    ("weekly_optimization", "planning", ["objective", "hard_violation_count"]),
    ("multiobjective_planning", "planning", ["hypervolume", "hard_violation_count"]),
    ("robust_optimization", "planning", ["worst_case_objective", "scenario_feasibility"]),
    ("counterfactual_planning", "planning", ["regret", "constraint_stability"]),
    ("preparation_scheduling", "operations", ["scheduled_rate", "makespan", "utilization"]),
    ("preparation_evidence", "evidence", ["reviewed_coverage", "schema_validity"]),
    ("demand_forecasting", "forecasting", ["mae", "rmse", "smape", "mase"]),
    ("forecast_backtesting", "forecasting", ["rolling_origin_mae", "coverage"]),
    ("inventory_simulation", "operations", ["stockout_rate", "waste_rate", "service_level"]),
    ("expiry_risk", "forecasting", ["concordance", "integrated_brier_score"]),
    ("sustainability_estimation", "sustainability", ["mae", "interval_coverage"]),
    ("food_safety_rule_check", "safety", ["recall", "false_negative_rate"]),
    ("allergen_detection", "safety", ["recall", "false_negative_rate"]),
    ("data_quality", "governance", ["error_detection_f1", "coverage"]),
    ("ood_detection", "uncertainty", ["auroc", "fpr_at_95_tpr"]),
    ("uncertainty_propagation", "uncertainty", ["coverage", "interval_width"]),
    ("preference_learning", "personalization", ["pairwise_accuracy", "log_loss"]),
    ("bandit_policy", "personalization", ["ips", "doubly_robust", "support_coverage"]),
    ("continual_personalization", "personalization", ["retention", "forward_transfer"]),
    ("n_of_1_analysis", "clinical_research", ["posterior_coverage", "sensitivity"]),
    ("privacy_audit", "security", ["attack_auc", "epsilon_or_risk_bound"]),
    ("capability_validation", "governance", ["import_success", "contract_pass_rate"]),
]

SAFETY_TASKS = {
    "nutrition_estimation",
    "recipe_generation",
    "substitution",
    "weekly_optimization",
    "robust_optimization",
    "food_safety_rule_check",
    "allergen_detection",
    "n_of_1_analysis",
}
TASKS = [
    _task(identifier, category, metrics, safety=identifier in SAFETY_TASKS)
    for identifier, category, metrics in TASK_ROWS
]


def _dataset(
    identifier: str,
    tasks: List[str],
    source_url: str = "local://research",
    license_name: str = "source-specific",
    readiness: Readiness = Readiness.RESEARCH_ONLY,
    modalities: List[str] | None = None,
    personal: bool = False,
    notes: str = "",
) -> DatasetSpec:
    return DatasetSpec(
        id=identifier,
        name=_title(identifier),
        source_url=source_url,
        modalities=modalities or ["tabular"],
        tasks=tasks,
        license=license_name,
        readiness=readiness,
        contains_personal_data=personal,
        notes=notes,
    )


DATASETS = [
    _dataset(
        "internal_recipes",
        ["recipe_search", "ingredient_extraction", "weekly_optimization", "data_quality"],
        "local://recipes",
        "repository/source-specific",
        Readiness.IMPLEMENTED,
        ["text", "tabular"],
    ),
    _dataset(
        "internal_feedback",
        ["personalized_ranking", "bandit_policy", "continual_personalization", "privacy_audit"],
        "local://feedback",
        "consent-required",
        Readiness.BLOCKED_DATA,
        ["events"],
        True,
    ),
    _dataset(
        "internal_inventory",
        ["demand_forecasting", "expiry_risk", "weekly_optimization", "inventory_simulation"],
        "local://inventory",
        "consent-required",
        Readiness.IMPLEMENTED,
        ["events"],
        True,
    ),
    _dataset(
        "internal_reservations",
        ["weekly_optimization", "inventory_simulation"],
        "local://stock-reservations",
        "consent-required",
        Readiness.IMPLEMENTED,
        ["events", "tabular"],
        True,
    ),
    _dataset(
        "internal_preparation_profiles",
        ["preparation_evidence", "preparation_scheduling", "data_quality"],
        "local://recipe-preparation-profiles",
        "reviewed-source-specific",
        Readiness.IMPLEMENTED,
        ["dag", "tabular", "evidence"],
    ),
    _dataset(
        "internal_experiment_runs",
        ["capability_validation", "data_quality"],
        "local://experiment-runs",
        "repository",
        Readiness.IMPLEMENTED,
        ["manifest", "metrics"],
    ),
    _dataset(
        "synthetic_contract_fixtures",
        ["data_quality", "ingredient_extraction", "substitution", "n_of_1_analysis"],
        "local://tests",
        "repository",
        Readiness.IMPLEMENTED,
        ["synthetic"],
    ),
    _dataset(
        "synthetic_demand_series",
        ["demand_forecasting", "forecast_backtesting"],
        "local://tests/demand",
        "repository",
        Readiness.IMPLEMENTED,
        ["synthetic", "time_series"],
    ),
    _dataset(
        "synthetic_planner_scenarios",
        ["robust_optimization", "counterfactual_planning"],
        "local://tests/planner-scenarios",
        "repository",
        Readiness.IMPLEMENTED,
        ["synthetic", "tabular"],
    ),
    _dataset(
        "synthetic_ranking_interactions",
        ["personalized_ranking", "ranking_diversification", "cold_start"],
        "local://tests/ranking",
        "repository",
        Readiness.IMPLEMENTED,
        ["synthetic", "events"],
    ),
    _dataset(
        "usda_fdc_foundation",
        ["nutrition_estimation", "data_quality"],
        "https://fdc.nal.usda.gov/download-datasets/",
        "CC0",
        Readiness.ADAPTER_AVAILABLE,
    ),
    _dataset(
        "usda_fdc_fndds",
        ["nutrition_estimation", "data_quality"],
        "https://fdc.nal.usda.gov/download-datasets/",
        "CC0",
    ),
    _dataset(
        "usda_fdc_branded",
        ["nutrition_estimation", "allergen_detection", "data_quality"],
        "https://fdc.nal.usda.gov/download-datasets/",
        "CC0",
    ),
    _dataset(
        "recipe1m_plus",
        ["recipe_search", "image_recipe_retrieval", "ingredient_extraction", "recipe_generation"],
        "http://pic2recipe.csail.mit.edu/",
        modalities=["text", "image"],
        notes="Review access and license terms before use",
    ),
    _dataset(
        "nutrition5k",
        ["portion_estimation", "nutrition_estimation"],
        "https://github.com/google-research-datasets/Nutrition5k",
        modalities=["rgb", "depth", "video", "tabular"],
    ),
    _dataset(
        "food101",
        ["food_classification", "ood_detection"],
        "https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/",
        modalities=["image"],
    ),
    _dataset(
        "foodseg103",
        ["food_segmentation", "food_detection"],
        "https://xiongweiwu.github.io/foodseg103.html",
        modalities=["image", "mask"],
    ),
    _dataset(
        "dishseg24k",
        ["food_segmentation", "food_detection"],
        "https://arxiv.org/search/?query=DishSeg24k&searchtype=all",
        readiness=Readiness.ANNOUNCED,
        modalities=["image", "mask"],
        notes="Verify release and license before use",
    ),
    _dataset(
        "uecfood256",
        ["food_classification", "food_detection"],
        "http://foodcam.mobi/dataset256.html",
        modalities=["image", "bbox"],
    ),
    _dataset(
        "vireofood172",
        ["food_classification", "ingredient_extraction"],
        "http://vireo.cs.cityu.edu.hk/VireoFood172/",
        modalities=["image", "text"],
    ),
    _dataset(
        "grocery_store",
        ["food_classification", "food_detection"],
        "https://github.com/marcusklasson/GroceryStoreDataset",
        modalities=["image"],
    ),
    _dataset(
        "open_food_facts",
        ["allergen_detection", "data_quality", "nutrition_estimation"],
        "https://world.openfoodfacts.org/data",
        "ODbL/source-specific",
        modalities=["tabular", "image"],
    ),
    _dataset(
        "nhanes_dietary",
        ["nutrition_estimation", "n_of_1_analysis"],
        "https://wwwn.cdc.gov/nchs/nhanes/",
        "public-use terms",
        modalities=["survey", "tabular"],
        personal=True,
    ),
    _dataset(
        "epic_kitchens",
        ["food_detection", "instruction_structuring"],
        "https://epic-kitchens.github.io/",
        modalities=["video", "audio"],
    ),
    _dataset(
        "ego4d",
        ["food_detection", "instruction_structuring"],
        "https://ego4d-data.org/",
        modalities=["video", "audio"],
    ),
    _dataset(
        "agribalyse",
        ["sustainability_estimation"],
        "https://agribalyse.ademe.fr/",
        modalities=["lca", "tabular"],
    ),
    _dataset(
        "ecoinvent",
        ["sustainability_estimation"],
        "https://ecoinvent.org/",
        "commercial/source-specific",
        Readiness.BLOCKED_DATA,
        ["lca", "tabular"],
    ),
    _dataset(
        "water_footprint",
        ["sustainability_estimation"],
        "https://www.waterfootprint.org/resources/",
    ),
    _dataset(
        "food2k",
        ["food_classification", "ood_detection"],
        "https://github.com/AlvinChou/Food2K",
        modalities=["image"],
    ),
    _dataset(
        "isia_food500",
        ["food_classification", "ood_detection"],
        "https://github.com/ustc-vim/ISIA-Food500",
        modalities=["image"],
    ),
]


def _model(
    identifier: str,
    family: str,
    tasks: List[str],
    readiness: Readiness = Readiness.RESEARCH_ONLY,
    risk: RiskLevel = RiskLevel.MODERATE,
    prerequisites: List[str] | None = None,
    notes: str = "",
) -> ModelSpec:
    return ModelSpec(
        id=identifier,
        name=_title(identifier),
        family=family,
        tasks=tasks,
        readiness=readiness,
        risk=risk,
        default_enabled=False,
        prerequisites=prerequisites or [],
        notes=notes,
    )


MODEL_ROWS = [
    ("tfidf_retriever", "retrieval", ["recipe_search"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("bm25_retriever", "retrieval", ["recipe_search"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("dense_text_retriever", "retrieval", ["recipe_search"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("clip_retriever", "multimodal", ["image_recipe_retrieval"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("siglip_retriever", "multimodal", ["image_recipe_retrieval"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("popularity_recommender", "recommendation", ["personalized_ranking", "cold_start"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("bayesian_popularity_recommender", "recommendation", ["personalized_ranking", "cold_start"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("content_recommender", "recommendation", ["personalized_ranking", "cold_start"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("item_knn_recommender", "collaborative_filtering", ["personalized_ranking"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("matrix_factorization", "recommendation", ["personalized_ranking"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("mmr_diversity_reranker", "reranking", ["ranking_diversification"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("two_tower", "recommendation", ["personalized_ranking"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("lightgcn", "recommendation", ["personalized_ranking"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("sasrec", "sequential", ["sequential_recommendation"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("bert4rec", "sequential", ["sequential_recommendation"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("linucb", "bandit", ["bandit_policy"], Readiness.BASELINE_AVAILABLE, RiskLevel.HIGH),
    ("thompson_sampling", "bandit", ["bandit_policy"], Readiness.BASELINE_AVAILABLE, RiskLevel.HIGH),
    ("resnet_food", "vision", ["food_classification"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("convnext_food", "vision", ["food_classification"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("vit_food", "vision", ["food_classification"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("swin_food", "vision", ["food_classification"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("dinov2_linear", "vision", ["food_classification", "ood_detection"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("faster_rcnn_food", "detection", ["food_detection"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("unet_food", "segmentation", ["food_segmentation"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("deeplab_food", "segmentation", ["food_segmentation"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("segformer_food", "segmentation", ["food_segmentation"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("mask2former_food", "segmentation", ["food_segmentation"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("prompt_segmenter", "segmentation", ["food_segmentation"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("rgbd_multitask_nutrition", "multimodal_regression", ["portion_estimation", "nutrition_estimation"], Readiness.RESEARCH_ONLY, RiskLevel.CLINICAL),
    ("component_weight_pipeline", "compositional_vision", ["portion_estimation", "nutrition_estimation"], Readiness.RESEARCH_ONLY, RiskLevel.CLINICAL),
    ("deep_ensemble_nutrition", "uncertainty", ["nutrition_estimation", "ood_detection", "uncertainty_propagation"], Readiness.RESEARCH_ONLY, RiskLevel.CLINICAL),
    ("ingredient_parser_rules", "rules", ["ingredient_extraction"], Readiness.IMPLEMENTED, RiskLevel.LOW),
    ("ingredient_ner", "sequence_labeling", ["ingredient_extraction"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("instruction_dag_rules", "rules", ["instruction_structuring"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("constrained_recipe_generator", "generation", ["recipe_generation"], Readiness.BLOCKED_VALIDATION, RiskLevel.HIGH),
    ("substitution_graph", "knowledge_graph", ["substitution"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("graphsage_substitution", "graph_neural_network", ["substitution"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("beam_weekly_optimizer", "optimization", ["weekly_optimization", "multiobjective_planning"], Readiness.IMPLEMENTED, RiskLevel.MODERATE),
    ("household_pantry_optimizer", "optimization", ["weekly_optimization", "multiobjective_planning"], Readiness.IMPLEMENTED, RiskLevel.MODERATE),
    ("pareto_optimizer", "optimization", ["multiobjective_planning"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("robust_pareto_optimizer", "robust_optimization", ["robust_optimization", "counterfactual_planning"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("planner_scenario_stress_test", "evaluation", ["robust_optimization", "counterfactual_planning"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("cp_sat_optimizer", "optimization", ["weekly_optimization", "multiobjective_planning"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("milp_optimizer", "optimization", ["weekly_optimization", "multiobjective_planning"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("nsga2_planner", "optimization", ["multiobjective_planning"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("preparation_resource_scheduler", "scheduling", ["preparation_scheduling"], Readiness.IMPLEMENTED, RiskLevel.MODERATE),
    ("preparation_profile_compiler", "evidence_compiler", ["preparation_evidence", "preparation_scheduling"], Readiness.IMPLEMENTED, RiskLevel.MODERATE),
    ("moving_average", "forecasting", ["demand_forecasting"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("seasonal_naive", "forecasting", ["demand_forecasting"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("simple_exponential_smoothing", "forecasting", ["demand_forecasting"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("holt_linear", "forecasting", ["demand_forecasting"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("croston", "forecasting", ["demand_forecasting"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("tsb_intermittent_demand", "forecasting", ["demand_forecasting"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("rolling_origin_backtest", "evaluation", ["forecast_backtesting"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("ridge_regression", "regression", ["nutrition_estimation", "sustainability_estimation"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW),
    ("arima_demand", "forecasting", ["demand_forecasting"], Readiness.RESEARCH_ONLY, RiskLevel.LOW),
    ("nbeats_demand", "forecasting", ["demand_forecasting"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("tft_demand", "forecasting", ["demand_forecasting", "expiry_risk"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("survival_expiry", "survival", ["expiry_risk"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("lca_inventory", "lca", ["sustainability_estimation"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("monte_carlo_lca", "lca", ["sustainability_estimation", "uncertainty_propagation"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("food_safety_rules", "rules", ["food_safety_rule_check"], Readiness.BLOCKED_DATA, RiskLevel.CLINICAL),
    ("allergen_ontology", "ontology", ["allergen_detection"], Readiness.BLOCKED_DATA, RiskLevel.CLINICAL),
    ("isolation_forest_quality", "anomaly", ["data_quality", "ood_detection"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE),
    ("mahalanobis_ood", "ood", ["ood_detection"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("conformal_predictor", "calibration", ["nutrition_estimation", "expiry_risk", "uncertainty_propagation"], Readiness.BASELINE_AVAILABLE, RiskLevel.HIGH),
    ("pairwise_btl", "preference", ["preference_learning"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE),
    ("replay_personalization", "continual", ["continual_personalization"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("adapter_personalization", "continual", ["continual_personalization"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("bayesian_nof1", "causal", ["n_of_1_analysis"], Readiness.RESEARCH_ONLY, RiskLevel.CLINICAL),
    ("privacy_attack_baseline", "privacy", ["privacy_audit"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    ("capability_registry_validator", "governance", ["capability_validation"], Readiness.IMPLEMENTED, RiskLevel.LOW),
]
MODELS = [_model(*row) for row in MODEL_ROWS]


def _experiment(
    identifier: str,
    tasks: List[str],
    datasets: List[str],
    models: List[str],
    readiness: Readiness = Readiness.RESEARCH_ONLY,
    risk: RiskLevel = RiskLevel.MODERATE,
    split: str = "group-aware holdout",
    metrics: List[str] | None = None,
    extra_gates: List[str] | None = None,
) -> ExperimentSpec:
    gates = ["data_provenance", "reproducibility"]
    if risk in {RiskLevel.HIGH, RiskLevel.CLINICAL}:
        gates.append("human_review")
    gates.extend(extra_gates or [])
    return ExperimentSpec(
        id=identifier,
        name=_title(identifier),
        tasks=tasks,
        datasets=datasets,
        models=models,
        split_strategy=split,
        primary_metrics=metrics or ["primary_metric"],
        readiness=readiness,
        risk=risk,
        required_gates=sorted(set(gates)),
    )


EXPERIMENTS = [
    _experiment("retrieval_sparse_baseline", ["recipe_search"], ["internal_recipes"], ["tfidf_retriever", "bm25_retriever"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW, metrics=["ndcg_at_k", "recall_at_k"]),
    _experiment("multimodal_retrieval", ["image_recipe_retrieval"], ["recipe1m_plus"], ["clip_retriever", "siglip_retriever"]),
    _experiment("personalization_baselines", ["personalized_ranking", "cold_start"], ["internal_feedback", "internal_recipes"], ["popularity_recommender", "bayesian_popularity_recommender", "content_recommender", "item_knn_recommender", "matrix_factorization"], Readiness.BLOCKED_DATA),
    _experiment("ranking_diversity_benchmark", ["personalized_ranking", "ranking_diversification"], ["synthetic_ranking_interactions"], ["bayesian_popularity_recommender", "item_knn_recommender", "mmr_diversity_reranker"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE, metrics=["ndcg_at_k", "intra_list_diversity", "coverage"]),
    _experiment("sequential_recommendation", ["sequential_recommendation"], ["internal_feedback"], ["sasrec", "bert4rec"], Readiness.BLOCKED_DATA, RiskLevel.HIGH),
    _experiment("optimizer_benchmark", ["weekly_optimization", "multiobjective_planning"], ["internal_recipes", "synthetic_contract_fixtures"], ["beam_weekly_optimizer", "pareto_optimizer", "cp_sat_optimizer", "milp_optimizer", "nsga2_planner"]),
    _experiment("robust_planner_scenarios", ["robust_optimization", "counterfactual_planning"], ["synthetic_planner_scenarios", "internal_recipes"], ["robust_pareto_optimizer", "planner_scenario_stress_test", "beam_weekly_optimizer"], Readiness.BASELINE_AVAILABLE, RiskLevel.MODERATE, metrics=["worst_case_objective", "scenario_feasibility", "regret"]),
    _experiment("pantry_replay", ["weekly_optimization", "demand_forecasting"], ["internal_inventory"], ["household_pantry_optimizer", "moving_average"], Readiness.BASELINE_AVAILABLE),
    _experiment("demand_baselines", ["demand_forecasting"], ["internal_inventory", "synthetic_demand_series"], ["moving_average", "seasonal_naive", "simple_exponential_smoothing", "holt_linear", "croston", "tsb_intermittent_demand", "arima_demand"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW, "rolling-origin temporal split", ["mae", "rmse", "smape", "mase"]),
    _experiment("intermittent_demand_benchmark", ["demand_forecasting", "forecast_backtesting"], ["synthetic_demand_series", "internal_inventory"], ["croston", "tsb_intermittent_demand", "rolling_origin_backtest"], Readiness.BASELINE_AVAILABLE, RiskLevel.LOW, "rolling-origin temporal split", ["mae", "mase", "stockout_proxy"]),
    _experiment("preparation_scheduler_benchmark", ["preparation_scheduling"], ["internal_preparation_profiles", "synthetic_contract_fixtures"], ["preparation_profile_compiler", "preparation_resource_scheduler"], Readiness.IMPLEMENTED, RiskLevel.MODERATE, "versioned scenario fixtures", ["scheduled_rate", "makespan", "capacity_violation_count"]),
    _experiment("preparation_evidence_coverage", ["preparation_evidence", "data_quality"], ["internal_preparation_profiles", "internal_recipes"], ["preparation_profile_compiler"], Readiness.IMPLEMENTED, RiskLevel.MODERATE, "full catalog audit", ["reviewed_coverage", "serving_range_coverage", "dag_validity_rate"]),
    _experiment("inventory_simulation_replay", ["inventory_simulation", "demand_forecasting"], ["internal_inventory", "internal_reservations", "synthetic_demand_series"], ["moving_average", "seasonal_naive", "croston", "tsb_intermittent_demand"], Readiness.RESEARCH_ONLY, RiskLevel.MODERATE, "rolling-origin event replay", ["stockout_rate", "waste_rate", "service_level"]),
    _experiment("expiry_risk_calibration", ["expiry_risk"], ["internal_inventory"], ["survival_expiry", "tft_demand"]),
    _experiment("vision_food101", ["food_classification", "ood_detection"], ["food101", "food2k", "isia_food500"], ["resnet_food", "convnext_food", "vit_food", "swin_food", "dinov2_linear"]),
    _experiment("detection_benchmark", ["food_detection"], ["uecfood256", "grocery_store"], ["faster_rcnn_food"]),
    _experiment("segmentation_foodseg", ["food_segmentation"], ["foodseg103", "dishseg24k"], ["unet_food", "deeplab_food", "segformer_food", "mask2former_food", "prompt_segmenter"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    _experiment("nutrition5k_rgbd", ["portion_estimation", "nutrition_estimation"], ["nutrition5k", "usda_fdc_foundation"], ["rgbd_multitask_nutrition", "component_weight_pipeline", "deep_ensemble_nutrition"], Readiness.BLOCKED_VALIDATION, RiskLevel.CLINICAL, extra_gates=["clinical_validation", "ood_evaluation", "calibration"]),
    _experiment("ingredient_parser_benchmark", ["ingredient_extraction"], ["internal_recipes", "recipe1m_plus", "synthetic_contract_fixtures"], ["ingredient_parser_rules", "ingredient_ner"]),
    _experiment("instruction_structuring", ["instruction_structuring"], ["recipe1m_plus", "epic_kitchens"], ["instruction_dag_rules"]),
    _experiment("substitution_counterfactual", ["substitution", "allergen_detection"], ["internal_recipes", "synthetic_contract_fixtures"], ["substitution_graph", "graphsage_substitution"], Readiness.RESEARCH_ONLY, RiskLevel.HIGH, extra_gates=["allergen_false_negative_review"]),
    _experiment("bandit_offline_policy", ["bandit_policy"], ["internal_feedback"], ["linucb", "thompson_sampling"], Readiness.BLOCKED_DATA, RiskLevel.HIGH, extra_gates=["support_overlap", "off_policy_evaluation"]),
    _experiment("continual_personalization", ["continual_personalization"], ["internal_feedback"], ["replay_personalization", "adapter_personalization"], Readiness.BLOCKED_DATA, RiskLevel.HIGH, extra_gates=["forgetting_audit", "privacy_review"]),
    _experiment("lca_uncertainty", ["sustainability_estimation", "uncertainty_propagation"], ["agribalyse", "ecoinvent", "water_footprint"], ["lca_inventory", "monte_carlo_lca"], Readiness.BLOCKED_DATA),
    _experiment("data_quality_red_team", ["data_quality"], ["internal_recipes", "usda_fdc_foundation", "usda_fdc_branded", "synthetic_contract_fixtures"], ["isolation_forest_quality"], Readiness.RESEARCH_ONLY, RiskLevel.LOW),
    _experiment("privacy_membership", ["privacy_audit"], ["internal_feedback", "synthetic_contract_fixtures"], ["privacy_attack_baseline", "adapter_personalization"], Readiness.BLOCKED_DATA, RiskLevel.HIGH, extra_gates=["privacy_review"]),
    _experiment("nof1_synthetic_protocol", ["n_of_1_analysis"], ["synthetic_contract_fixtures"], ["bayesian_nof1"], Readiness.RESEARCH_ONLY, RiskLevel.CLINICAL, extra_gates=["clinical_validation"]),
    _experiment("capability_registry_validation", ["capability_validation"], ["internal_experiment_runs", "synthetic_contract_fixtures"], ["capability_registry_validator"], Readiness.IMPLEMENTED, RiskLevel.LOW, "full import and symbol audit", ["import_success", "contract_pass_rate"]),
]


def _feature(
    identifier: str,
    category: str,
    readiness: Readiness,
    risk: RiskLevel = RiskLevel.MODERATE,
    dependencies: List[str] | None = None,
    safety_notes: str = "",
) -> FeatureSpec:
    return FeatureSpec(
        id=identifier,
        category=category,
        name=_title(identifier),
        readiness=readiness,
        risk=risk,
        dependencies=dependencies or [],
        safety_notes=safety_notes,
    )


FEATURES = [
    _feature("household_profiles", "product", Readiness.IMPLEMENTED, dependencies=["weekly_optimization"]),
    _feature("pantry_lots", "product", Readiness.IMPLEMENTED),
    _feature("inventory_ledger", "product", Readiness.IMPLEMENTED),
    _feature("leftover_batches", "product", Readiness.IMPLEMENTED),
    _feature("shopping_reconciliation", "product", Readiness.IMPLEMENTED),
    _feature("batch_prep", "product", Readiness.IMPLEMENTED),
    _feature("family_planning", "product", Readiness.IMPLEMENTED, dependencies=["household_pantry_optimizer"]),
    _feature("pareto_explorer", "research", Readiness.BASELINE_AVAILABLE, dependencies=["pareto_optimizer"]),
    _feature("robust_scenario_planning", "research", Readiness.BASELINE_AVAILABLE, dependencies=["robust_pareto_optimizer", "planner_scenario_stress_test"]),
    _feature("constraint_explanations", "product", Readiness.IMPLEMENTED),
    _feature("preparation_profiles", "evidence", Readiness.IMPLEMENTED, dependencies=["internal_preparation_profiles"]),
    _feature("preparation_task_compilation", "product", Readiness.IMPLEMENTED, dependencies=["preparation_profile_compiler"]),
    _feature("resource_scheduling", "product", Readiness.IMPLEMENTED, dependencies=["preparation_resource_scheduler"]),
    _feature("dependency_dag_scheduling", "product", Readiness.IMPLEMENTED, dependencies=["preparation_resource_scheduler"]),
    _feature("preparation_import_cli", "evidence", Readiness.IMPLEMENTED, dependencies=["internal_preparation_profiles"]),
    _feature("forecast_backtesting", "research", Readiness.BASELINE_AVAILABLE, dependencies=["rolling_origin_backtest"]),
    _feature("ranking_diversification", "research", Readiness.BASELINE_AVAILABLE, dependencies=["mmr_diversity_reranker"]),
    _feature("runtime_capability_validation", "governance", Readiness.IMPLEMENTED, dependencies=["capability_registry_validator"]),
    _feature("fooddata_central", "adapter", Readiness.ADAPTER_AVAILABLE, dependencies=["usda_fdc_foundation"]),
    _feature("dataset_registry", "research", Readiness.IMPLEMENTED),
    _feature("model_registry", "research", Readiness.IMPLEMENTED),
    _feature("experiment_manifests", "research", Readiness.IMPLEMENTED),
    _feature("offline_baselines", "research", Readiness.BASELINE_AVAILABLE),
    _feature("model_cards", "governance", Readiness.IMPLEMENTED),
    _feature("dataset_cards", "governance", Readiness.IMPLEMENTED),
    _feature("shadow_deployment", "governance", Readiness.RESEARCH_ONLY, RiskLevel.HIGH),
    _feature("drift_monitoring", "governance", Readiness.IMPLEMENTED),
    _feature("rollback", "governance", Readiness.IMPLEMENTED),
    _feature("pairwise_preferences", "product", Readiness.RESEARCH_ONLY, dependencies=["pairwise_btl"]),
    _feature("safe_bandits", "research", Readiness.BLOCKED_VALIDATION, RiskLevel.HIGH, ["linucb", "thompson_sampling"], "Requires consent, support overlap, off-policy evaluation, and kill switches."),
    _feature("receipt_import", "product", Readiness.RESEARCH_ONLY, RiskLevel.MODERATE, ["data_quality"]),
    _feature("food_photo_correction", "product", Readiness.BLOCKED_VALIDATION, RiskLevel.HIGH, ["food_classification", "nutrition_estimation"]),
    _feature("structured_generation", "research", Readiness.BLOCKED_VALIDATION, RiskLevel.HIGH, ["constrained_recipe_generator"]),
    _feature("substitution_suggestions", "product", Readiness.BASELINE_AVAILABLE, RiskLevel.HIGH, ["substitution_graph"], "Never treat a suggestion as allergy-safe without reviewed evidence."),
    _feature("evidence_coverage_dashboard", "governance", Readiness.RESEARCH_ONLY, dependencies=["preparation_evidence", "data_quality"]),
    _feature("inventory_simulator", "research", Readiness.RESEARCH_ONLY, dependencies=["inventory_simulation", "demand_forecasting"]),
    _feature("data_export_delete", "privacy", Readiness.RESEARCH_ONLY, RiskLevel.HIGH, ["privacy_audit"]),
]


CATALOG = ResearchCatalog(
    version="2026-08-01.1",
    tasks=TASKS,
    datasets=DATASETS,
    models=MODELS,
    experiments=EXPERIMENTS,
    features=FEATURES,
)


def get_catalog() -> ResearchCatalog:
    return CATALOG.model_copy(deep=True)


def get_by_id(collection: str, item_id: str):
    if collection not in {
        "tasks",
        "datasets",
        "models",
        "experiments",
        "features",
    }:
        raise KeyError(collection)
    for item in getattr(CATALOG, collection):
        if item.id == item_id:
            return item.model_copy(deep=True)
    raise LookupError(item_id)
