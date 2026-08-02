from __future__ import annotations

from scripts.benchmark_preparation_repair import benchmark_report


def test_preparation_repair_benchmark_acceptance():
    report = benchmark_report()
    assert report["document_version"] == "preparation-repair-benchmark-report-v1"
    assert report["deterministic"] is True
    assert report["case_count"] >= 5
    assert report["passed_count"] == report["case_count"]
    assert report["failed_case_ids"] == []


def test_preparation_repair_benchmark_is_deterministic():
    first = benchmark_report()
    second = benchmark_report()
    assert first == second
