"""Validated registry of research tasks, datasets, models, experiments, and features.

Catalog entries are evaluation contracts; they do not claim that data was
downloaded, a model was trained, or a feature is safe to enable.
"""
from __future__ import annotations
from enum import Enum
from typing import Dict, List
from pydantic import BaseModel, Field, model_validator

class Readiness(str,Enum):
    IMPLEMENTED="implemented"; BASELINE_AVAILABLE="baseline_available"; ADAPTER_AVAILABLE="adapter_available"; RESEARCH_ONLY="research_only"; BLOCKED_DATA="blocked_data"; BLOCKED_VALIDATION="blocked_validation"; ANNOUNCED="announced"
class RiskLevel(str,Enum): LOW="low"; MODERATE="moderate"; HIGH="high"; CLINICAL="clinical"
class TaskSpec(BaseModel):
    id:str; category:str; name:str; description:str; primary_metrics:List[str]=Field(default_factory=list); safety_critical:bool=False
class DatasetSpec(BaseModel):
    id:str; name:str; source_url:str; modalities:List[str]; tasks:List[str]; license:str; readiness:Readiness; download_policy:str="manual_or_explicit_adapter"; contains_personal_data:bool=False; notes:str=""
class ModelSpec(BaseModel):
    id:str; name:str; family:str; tasks:List[str]; readiness:Readiness; risk:RiskLevel; default_enabled:bool=False; prerequisites:List[str]=Field(default_factory=list); notes:str=""
class ExperimentSpec(BaseModel):
    id:str; name:str; tasks:List[str]; datasets:List[str]; models:List[str]; split_strategy:str; primary_metrics:List[str]; readiness:Readiness; risk:RiskLevel; required_gates:List[str]=Field(default_factory=list)
class FeatureSpec(BaseModel):
    id:str; category:str; name:str; readiness:Readiness; risk:RiskLevel; dependencies:List[str]=Field(default_factory=list); safety_notes:str=""
class ResearchCatalog(BaseModel):
    version:str; tasks:List[TaskSpec]; datasets:List[DatasetSpec]; models:List[ModelSpec]; experiments:List[ExperimentSpec]; features:List[FeatureSpec]
    @model_validator(mode="after")
    def validate_refs(self):
        for name in ("tasks","datasets","models","experiments","features"):
            ids=[x.id for x in getattr(self,name)]
            if len(ids)!=len(set(ids)): raise ValueError(f"Duplicate identifiers in {name}")
        tasks={x.id for x in self.tasks}; datasets={x.id for x in self.datasets}; models={x.id for x in self.models}
        for value in self.datasets:
            if set(value.tasks)-tasks: raise ValueError(f"Dataset {value.id} references unknown tasks")
        for value in self.models:
            if set(value.tasks)-tasks: raise ValueError(f"Model {value.id} references unknown tasks")
        for value in self.experiments:
            if set(value.tasks)-tasks or set(value.datasets)-datasets or set(value.models)-models: raise ValueError(f"Experiment {value.id} has unknown references")
        return self
    def summary(self)->Dict[str,Dict[str,int]]:
        result={}
        for name in ("tasks","datasets","models","experiments","features"):
            values=getattr(self,name); counts={"total":len(values)}
            for value in values:
                readiness=getattr(value,"readiness",None)
                if readiness: counts[readiness.value]=counts.get(readiness.value,0)+1
            result[name]=counts
        return result

def _title(value:str)->str: return value.replace("_"," ").title()
def _task(identifier:str,category:str="research",safety:bool=False)->TaskSpec:
    return TaskSpec(id=identifier,category=category,name=_title(identifier),description=f"Evaluate {_title(identifier).lower()} with explicit contracts.",primary_metrics=["primary_metric"],safety_critical=safety)
TASK_IDS=["recipe_search","image_recipe_retrieval","personalized_ranking","sequential_recommendation","cold_start","food_classification","food_detection","food_segmentation","portion_estimation","nutrition_estimation","ingredient_extraction","instruction_structuring","recipe_generation","substitution","weekly_optimization","multiobjective_planning","demand_forecasting","expiry_risk","sustainability_estimation","food_safety_rule_check","allergen_detection","data_quality","ood_detection","preference_learning","bandit_policy","continual_personalization","n_of_1_analysis","privacy_audit"]
SAFETY_TASKS={"nutrition_estimation","recipe_generation","substitution","weekly_optimization","food_safety_rule_check","allergen_detection","n_of_1_analysis"}
TASKS=[_task(value,"safety" if value in SAFETY_TASKS else "research",value in SAFETY_TASKS) for value in TASK_IDS]

