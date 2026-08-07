#!/usr/bin/env python3
"""Validate the generated FastAPI OpenAPI document against release contracts."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from backend.main import app


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "contracts" / "openapi_required.json"
DEFAULT_EXTENSIONS = (
    ROOT / "contracts" / "openapi_execution_repair_extension.json",
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
MUTATION_METHODS = {"post", "put", "patch", "delete"}


def _load_contract(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("OpenAPI contract must be a JSON object")
    return raw


def _merge_contract_extensions(
    base: dict[str, Any],
    extension_paths: list[Path],
) -> tuple[dict[str, Any], list[str]]:
    """Merge reviewed additive contract fragments without hiding conflicts."""

    merged = copy.deepcopy(base)
    merged.setdefault("paths", {})
    merged.setdefault("schemas", {})
    versions: list[str] = []
    base_version = str(base.get("contract_version", ""))

    for path in extension_paths:
        extension = _load_contract(path)
        expected_base = str(extension.get("base_contract_version", ""))
        if expected_base != base_version:
            raise ValueError(
                f"OpenAPI extension {path.name} expects base {expected_base}; "
                f"loaded base is {base_version}"
            )
        extension_version = str(extension.get("contract_extension_version", ""))
        if not extension_version:
            raise ValueError(f"OpenAPI extension {path.name} lacks a version")
        versions.append(extension_version)

        for section in ("paths", "schemas"):
            additions = extension.get(section, {})
            if not isinstance(additions, dict):
                raise ValueError(
                    f"OpenAPI extension {path.name} {section} must be an object"
                )
            target = merged[section]
            for key, rule in additions.items():
                if key in target and target[key] != rule:
                    raise ValueError(
                        f"OpenAPI extension {path.name} conflicts on {section}.{key}"
                    )
                target[key] = copy.deepcopy(rule)

    return merged, versions


def _operation_methods(path_value: dict[str, Any]) -> set[str]:
    return {key for key in path_value if key.lower() in HTTP_METHODS}


def _schema_errors(
    schemas: dict[str, Any],
    required_schemas: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for schema_name, rule in sorted(required_schemas.items()):
        observed = schemas.get(schema_name)
        if not isinstance(observed, dict):
            errors.append(f"missing OpenAPI schema: {schema_name}")
            continue

        expected_enum = rule.get("enum")
        if expected_enum is not None:
            if not isinstance(expected_enum, list):
                errors.append(f"contract enum for {schema_name} must be a list")
            elif observed.get("enum") != expected_enum:
                errors.append(
                    f"schema {schema_name} enum drifted: expected {expected_enum}; "
                    f"observed {observed.get('enum')}"
                )

        required_fields = set(rule.get("required", []))
        if not required_fields:
            continue
        properties = observed.get("properties")
        if not isinstance(properties, dict):
            errors.append(f"schema {schema_name} has no properties object")
            continue
        missing_properties = sorted(required_fields - set(properties))
        if missing_properties:
            errors.append(
                f"schema {schema_name} is missing properties: "
                + ", ".join(missing_properties)
            )
        observed_required = set(observed.get("required", []))
        missing_required = sorted(required_fields - observed_required)
        if missing_required:
            errors.append(
                f"schema {schema_name} no longer requires: "
                + ", ".join(missing_required)
            )
    return errors


def validate_openapi_contract(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    extension_paths: list[Path] | None = None,
) -> dict[str, Any]:
    base_contract = _load_contract(contract_path)
    if extension_paths is None:
        extension_paths = list(DEFAULT_EXTENSIONS)
    contract, extension_versions = _merge_contract_extensions(
        base_contract,
        extension_paths,
    )
    document = app.openapi()
    errors: list[str] = []

    observed_version = str(document.get("info", {}).get("version", ""))
    expected_version = str(contract.get("api_version", ""))
    if observed_version != expected_version:
        errors.append(
            f"API version mismatch: expected {expected_version}; observed {observed_version}"
        )

    paths = document.get("paths")
    if not isinstance(paths, dict):
        paths = {}
        errors.append("OpenAPI document has no paths object")

    path_report: dict[str, Any] = {}
    for path, rule in sorted(contract.get("paths", {}).items()):
        observed = paths.get(path)
        if not isinstance(observed, dict):
            errors.append(f"missing required API path: {path}")
            continue
        actual_methods = _operation_methods(observed)
        expected_methods = {str(value).lower() for value in rule.get("methods", [])}
        if actual_methods != expected_methods:
            errors.append(
                f"method drift for {path}: expected {sorted(expected_methods)}; "
                f"observed {sorted(actual_methods)}"
            )
        if rule.get("authenticated"):
            for method in sorted(expected_methods):
                operation = observed.get(method, {})
                security = operation.get("security") if isinstance(operation, dict) else None
                if not isinstance(security, list) or not security:
                    errors.append(
                        f"required authenticated operation lacks security: "
                        f"{method.upper()} {path}"
                    )
        path_report[path] = {
            "expected_methods": sorted(expected_methods),
            "observed_methods": sorted(actual_methods),
        }

    for prefix in contract.get("forbidden_mutation_prefixes", []):
        for path, value in paths.items():
            if path == prefix or path.startswith(f"{prefix}/"):
                methods = _operation_methods(value if isinstance(value, dict) else {})
                forbidden = sorted(methods & MUTATION_METHODS)
                # Exact reviewed conversion is a computation endpoint, not evidence mutation.
                if path.endswith("/convert-reviewed"):
                    forbidden = [method for method in forbidden if method != "post"]
                if forbidden:
                    errors.append(
                        f"global immutable evidence mutation exposed at {path}: "
                        + ", ".join(method.upper() for method in forbidden)
                    )

    schemas = document.get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        schemas = {}
        errors.append("OpenAPI document has no component schemas")
    errors.extend(_schema_errors(schemas, contract.get("schemas", {})))

    security_schemes = document.get("components", {}).get("securitySchemes", {})
    if not isinstance(security_schemes, dict) or not security_schemes:
        errors.append("OpenAPI document has no authentication security scheme")

    return {
        "valid": not errors,
        "contract_version": contract.get("contract_version"),
        "contract_extensions": extension_versions,
        "api_version": observed_version,
        "title": document.get("info", {}).get("title"),
        "path_count": len(paths),
        "schema_count": len(schemas),
        "security_schemes": sorted(security_schemes),
        "required_paths": path_report,
        "required_schemas": sorted(contract.get("schemas", {})),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate generated FastAPI OpenAPI contracts"
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument(
        "--extension",
        action="append",
        type=Path,
        dest="extensions",
        help=(
            "Additive OpenAPI contract extension. Defaults to the reviewed "
            "execution-repair extension when omitted."
        ),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = validate_openapi_contract(
            contract_path=args.contract,
            extension_paths=args.extensions,
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"OpenAPI contract validation failed: {type(exc).__name__}: {exc}")
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
