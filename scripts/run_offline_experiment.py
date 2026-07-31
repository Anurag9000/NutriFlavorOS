#!/usr/bin/env python3
"""Run whitelisted deterministic offline baselines and emit a manifest.

The runner never imports a class from user input and never executes arbitrary
code. Potential user-owned data requires explicit consent flags.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any,Dict,List
from backend.research.baselines import CrostonForecaster,MovingAverageForecaster,RidgeRegressor,TfidfRetriever
from backend.research.catalog import get_catalog
from backend.research.evaluation import mae,ndcg_at_k,recall_at_k,reciprocal_rank,r2,rmse,wape
from backend.research.manifest import ExperimentRunConfig,artifact_entry,create_manifest,fingerprint_file,fingerprint_json,seed_everything
ROOT=Path(__file__).resolve().parents[1]
SAFE_DATA_ROOTS=[ROOT/"backend"/"data",ROOT/"reports"/"fixtures",ROOT/"backend"/"tests"/"fixtures"]
SUPPORTED_BASELINES={"catalog_validation","tfidf_retriever","moving_average","croston","ridge_regression"}
def _read_json(path:Path)->Any:
    with path.open("r",encoding="utf-8") as handle: return json.load(handle)
def _resolve_dataset(path_value:str|None,allow_external_path:bool)->Path|None:
    if path_value is None:return None
    path=Path(path_value); path=path if path.is_absolute() else ROOT/path; resolved=path.resolve()
    if not resolved.is_file(): raise FileNotFoundError(resolved)
    if not allow_external_path and not any(root.resolve()==resolved or root.resolve() in resolved.parents for root in SAFE_DATA_ROOTS): raise ValueError("Dataset path is outside approved fixture/data directories; use --allow-external-path explicitly")
    return resolved
def _run_tfidf(payload:Dict[str,Any],parameters:Dict[str,Any])->Dict[str,Any]:
    documents,queries=payload.get("documents"),payload.get("queries")
    if not isinstance(documents,list) or not isinstance(queries,list): raise ValueError("TF-IDF dataset requires documents and queries lists")
    retriever=TfidfRetriever().fit((str(item["id"]),str(item["text"])) for item in documents if isinstance(item,dict) and "id" in item and "text" in item); k=min(max(int(parameters.get("k",10)),1),100); recalls=[]; reciprocal=[]; ndcgs=[]; results=[]
    for query in queries:
        if not isinstance(query,dict): continue
        ranked=retriever.rank(str(query.get("text","")),k=k); ids=[item.item_id for item in ranked]; relevant=[str(value) for value in query.get("relevant_ids",[])]; graded={str(key):float(value) for key,value in (query.get("relevance",{}) or {}).items()}; recalls.append(recall_at_k(relevant,ids,k)); reciprocal.append(reciprocal_rank(relevant,ids)); ndcgs.append(ndcg_at_k(graded or {item:1.0 for item in relevant},ids,k)); results.append({"query_id":query.get("id"),"ranked":[item.__dict__ for item in ranked]})
    if not results: raise ValueError("No valid queries were found")
    return {"metrics":{f"recall@{k}":sum(recalls)/len(recalls),"mrr":sum(reciprocal)/len(reciprocal),f"ndcg@{k}":sum(ndcgs)/len(ndcgs),"queries":len(results)},"predictions":results,"warnings":[]}
def _run_forecast(payload:Dict[str,Any],baseline:str,parameters:Dict[str,Any])->Dict[str,Any]:
    train=[float(value) for value in payload.get("train",[])]; test=[float(value) for value in payload.get("test",[])]
    if not train or not test: raise ValueError("Forecast dataset requires non-empty train and test arrays")
    model=MovingAverageForecaster(window=int(parameters.get("window",4))).fit(train) if baseline=="moving_average" else CrostonForecaster(alpha=float(parameters.get("alpha",0.1))).fit(train); predicted=model.predict(len(test)); return {"metrics":{"mae":mae(test,predicted),"rmse":rmse(test,predicted),"wape":wape(test,predicted)},"predictions":predicted,"warnings":[]}
def _run_ridge(payload:Dict[str,Any],parameters:Dict[str,Any])->Dict[str,Any]:
    train_x,train_y,test_x,test_y=(payload.get(key) for key in ("train_x","train_y","test_x","test_y"))
    if not all(isinstance(value,list) and value for value in (train_x,train_y,test_x,test_y)): raise ValueError("Ridge dataset requires train_x, train_y, test_x, and test_y")
    model=RidgeRegressor(alpha=float(parameters.get("alpha",1.0))).fit(train_x,train_y); predicted=model.predict(test_x); return {"metrics":{"mae":mae(test_y,predicted),"rmse":rmse(test_y,predicted),"r2":r2(test_y,predicted)},"predictions":predicted,"model":{"coef":model.coef_.tolist(),"intercept":model.intercept_},"warnings":[]}
def run(config:ExperimentRunConfig,*,allow_external_path:bool=False)->Path:
    if config.baseline not in SUPPORTED_BASELINES: raise ValueError(f"Unsupported baseline: {config.baseline}")
    seed_everything(config.seed); manifest=create_manifest(config); dataset_path=_resolve_dataset(config.dataset_path,allow_external_path); payload={}
    if dataset_path is not None:
        payload=_read_json(dataset_path)
        if not isinstance(payload,dict): raise ValueError("Dataset root must be a JSON object")
        manifest.dataset_fingerprint=fingerprint_file(dataset_path)
    if config.baseline=="catalog_validation": result={"metrics":get_catalog().summary(),"warnings":[]}
    elif config.baseline=="tfidf_retriever": result=_run_tfidf(payload,config.parameters)
    elif config.baseline in {"moving_average","croston"}: result=_run_forecast(payload,config.baseline,config.parameters)
    else: result=_run_ridge(payload,config.parameters)
    manifest.status="completed"; manifest.metrics=result["metrics"]; manifest.warnings.extend(result.get("warnings",[])); manifest.model_fingerprint=fingerprint_json({"baseline":config.baseline,"parameters":config.parameters,"implementation":"nfos-offline-v1"})
    output_dir=ROOT/"reports"/"experiments"/manifest.run_id; output_dir.mkdir(parents=True,exist_ok=False); predictions=output_dir/"predictions.json"; predictions.write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8"); manifest.artifacts.append(artifact_entry(predictions,root=ROOT,media_type="application/json")); manifest_path=output_dir/"manifest.json"; manifest_path.write_text(manifest.model_dump_json(indent=2),encoding="utf-8"); return manifest_path
def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--config",required=True); parser.add_argument("--allow-external-path",action="store_true"); args=parser.parse_args(); output=run(ExperimentRunConfig.model_validate(_read_json(Path(args.config))),allow_external_path=args.allow_external_path); print(output); return 0
if __name__=="__main__": raise SystemExit(main())