def _dataset(identifier:str,tasks:List[str],url:str="local://research",license_name:str="source-specific",readiness:Readiness=Readiness.RESEARCH_ONLY,modalities:List[str]|None=None,personal:bool=False,notes:str="")->DatasetSpec:
    return DatasetSpec(id=identifier,name=_title(identifier),source_url=url,modalities=modalities or ["tabular"],tasks=tasks,license=license_name,readiness=readiness,contains_personal_data=personal,notes=notes)
DATASETS=[
_dataset("internal_recipes",["recipe_search","ingredient_extraction","weekly_optimization","data_quality"],"local://recipes","repository/source-specific",Readiness.IMPLEMENTED,["text","tabular"]),
_dataset("internal_feedback",["personalized_ranking","bandit_policy","continual_personalization","privacy_audit"],"local://feedback","consent-required",Readiness.BLOCKED_DATA,["events"],True),
_dataset("internal_inventory",["demand_forecasting","expiry_risk","weekly_optimization"],"local://inventory","consent-required",Readiness.IMPLEMENTED,["events"],True),
_dataset("usda_fdc_foundation",["nutrition_estimation","data_quality"],"https://fdc.nal.usda.gov/download-datasets/","CC0",Readiness.ADAPTER_AVAILABLE),
_dataset("usda_fdc_fndds",["nutrition_estimation","data_quality"],"https://fdc.nal.usda.gov/download-datasets/","CC0"),
_dataset("usda_fdc_branded",["nutrition_estimation","allergen_detection","data_quality"],"https://fdc.nal.usda.gov/download-datasets/","CC0"),
_dataset("recipe1m_plus",["recipe_search","image_recipe_retrieval","ingredient_extraction","recipe_generation"],"http://pic2recipe.csail.mit.edu/",modalities=["text","image"],notes="Review access and license terms"),
_dataset("nutrition5k",["portion_estimation","nutrition_estimation"],"https://github.com/google-research-datasets/Nutrition5k",modalities=["rgb","depth","video","tabular"]),
_dataset("food101",["food_classification","ood_detection"],"https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/",modalities=["image"]),
_dataset("foodseg103",["food_segmentation","food_detection"],"https://xiongweiwu.github.io/foodseg103.html",modalities=["image","mask"]),
_dataset("dishseg24k",["food_segmentation","food_detection"],"https://arxiv.org/search/?query=DishSeg24k&searchtype=all",readiness=Readiness.ANNOUNCED,modalities=["image","mask"],notes="Announced; verify release and license before use"),
_dataset("uecfood256",["food_classification","food_detection"],"http://foodcam.mobi/dataset256.html",modalities=["image","bbox"]),
_dataset("vireofood172",["food_classification","ingredient_extraction"],"http://vireo.cs.cityu.edu.hk/VireoFood172/",modalities=["image","text"]),
_dataset("grocery_store",["food_classification","food_detection"],"https://github.com/marcusklasson/GroceryStoreDataset",modalities=["image"]),
_dataset("open_food_facts",["allergen_detection","data_quality","nutrition_estimation"],"https://world.openfoodfacts.org/data","ODbL/source-specific",modalities=["tabular","image"]),
_dataset("nhanes_dietary",["nutrition_estimation","n_of_1_analysis"],"https://wwwn.cdc.gov/nchs/nhanes/","public-use terms",modalities=["survey","tabular"],personal=True),
_dataset("epic_kitchens",["food_detection","instruction_structuring"],"https://epic-kitchens.github.io/",modalities=["video","audio"]),
_dataset("ego4d",["food_detection","instruction_structuring"],"https://ego4d-data.org/",modalities=["video","audio"]),
_dataset("agribalyse",["sustainability_estimation"],"https://agribalyse.ademe.fr/",modalities=["lca","tabular"]),
_dataset("ecoinvent",["sustainability_estimation"],"https://ecoinvent.org/","commercial/source-specific",Readiness.BLOCKED_DATA,["lca","tabular"]),
_dataset("water_footprint",["sustainability_estimation"],"https://www.waterfootprint.org/resources/"),
_dataset("food2k",["food_classification","ood_detection"],"https://github.com/AlvinChou/Food2K",modalities=["image"]),
_dataset("isia_food500",["food_classification","ood_detection"],"https://github.com/ustc-vim/ISIA-Food500",modalities=["image"]),
_dataset("synthetic_contract_fixtures",["data_quality","ingredient_extraction","substitution","n_of_1_analysis"],"local://tests","repository",Readiness.IMPLEMENTED,["synthetic"]),
]

