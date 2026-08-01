import { beforeEach, describe, expect, it } from "vitest";

import {
  buildPreparationOperationsHandoff,
  canonicalJson,
  consumePreparationOperationsHandoff,
  PREPARATION_OPERATIONS_HANDOFF_KEY,
  sha256Hex,
  storePreparationOperationsHandoff,
} from "@/lib/preparationOperationsHandoff";

const calendar = {
  id: 7,
  household_id: "household-1",
  calendar_version: "calendar-v1",
  horizon_minutes: 240,
  timezone: "UTC",
  evidence_status: "reviewed" as const,
  reviewed_at: "2026-08-01T00:00:00Z",
  reviewed_by: "Reviewer",
  notes: null,
  content_hash: "a".repeat(64),
  supersedes_calendar_id: null,
  active: true,
  created_by_user_id: "owner@example.test",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  resources: [
    {
      id: 11,
      calendar_version_id: 7,
      resource_id: "person",
      label: "Available cook",
      capacity: 1,
      resource_kind: "person",
      availability_windows: [
        { start_minute: 0, end_minute: 60 },
        { start_minute: 90, end_minute: 240 },
      ],
      metadata: {},
    },
  ],
};

const compileRequest = {
  occurrences: [
    {
      occurrence_id: "day1.dinner",
      recipe_id: "reviewed-soup",
      required_finish_minute: 180,
      servings: 4,
      priority: 3,
    },
  ],
  duration_policy: "conservative_max" as const,
  reviewed_only: true,
  allow_partial: false,
  horizon_minutes: 240,
  granularity_minutes: 5,
  resources: [
    {
      resource_id: "person",
      label: "Available cook",
      capacity: 1,
      availability_windows: [
        { start_minute: 0, end_minute: 60 },
        { start_minute: 90, end_minute: 240 },
      ],
    },
  ],
};

const compileResponse = {
  compilation: {
    tasks: [
      {
        task_id: "day1.dinner.prepare",
        duration_minutes: 20,
        earliest_start_minute: 90,
        latest_finish_minute: 180,
        priority: 3,
        resource_demands: { person: 1 },
        dependencies: [],
        metadata: { profile_content_hash: "b".repeat(64) },
      },
    ],
    unresolved: [],
    profile_versions: {
      "reviewed-soup": `profile:1/version:2/sha256:${"b".repeat(64)}`,
    },
    duration_policy: "conservative_max" as const,
    warnings: [],
  },
  schedule: {
    method: "deterministic_dependency_aware_resource_scheduler_v3_multi_window",
    deterministic: true,
    horizon_minutes: 240,
    granularity_minutes: 5,
    scheduled: [
      {
        task_id: "day1.dinner.prepare",
        start_minute: 90,
        finish_minute: 110,
        duration_minutes: 20,
        priority: 3,
        resource_demands: { person: 1 },
        dependencies: [],
        metadata: { profile_content_hash: "b".repeat(64) },
      },
    ],
    unscheduled: [],
    resource_utilization: { person: 20 / 210 },
    resource_peak_usage: { person: 1 },
    makespan_minutes: 110,
    diagnostics: {},
  },
  partial: false,
  execution_status: "scheduled" as const,
};

beforeEach(() => {
  sessionStorage.clear();
});

describe("Preparation operations handoff", () => {
  it("canonicalizes object keys and hashes equivalent documents identically", async () => {
    expect(canonicalJson({ b: 2, a: { d: 4, c: 3 } })).toBe(
      canonicalJson({ a: { c: 3, d: 4 }, b: 2 }),
    );
    expect(await sha256Hex({ b: 2, a: 1 })).toBe(
      await sha256Hex({ a: 1, b: 2 }),
    );
  });

  it("builds a complete multi-window replay bundle", async () => {
    const handoff = await buildPreparationOperationsHandoff({
      householdId: "household-1",
      calendar,
      compileRequest,
      compileResponse,
      occurrenceSetVersion: "occurrences-v1",
      notes: "Reviewed handoff",
    });

    expect(handoff.bundle.calendar_version_id).toBe(calendar.id);
    expect(handoff.bundle.occurrence_set_hash).toMatch(/^[a-f0-9]{64}$/);
    expect(handoff.bundle.schedule_request.resources[0].availability_windows).toEqual(
      calendar.resources[0].availability_windows,
    );
    expect(handoff.bundle.schedule_request.tasks[0].metadata).toEqual({
      profile_content_hash: "b".repeat(64),
    });
    expect(handoff.bundle.schedule_response).toEqual(compileResponse.schedule);
    expect(handoff.bundle.profile_versions).toEqual(
      compileResponse.compilation.profile_versions,
    );
  });

  it("rejects partial or unresolved pipeline output", async () => {
    await expect(
      buildPreparationOperationsHandoff({
        householdId: "household-1",
        calendar,
        compileRequest: { ...compileRequest, allow_partial: true },
        compileResponse: { ...compileResponse, partial: true },
        occurrenceSetVersion: "occurrences-v1",
      }),
    ).rejects.toThrow(/complete fail-closed|partial/i);
  });

  it("stores and consumes a handoff exactly once", async () => {
    const handoff = await buildPreparationOperationsHandoff({
      householdId: "household-1",
      calendar,
      compileRequest,
      compileResponse,
      occurrenceSetVersion: "occurrences-v1",
    });
    storePreparationOperationsHandoff(handoff);
    expect(sessionStorage.getItem(PREPARATION_OPERATIONS_HANDOFF_KEY)).not.toBeNull();
    expect(consumePreparationOperationsHandoff()).toEqual(handoff);
    expect(consumePreparationOperationsHandoff()).toBeNull();
  });
});
