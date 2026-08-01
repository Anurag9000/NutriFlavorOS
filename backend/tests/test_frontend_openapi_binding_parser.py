from __future__ import annotations

import re

from scripts.validate_frontend_openapi_bindings import (
    _binding_block,
    _extract_braced_block,
    _interface_fields,
    _type_union_values,
)


def test_parser_extracts_interface_properties_and_optionality():
    source = """
export interface ExampleView {
  id: number;
  reviewed_at?: string | null;
  metadata: Record<string, unknown>;
}
"""
    assert _interface_fields(source, "ExampleView") == {
        "id": False,
        "reviewed_at": True,
        "metadata": False,
    }


def test_parser_extracts_multiline_string_union():
    source = """
export type EvidenceState =
  | "reviewed"
  | 'rejected'
  | "legacy_unreviewed";
"""
    assert _type_union_values(source, "EvidenceState") == {
        "reviewed",
        "rejected",
        "legacy_unreviewed",
    }


def test_object_scoping_disambiguates_duplicate_binding_names():
    source = """
export const legacyApi = {
  storagePolicies: () => request(`/food-evidence/storage-policies`),
};

export const evidenceHistoryApi = {
  storagePolicies: (options = {}) => {
    const params = new URLSearchParams();
    return request(`/food-evidence/history/storage-policies?${params.toString()}`);
  },
  convertReviewed: (payload) => request(
    "/food-evidence/history/convert-reviewed",
    { method: "POST", body: JSON.stringify(payload) },
  ),
};
"""
    legacy = _extract_braced_block(source, "export const legacyApi =")
    history = _extract_braced_block(source, "export const evidenceHistoryApi =")
    assert "/food-evidence/storage-policies" in _binding_block(
        legacy,
        "storagePolicies",
    )
    history_block = _binding_block(history, "storagePolicies")
    assert "/food-evidence/history/storage-policies" in history_block
    assert "/food-evidence/storage-policies`" not in history_block

    conversion = _binding_block(history, "convertReviewed")
    method = re.search(r"method\s*:\s*[\"']([A-Za-z]+)[\"']", conversion)
    assert method is not None
    assert method.group(1).lower() == "post"


def test_brace_parser_ignores_template_expression_braces():
    source = """
export const api = {
  lifecycleEvents: (options = {}) => {
    const params = new URLSearchParams();
    return request(`/history/${options.kind ?? "all"}?${params.toString()}`);
  },
  next: () => request("/next"),
};
"""
    block = _extract_braced_block(source, "export const api =")
    lifecycle = _binding_block(block, "lifecycleEvents")
    assert "params.toString()" in lifecycle
    assert "next:" not in lifecycle