def _model(identifier:str,family:str,tasks:List[str],readiness:Readiness=Readiness.RESEARCH_ONLY,risk:RiskLevel=RiskLevel.MODERATE)->ModelSpec:
    return ModelSpec(id=identifier,name=_title(identifier),family=family,tasks=tasks,readiness=readiness,risk=risk,default_enabled=False)
MODEL_ROWS=[
("tfidf_retriever","retrieval",["recipe_search"],Readiness.BASELINE_AVAILABLE,RiskLevel.LOW),("bm25_retriever","retrieval",["recipe_search"],Readiness.RESEARCH_ONLY,RiskLevel.LOW),("dense_text_retriever","retrieval",["recipe_search"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("clip_retriever","multimodal",["image_recipe_retrieval"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("siglip_retriever","multimodal",["image_recipe_retrieval"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("popularity_recommender","recommendation",["personalized_ranking","cold_start"],Readiness.BASELINE_AVAILABLE,RiskLevel.LOW),("content_recommender","recommendation",["personalized_ranking","cold_start"],Readiness.BASELINE_AVAILABLE,RiskLevel.LOW),("matrix_factorization","recommendation",["personalized_ranking"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("two_tower","recommendation",["personalized_ranking"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("lightgcn","recommendation",["personalized_ranking"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("sasrec","sequential",["sequential_recommendation"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("bert4rec","sequential",["sequential_recommendation"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("linucb","bandit",["bandit_policy"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("thompson_sampling","bandit",["bandit_policy"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("resnet_food","vision",["food_classification"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("convnext_food","vision",["food_classification"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("vit_food","vision",["food_classification"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("swin_food","vision",["food_classification"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("dinov2_linear","vision",["food_classification","ood_detection"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("faster_rcnn_food","detection",["food_detection"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("unet_food","segmentation",["food_segmentation"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("deeplab_food","segmentation",["food_segmentation"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("segformer_food","segmentation",["food_segmentation"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("mask2former_food","segmentation",["food_segmentation"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("prompt_segmenter","segmentation",["food_segmentation"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("rgbd_multitask_nutrition","multimodal_regression",["portion_estimation","nutrition_estimation"],Readiness.RESEARCH_ONLY,RiskLevel.CLINICAL),("component_weight_pipeline","compositional_vision",["portion_estimation","nutrition_estimation"],Readiness.RESEARCH_ONLY,RiskLevel.CLINICAL),("deep_ensemble_nutrition","uncertainty",["nutrition_estimation","ood_detection"],Readiness.RESEARCH_ONLY,RiskLevel.CLINICAL),("ingredient_parser_rules","rules",["ingredient_extraction"],Readiness.IMPLEMENTED,RiskLevel.LOW),("ingredient_ner","sequence_labeling",["ingredient_extraction"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("instruction_dag_rules","rules",["instruction_structuring"],Readiness.BASELINE_AVAILABLE,RiskLevel.LOW),("constrained_recipe_generator","generation",["recipe_generation"],Readiness.BLOCKED_VALIDATION,RiskLevel.HIGH),("substitution_graph","knowledge_graph",["substitution"],Readiness.BASELINE_AVAILABLE,RiskLevel.MODERATE),("graphsage_substitution","graph_neural_network",["substitution"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("beam_weekly_optimizer","optimization",["weekly_optimization","multiobjective_planning"],Readiness.IMPLEMENTED,RiskLevel.MODERATE),("cp_sat_optimizer","optimization",["weekly_optimization","multiobjective_planning"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("milp_optimizer","optimization",["weekly_optimization","multiobjective_planning"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("nsga2_planner","optimization",["multiobjective_planning"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("moving_average","forecasting",["demand_forecasting"],Readiness.BASELINE_AVAILABLE,RiskLevel.LOW),("croston","forecasting",["demand_forecasting"],Readiness.BASELINE_AVAILABLE,RiskLevel.LOW),("ridge_regression","regression",["nutrition_estimation","sustainability_estimation"],Readiness.BASELINE_AVAILABLE,RiskLevel.LOW),("arima_demand","forecasting",["demand_forecasting"],Readiness.RESEARCH_ONLY,RiskLevel.LOW),("nbeats_demand","forecasting",["demand_forecasting"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("tft_demand","forecasting",["demand_forecasting","expiry_risk"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("survival_expiry","survival",["expiry_risk"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("lca_inventory","lca",["sustainability_estimation"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("monte_carlo_lca","lca",["sustainability_estimation"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("food_safety_rules","rules",["food_safety_rule_check"],Readiness.BLOCKED_DATA,RiskLevel.CLINICAL),("allergen_ontology","ontology",["allergen_detection"],Readiness.BLOCKED_DATA,RiskLevel.CLINICAL),("isolation_forest_quality","anomaly",["data_quality","ood_detection"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("mahalanobis_ood","ood",["ood_detection"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("conformal_predictor","calibration",["nutrition_estimation","expiry_risk"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("pairwise_btl","preference",["preference_learning"],Readiness.RESEARCH_ONLY,RiskLevel.MODERATE),("replay_personalization","continual",["continual_personalization"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("adapter_personalization","continual",["continual_personalization"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("bayesian_nof1","causal",["n_of_1_analysis"],Readiness.RESEARCH_ONLY,RiskLevel.CLINICAL),("privacy_attack_baseline","privacy",["privacy_audit"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH)]
MODELS=[_model(*row) for row in MODEL_ROWS]

def _experiment(identifier:str,tasks:List[str],datasets:List[str],models:List[str],readiness:Readiness=Readiness.RESEARCH_ONLY,risk:RiskLevel=RiskLevel.MODERATE,split:str="group-aware holdout")->ExperimentSpec:
    return ExperimentSpec(id=identifier,name=_title(identifier),tasks=tasks,datasets=datasets,models=models,split_strategy=split,primary_metrics=["primary_metric"],readiness=readiness,risk=risk,required_gates=["data_provenance","reproducibility"])
EXPERIMENT_ROWS=[
("retrieval_sparse_baseline",["recipe_search"],["internal_recipes"],["tfidf_retriever","bm25_retriever"],Readiness.BASELINE_AVAILABLE,RiskLevel.LOW),("multimodal_retrieval",["image_recipe_retrieval"],["recipe1m_plus"],["clip_retriever","siglip_retriever"]),("personalization_baselines",["personalized_ranking","cold_start"],["internal_feedback","internal_recipes"],["popularity_recommender","content_recommender","matrix_factorization"]),("sequential_recommendation",["sequential_recommendation"],["internal_feedback"],["sasrec","bert4rec"],Readiness.BLOCKED_DATA,RiskLevel.HIGH),("optimizer_benchmark",["weekly_optimization","multiobjective_planning"],["internal_recipes","synthetic_contract_fixtures"],["beam_weekly_optimizer","cp_sat_optimizer","milp_optimizer","nsga2_planner"]),("pantry_replay",["weekly_optimization","demand_forecasting"],["internal_inventory"],["beam_weekly_optimizer","moving_average"],Readiness.BASELINE_AVAILABLE,RiskLevel.MODERATE),("demand_baselines",["demand_forecasting"],["internal_inventory"],["moving_average","croston","arima_demand"]),("expiry_risk_calibration",["expiry_risk"],["internal_inventory"],["survival_expiry","tft_demand"]),("vision_food101",["food_classification","ood_detection"],["food101","food2k","isia_food500"],["resnet_food","convnext_food","vit_food","swin_food","dinov2_linear"]),("detection_benchmark",["food_detection"],["uecfood256","grocery_store"],["faster_rcnn_food"]),("segmentation_foodseg",["food_segmentation"],["foodseg103","dishseg24k"],["unet_food","deeplab_food","segformer_food","mask2former_food","prompt_segmenter"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("nutrition5k_rgbd",["portion_estimation","nutrition_estimation"],["nutrition5k","usda_fdc_foundation"],["rgbd_multitask_nutrition","component_weight_pipeline","deep_ensemble_nutrition"],Readiness.BLOCKED_VALIDATION,RiskLevel.CLINICAL),("ingredient_parser_benchmark",["ingredient_extraction"],["internal_recipes","recipe1m_plus","synthetic_contract_fixtures"],["ingredient_parser_rules","ingredient_ner"]),("instruction_structuring",["instruction_structuring"],["recipe1m_plus","epic_kitchens"],["instruction_dag_rules"]),("substitution_counterfactual",["substitution","allergen_detection"],["internal_recipes","synthetic_contract_fixtures"],["substitution_graph","graphsage_substitution"],Readiness.RESEARCH_ONLY,RiskLevel.HIGH),("bandit_offline_policy",["bandit_policy"],["internal_feedback"],["linucb","thompson_sampling"],Readiness.BLOCKED_DATA,RiskLevel.HIGH),("continual_personalization",["continual_personalization"],["internal_feedback"],["replay_personalization","adapter_personalization"],Readiness.BLOCKED_DATA,RiskLevel.HIGH),("lca_uncertainty",["sustainability_estimation"],["agribalyse","ecoinvent","water_footprint"],["lca_inventory","monte_carlo_lca"],Readiness.BLOCKED_DATA,RiskLevel.MODERATE),("data_quality_red_team",["data_quality"],["internal_recipes","usda_fdc_foundation","usda_fdc_branded","synthetic_contract_fixtures"],["isolation_forest_quality"],Readiness.RESEARCH_ONLY,RiskLevel.LOW),("privacy_membership",["privacy_audit"],["internal_feedback","synthetic_contract_fixtures"],["privacy_attack_baseline","adapter_personalization"],Readiness.BLOCKED_DATA,RiskLevel.HIGH),("nof1_synthetic_protocol",["n_of_1_analysis"],["synthetic_contract_fixtures"],["bayesian_nof1"],Readiness.RESEARCH_ONLY,RiskLevel.CLINICAL)]
EXPERIMENTS=[_experiment(*row) for row in EXPERIMENT_ROWS]
FEATURE_IDS=["household_profiles","pantry_lots","inventory_ledger","leftover_batches","shopping_reconciliation","batch_prep","family_planning","pareto_explorer","constraint_explanations","fooddata_central","dataset_registry","model_registry","experiment_manifests","offline_baselines","model_cards","dataset_cards","shadow_deployment","drift_monitoring","rollback","pairwise_preferences","safe_bandits","receipt_import","food_photo_correction","structured_generation","substitution_suggestions","data_export_delete"]
IMPLEMENTED={"household_profiles","pantry_lots","inventory_ledger","leftover_batches","shopping_reconciliation","batch_prep","constraint_explanations","dataset_registry","model_registry","experiment_manifests","model_cards","dataset_cards","drift_monitoring","rollback"}
BASELINES={"offline_baselines","substitution_suggestions"}; ADAPTERS={"fooddata_central"}; BLOCKED={"safe_bandits","food_photo_correction","structured_generation"}
FEATURES=[FeatureSpec(id=value,category="research" if value in {"dataset_registry","model_registry","experiment_manifests","offline_baselines","model_cards","dataset_cards","shadow_deployment","drift_monitoring","rollback"} else "product",name=_title(value),readiness=Readiness.IMPLEMENTED if value in IMPLEMENTED else Readiness.BASELINE_AVAILABLE if value in BASELINES else Readiness.ADAPTER_AVAILABLE if value in ADAPTERS else Readiness.BLOCKED_VALIDATION if value in BLOCKED else Readiness.RESEARCH_ONLY,risk=RiskLevel.HIGH if value in {"safe_bandits","food_photo_correction","structured_generation","shadow_deployment"} else RiskLevel.MODERATE) for value in FEATURE_IDS]
CATALOG=ResearchCatalog(version="2026-07-31.3",tasks=TASKS,datasets=DATASETS,models=MODELS,experiments=EXPERIMENTS,features=FEATURES)
def get_catalog()->ResearchCatalog: return CATALOG.model_copy(deep=True)
def get_by_id(collection:str,item_id:str):
    if collection not in {"tasks","datasets","models","experiments","features"}: raise KeyError(collection)
    for item in getattr(CATALOG,collection):
        if item.id==item_id: return item.model_copy(deep=True)
    raise LookupError(item_id)
