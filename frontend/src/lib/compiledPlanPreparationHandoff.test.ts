import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildCompiledPlanPreparationHandoff,
  storeCompiledPlanPreparationHandoff,
} from "@/lib/compiledPlanPreparationHandoff";
import type {
  ApprovedPlanPreparationCompileView,
} from "@/lib/householdPlanApi";

const mocks = vi.hoisted(() => ({
  storePreparationOperationsHandoff: vi.fn(),
}));

vi.mock("@/lib/preparationOperationsHandoff", () => ({
  storePreparationOperationsHandoff:
    mocks.storePreparationOperationsHandoff,
}));

function compiled(): ApprovedPlanPreparationCompileView {
  return {
    household_id: "home-1",
    source_plan_id: 42,
    source_plan_version: 2,
    calendar_version_id: 7,
    calendar_version: "calendar-v1",
    calendar_content_hash: "b".repeat(64),
    occurrence_set: {
      document_version: "preparation-occurrence-set-v1",
      household_id: "home-1",
      occurrence_set_version: "plan-42-v2-occurrences-v1",
      duration_policy: "conservative_max",
      occurrences: [
        {
          occurrence_id: "day-1.dinner",
          recipe_id: "recipe-1",
          required_finish_minute: 180,
          servings: 2,
          priority: 3,
        },
      ],
    },
    profile_versions: {
      "recipe-1": `profile:7/version:v1/sha256:${"a".repeat(64)}`,
    },
    schedule_request: {
      horizon_minutes: 240,
      granularity_minutes: 5,
      resources: [
        {
          resource_id: "person",
          capacity: 1,
          availability_windows: [
            { start_minute: 0, end_minute: 240 },
          ],
          label: "Available cook",
        },
      ],
      tasks: [
        {
          task_id: "day-1.dinner:prep",
          duration_minutes: 15,
          earliest_start_minute: 0,
          latest_finish_minute: 180,
          priority: 3,
          resource_demands: { person: 1 },
          dependencies: [],
          metadata: {
            occurrence_id: "day-1.dinner",
            recipe_id: "recipe-1",
            servings: 2,
            profile_id: 7,
            profile_version: "v1",
            profile_content_hash: "a".repeat(64),
            duration_min_minutes: 10,
            duration_max_minutes: 15,
            duration_policy: "conservative_max",
            template_id: "prep",
          },
        },
      ],
    },
    schedule_response: {
      method: "deterministic_dependency_aware_resource_scheduler_v2",
      deterministic: true,
      horizon_minutes: 240,
      granularity_minutes: 5,
      scheduled: [
        {
          task_id: "day-1.dinner:prep",
          start_minute: 0,
          finish_minute: 15,
          duration_minutes: 15,
          priority: 3,
          resource_demands: { person: 1 },
          dependencies: [],
          metadata: {
            occurrence_id: "day-1.dinner",
            recipe_id: "recipe-1",
          },
        },
      ],
      unscheduled: [],
      resource_utilization: { person: 0.0625 },
      resource_peak_usage: { person: 1 },
      makespan_minutes: 15,
      diagnostics: {},
    },
    partial: false,
    execution_status: "complete",
    warnings: [],
  };
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("compiled approved-plan preparation handoff", () => {
  it("builds an exact operations v2 bundle with a canonical occurrence hash", async () => {
    const value = await buildCompiledPlanPreparationHandoff(
      compiled(),
      "2026-08-02T10:00:00.000Z",
    );

    expect(value.document_version).toBe("preparation-operations-handoff-v2");
    expect(value.household_id).toBe("home-1");
    expect(value.created_at).toBe("2026-08-02T10:00:00.000Z");
    expect(value.occurrence_set_hash_preview).toMatch(/^[a-f0-9]{64}$/);
    expect(value.bundle.calendar_version_id).toBe(7);
    expect(value.bundle.source_plan_id).toBe(42);
    expect(value.bundle.source_plan_version).toBe(2);
    expect(value.bundle.occurrence_set).toEqual(compiled().occurrence_set);
    expect(value.bundle.profile_versions).toEqual(compiled().profile_versions);
    expect(value.bundle.schedule_request).toEqual(compiled().schedule_request);
    expect(value.bundle.schedule_response).toEqual(compiled().schedule_response);
    expect(value.bundle.notes).toContain("Approved plan #42 version 2");
    expect(value.bundle.notes).toContain("calendar-v1");
  });

  it("uses the canonical operations writer only after a complete build", async () => {
    const value = await storeCompiledPlanPreparationHandoff(compiled());

    expect(mocks.storePreparationOperationsHandoff).toHaveBeenCalledTimes(1);
    expect(mocks.storePreparationOperationsHandoff).toHaveBeenCalledWith(
      value,
      sessionStorage,
    );
  });

  it("rejects partial or unscheduled output", async () => {
    const partial = compiled();
    partial.partial = true;
    partial.execution_status = "partial_unscheduled";
    partial.schedule_response.unscheduled = [
      {
        task_id: "day-1.dinner:prep",
        reason_code: "missing_resource",
        message: "Required resource is missing",
        missing_resources: ["person"],
        blocked_by: [],
        capacity_violations: {},
        metadata: {},
      },
    ];
    partial.schedule_response.scheduled = [];

    await expect(buildCompiledPlanPreparationHandoff(partial)).rejects.toThrow(
      /partial or unscheduled/i,
    );
    expect(mocks.storePreparationOperationsHandoff).not.toHaveBeenCalled();
  });

  it("rejects empty, incomplete, and inconsistent compilations", async () => {
    const empty = compiled();
    empty.schedule_request.tasks = [];
    empty.schedule_response.scheduled = [];
    await expect(buildCompiledPlanPreparationHandoff(empty)).rejects.toThrow(
      /contains no tasks/i,
    );

    const missingTask = compiled();
    missingTask.schedule_response.scheduled = [];
    await expect(
      buildCompiledPlanPreparationHandoff(missingTask),
    ).rejects.toThrow(/every compiled preparation task/i);

    const wrongHousehold = compiled();
    wrongHousehold.occurrence_set.household_id = "other-home";
    await expect(
      buildCompiledPlanPreparationHandoff(wrongHousehold),
    ).rejects.toThrow(/internally inconsistent/i);

    const wrongStatus = compiled();
    wrongStatus.execution_status = "unexpected";
    await expect(
      buildCompiledPlanPreparationHandoff(wrongStatus),
    ).rejects.toThrow(/not complete/i);
  });
});
