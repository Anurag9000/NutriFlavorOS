#!/usr/bin/env python3
"""Validate handwritten frontend API bindings against generated FastAPI OpenAPI."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from backend.main import app


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "contracts" / "frontend_openapi_bindings.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Frontend OpenAPI binding contract must be a JSON object")
    return value


def _extract_braced_block(source: str, marker: str) -> str:
    start = source.find(marker)
    if start < 0:
        raise ValueError(f"TypeScript declaration not found: {marker}")
    open_brace = source.find("{", start + len(marker))
    if open_brace < 0:
        raise ValueError(f"TypeScript declaration has no opening brace: {marker}")
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(open_brace, len(source)):
        char = source[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'", "`"}:
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace + 1 : index]
    raise ValueError(f"Unclosed TypeScript declaration: {marker}")


def _interface_fields(source: str, name: str) -> dict[str, bool]:
    block = _extract_braced_block(source, f"export interface {name}")
    result: dict[str, bool] = {}
    for line in block.splitlines():
        match = re.match(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)(\?)?\s*:", line)
        if match:
            result[match.group(1)] = bool(match.group(2))
    if not result:
        raise ValueError(f"No TypeScript properties parsed from interface {name}")
    return result


def _type_union_values(source: str, name: str) -> set[str]:
    match = re.search(
        rf"export\s+type\s+{re.escape(name)}\s*=\s*(.*?);",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError(f"TypeScript union not found: {name}")
    values = set(re.findall(r"[\"']([^\"']+)[\"']", match.group(1)))
    if not values:
        raise ValueError(f"TypeScript union contains no string literals: {name}")
    return values


def _binding_block(object_source: str, name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}\s*:",
        object_source,
        flags=re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"Frontend API binding not found: {name}")
    start = match.start()
    next_binding = re.search(
        r"^  [A-Za-z_][A-Za-z0-9_]*\s*:",
        object_source[match.end() :],
        flags=re.MULTILINE,
    )
    end = (
        match.end() + next_binding.start()
        if next_binding is not None
        else len(object_source)
    )
    return object_source[start:end]


def _enum_from_openapi(schema: dict[str, Any]) -> set[str]:
    direct = schema.get("enum")
    if isinstance(direct, list):
        return {str(value) for value in direct}
    for branch in schema.get("anyOf", []):
        if isinstance(branch, dict) and isinstance(branch.get("enum"), list):
            return {str(value) for value in branch["enum"]}
    return set()


def validate_frontend_openapi_bindings(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    contract = _load(contract_path)
    source_path = ROOT / str(contract["typescript_source"])
    source = source_path.read_text(encoding="utf-8")
    document = app.openapi()
    schemas = document.get("components", {}).get("schemas", {})
    paths = document.get("paths", {})
    errors: list[str] = []
    permissive_optional_fields: dict[str, list[str]] = {}
    schema_report: dict[str, Any] = {}

    for openapi_name, typescript_name in sorted(contract.get("schemas", {}).items()):
        schema = schemas.get(openapi_name)
        if not isinstance(schema, dict):
            errors.append(f"OpenAPI schema is missing: {openapi_name}")
            continue
        try:
            fields = _interface_fields(source, str(typescript_name))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        observed = set(fields)
        expected = set(properties)
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        if missing:
            errors.append(
                f"TypeScript interface {typescript_name} is missing OpenAPI fields: "
                + ", ".join(missing)
            )
        if extra:
            errors.append(
                f"TypeScript interface {typescript_name} has fields absent from OpenAPI: "
                + ", ".join(extra)
            )
        required = set(schema.get("required", []))
        permissive = sorted(name for name in required if fields.get(name) is True)
        if permissive:
            permissive_optional_fields[str(typescript_name)] = permissive
        schema_report[openapi_name] = {
            "typescript_interface": typescript_name,
            "openapi_property_count": len(expected),
            "typescript_property_count": len(observed),
            "missing": missing,
            "extra": extra,
            "frontend_optional_for_required": permissive,
        }

    enum_report: dict[str, Any] = {}
    for openapi_name, typescript_name in sorted(contract.get("enums", {}).items()):
        schema = schemas.get(openapi_name)
        if not isinstance(schema, dict):
            errors.append(f"OpenAPI enum schema is missing: {openapi_name}")
            continue
        expected = _enum_from_openapi(schema)
        try:
            observed = _type_union_values(source, str(typescript_name))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if expected != observed:
            errors.append(
                f"TypeScript union {typescript_name} differs from OpenAPI enum {openapi_name}: "
                f"expected {sorted(expected)}; observed {sorted(observed)}"
            )
        enum_report[openapi_name] = {
            "typescript_type": typescript_name,
            "expected": sorted(expected),
            "observed": sorted(observed),
        }

    object_blocks: dict[str, str] = {}
    operation_report: list[dict[str, Any]] = []
    for operation in contract.get("operations", []):
        path = str(operation["openapi_path"])
        method = str(operation["method"]).lower()
        object_name = str(operation["object"])
        binding = str(operation["binding"])
        fragment = str(operation["source_fragment"])
        path_value = paths.get(path)
        actual_methods = (
            {
                key.lower()
                for key in path_value
                if key.lower() in HTTP_METHODS
            }
            if isinstance(path_value, dict)
            else set()
        )
        if method not in actual_methods:
            errors.append(f"OpenAPI operation is missing: {method.upper()} {path}")
        try:
            object_block = object_blocks.setdefault(
                object_name,
                _extract_braced_block(source, f"export const {object_name} ="),
            )
            block = _binding_block(object_block, binding)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if fragment not in block:
            errors.append(
                f"Frontend binding {object_name}.{binding} does not contain declared route fragment: {fragment}"
            )
        method_match = re.search(
            r"method\s*:\s*[\"']([A-Za-z]+)[\"']",
            block,
        )
        observed_method = method_match.group(1).lower() if method_match else "get"
        if observed_method != method:
            errors.append(
                f"Frontend binding {object_name}.{binding} method drift: expected {method}; observed {observed_method}"
            )
        operation_report.append(
            {
                "path": path,
                "object": object_name,
                "binding": binding,
                "expected_method": method,
                "observed_method": observed_method,
                "route_fragment_present": fragment in block,
            }
        )

    return {
        "valid": not errors,
        "contract_version": contract.get("contract_version"),
        "openapi_version": document.get("info", {}).get("version"),
        "typescript_source": str(source_path.relative_to(ROOT)),
        "schemas": schema_report,
        "enums": enum_report,
        "operations": operation_report,
        "permissive_optional_fields": permissive_optional_fields,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate TypeScript API bindings against generated OpenAPI"
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = validate_frontend_openapi_bindings(contract_path=args.contract)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Frontend OpenAPI binding validation failed: {type(exc).__name__}: {exc}")
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
