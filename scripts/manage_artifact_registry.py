"""Offline CLI for dataset/model cards and integrity-gated artifact promotion."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from backend.research.cards import build_dataset_card,build_model_card
from backend.research.registry import LocalArtifactRegistry,RegistryStage
def _json_object(path:Path)->dict:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise ValueError(f"Expected a JSON object in {path}")
    return value
def main()->None:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--registry-root",type=Path,default=Path("reports/registry")); subs=parser.add_subparsers(dest="command",required=True)
    dataset=subs.add_parser("register-dataset"); dataset.add_argument("dataset_id"); dataset.add_argument("version"); dataset.add_argument("--artifact",type=Path)
    model=subs.add_parser("register-model"); model.add_argument("model_id"); model.add_argument("version"); model.add_argument("artifact",type=Path)
    promote=subs.add_parser("promote"); promote.add_argument("model_id"); promote.add_argument("version"); promote.add_argument("stage",choices=[RegistryStage.CANDIDATE.value,RegistryStage.CHAMPION.value]); promote.add_argument("gate_results",type=Path); promote.add_argument("--evaluation",type=Path)
    verify=subs.add_parser("verify"); verify.add_argument("kind",choices=["dataset","model"]); verify.add_argument("item_id"); verify.add_argument("version"); subs.add_parser("list")
    args=parser.parse_args(); registry=LocalArtifactRegistry(args.registry_root)
    if args.command=="register-dataset": print(registry.register_dataset(build_dataset_card(args.dataset_id,version=args.version),args.artifact).model_dump_json(indent=2))
    elif args.command=="register-model": print(registry.register_model(build_model_card(args.model_id,version=args.version),args.artifact).model_dump_json(indent=2))
    elif args.command=="promote": print(registry.promote(args.model_id,args.version,target_stage=RegistryStage(args.stage),gate_results={key:bool(value) for key,value in _json_object(args.gate_results).items()},evaluation=_json_object(args.evaluation) if args.evaluation else None).model_dump_json(indent=2))
    elif args.command=="verify":
        entry=registry.get(args.kind,args.item_id,args.version); print(json.dumps({"entry":entry.key,"integrity_ok":registry.verify_integrity(entry)},indent=2))
    else: print(json.dumps([entry.model_dump(mode="json") for entry in registry.list()],indent=2))
if __name__=="__main__": main()
