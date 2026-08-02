#!/usr/bin/env python3
"""Synchronize current 0.12.1 documents for structured operations review."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(
            f"Unexpected synchronization anchor in {path.relative_to(ROOT)}: {old[:80]!r}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def remove_regex_once(path: Path, pattern: str, replacement: str = "") -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count == 0:
        if replacement and replacement.strip() in text:
            return
        if not replacement and not re.search(pattern, text, flags=re.DOTALL):
            return
        raise RuntimeError(f"Synchronization pattern failed in {path.relative_to(ROOT)}")
    path.write_text(updated, encoding="utf-8")


def readme() -> None:
    path = ROOT / "README.md"
    replace_once(
        path,
        "- structured calendar builder at `/preparation/operations/calendars/new`;\n",
        "- structured calendar builder at `/preparation/operations/calendars/new`;\n"
        "- structured final persistence review with exact source, occurrence, profile, calendar, task-DAG, deterministic-output, and confirmation surfaces;\n",
    )
    replace_once(
        path,
        "- Raw schedule-bundle JSON still needs a fully structured final persistence-review replacement.\n",
        "- Structured final persistence review is implemented; canonical bundle JSON is read-only and optional for expert inspection.\n",
    )


def status() -> None:
    path = ROOT / "docs" / "IMPLEMENTATION_STATUS.md"
    replace_once(
        path,
        "- Protected operations and coverage workspaces.\n",
        "- Protected operations and coverage workspaces.\n"
        "- Structured final persistence review with exact source-plan, occurrence/hash, profile, calendar/hash, task-DAG, deterministic-output, read-only JSON, four confirmations, and explicit draft persistence.\n",
    )
    replace_once(path, "- Structured final persistence review replacing raw expert JSON editing.\n", "")
    replace_once(
        path,
        "- Dashboard, planner, household/pantry, plan review, occurrence confirmation, analytics, settings, preparation editor, reviewed pipeline, operations, task execution, calendar builder, combined provenance/execution coverage, and research views.\n",
        "- Dashboard, planner, household/pantry, plan review, occurrence confirmation, analytics, settings, preparation editor, reviewed pipeline, structured operations review, task execution, calendar builder, combined provenance/execution coverage, and research views.\n",
    )
    replace_once(
        path,
        "- Structured final persistence review, authenticated Playwright/PostgreSQL journeys, automated axe, keyboard-only/screen-reader suites, visual regression, offline/PWA policy, and internationalization.\n",
        "- Authenticated Playwright/PostgreSQL journeys, automated axe, keyboard-only/screen-reader suites, visual regression, offline/PWA policy, and internationalization.\n",
    )
    old = (
        "## Immediate priorities\n\n"
        "1. Inspect and close the exact latest hosted workflows.\n"
        "2. Migrate remaining low-level completion callers to the task terminality guard.\n"
        "3. Replace raw schedule-bundle JSON with structured final persistence review.\n"
        "4. Add authenticated Playwright/PostgreSQL and automated accessibility coverage.\n"
        "5. Add deterministic minimal-change plan/schedule repair with explicit human acceptance.\n"
        "6. Expand reviewed evidence and cross-domain coverage.\n"
        "7. Expand forecasting uncertainty, stochastic inventory costs, ranking robustness, identity lifecycle, backups, observability, SLOs, and incident evidence.\n"
    )
    new = (
        "## Immediate priorities\n\n"
        "1. Inspect and close the exact latest hosted workflows.\n"
        "2. Migrate remaining low-level completion callers to the task terminality guard.\n"
        "3. Add authenticated Playwright/PostgreSQL and automated accessibility coverage.\n"
        "4. Add deterministic minimal-change plan/schedule repair with explicit human acceptance.\n"
        "5. Expand reviewed evidence and cross-domain coverage.\n"
        "6. Expand forecasting uncertainty, stochastic inventory costs, ranking robustness, identity lifecycle, backups, observability, SLOs, and incident evidence.\n"
    )
    replace_once(path, old, new)


def roadmap() -> None:
    path = ROOT / "docs" / "ROADMAP.md"
    replace_once(
        path,
        "## C10 — Forecasting, ranking, and inventory evaluation\n",
        "## C10 — Structured final operations persistence review\n\n"
        "Exact plan/version, occurrence document/hash, profile identities, active reviewed calendar/hash, task DAG, durations, demands, deadlines, deterministic scheduled output, unresolved-work blocking, read-only canonical JSON, four confirmations, role controls, retry-stable idempotency, and explicit draft persistence are implemented. Approval and task execution remain separate actions.\n\n"
        "## C11 — Forecasting, ranking, and inventory evaluation\n",
    )
    replace_once(path, "## C11 — Release governance\n", "## C12 — Release governance\n")
    remove_regex_once(
        path,
        r"## P1\.1 Structured final persistence review — next product slice\n.*?(?=## P1\.2 Browser E2E and accessibility)",
    )
    replace_once(path, "## P1.2 Browser E2E and accessibility\n", "## P1.1 Browser E2E and accessibility\n")
    replace_once(path, "## P1.3 Local timers/reminders without inference\n", "## P1.2 Local timers/reminders without inference\n")
    replace_once(path, "## P1.4 Joint minimal-change repair\n", "## P1.3 Joint minimal-change repair\n")
    old = (
        "# Immediate execution order\n\n"
        "1. Inspect and close the exact latest hosted workflows.\n"
        "2. Migrate low-level completion callers and make terminality authoritative.\n"
        "3. Build structured final persistence review.\n"
        "4. Add authenticated E2E and accessibility coverage.\n"
        "5. Add deterministic minimal-change repair.\n"
        "6. Expand reviewed evidence and cross-domain coverage.\n"
        "7. Continue forecasting, inventory, ranking, security, and reliability hardening.\n"
    )
    new = (
        "# Immediate execution order\n\n"
        "1. Inspect and close the exact latest hosted workflows.\n"
        "2. Migrate low-level completion callers and make terminality authoritative.\n"
        "3. Add authenticated E2E and accessibility coverage.\n"
        "4. Add deterministic minimal-change repair.\n"
        "5. Expand reviewed evidence and cross-domain coverage.\n"
        "6. Continue forecasting, inventory, ranking, security, and reliability hardening.\n"
    )
    replace_once(path, old, new)


def operations_spec() -> None:
    path = ROOT / "docs" / "PREPARATION_OPERATIONS.md"
    marker = "## Append-only task execution ledger\n"
    section = (
        "## Structured final persistence review\n\n"
        "The routed `/preparation/operations` page consumes `preparation-operations-handoff-v2` once and presents exact plan, occurrence/hash, profile, active reviewed calendar/hash, task-DAG, demand, deadline, and deterministic schedule content structurally. It performs no persistence on load.\n\n"
        "Persistence requires four independent confirmations covering source/occurrence/profile evidence, calendar/resource evidence, task/schedule evidence, and the non-execution/non-safety boundary. Canonical JSON remains available only as read-only expert inspection. Extra profile recipes, unresolved tasks, task-ID mismatch, unknown dependencies, calendar drift, horizon drift, or resource-ID drift block the browser action; server replay remains authoritative.\n\n"
        "Editor/owner persistence creates a draft only. Owner approval, task execution, and completion remain separate actions.\n\n"
    )
    replace_once(path, marker, section + marker)
    replace_once(
        path,
        "- Structured final persistence review, timers/reminders, minimal-change repair, and joint optimization remain incomplete.\n",
        "- Timers/reminders, minimal-change repair, and joint optimization remain incomplete.\n",
    )


def subsystem_specs() -> None:
    replace_once(
        ROOT / "docs" / "APPROVED_PLAN_PREPARATION.md",
        "- Structured final persistence review still exposes expert JSON and remains incomplete.\n",
        "- Structured final persistence review is implemented; canonical expert JSON is read-only and optional.\n",
    )
    replace_once(
        ROOT / "docs" / "HOUSEHOLD_PLAN_LIFECYCLE.md",
        "- Structured final persistence review, authenticated browser E2E, minimal-change repair, and joint optimization remain incomplete.\n",
        "- Authenticated browser E2E, minimal-change repair, and joint optimization remain incomplete.\n",
    )


def main() -> int:
    readme()
    status()
    roadmap()
    operations_spec()
    subsystem_specs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
