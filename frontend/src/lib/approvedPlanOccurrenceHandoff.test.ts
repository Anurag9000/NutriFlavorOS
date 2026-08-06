import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  APPROVED_PLAN_OCCURRENCE_HANDOFF_KEY,
  buildApprovedPlanOccurrenceHandoff,
  consumeApprovedPlanOccurrenceHandoff,
  peekApprovedPlanOccurrenceHandoff,
  storeApprovedPlanOccurrenceHandoff,
  validateApprovedPlanOccurrenceHandoff,
} from "@/lib/approvedPlanOccurrenceHandoff";
import type { ConfirmedPlanOccurrenceSetView } from "@/lib/householdPlanApi";

const NOW = "2026-08-02T10:00:00.000Z";

function confirmed(): ConfirmedPlanOccurrenceSetView {
  return {
    household_id: "home-1",
    source_plan_id: 42,
    source_plan_version: 2,
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
    confirmed_count: 1,
    excluded_count: 0,
    warnings: [],
  };
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(NOW));
  sessionStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("approved-plan occurrence handoff", () => {
  it("round-trips once and removes the stored handoff on consumption", () => {
    const handoff = buildApprovedPlanOccurrenceHandoff(confirmed(), NOW);
    storeApprovedPlanOccurrenceHandoff(handoff);

    expect(peekApprovedPlanOccurrenceHandoff()).toEqual(handoff);
    expect(consumeApprovedPlanOccurrenceHandoff()).toEqual(handoff);
    expect(
      sessionStorage.getItem(APPROVED_PLAN_OCCURRENCE_HANDOFF_KEY),
    ).toBeNull();
    expect(consumeApprovedPlanOccurrenceHandoff()).toBeNull();
  });

  it("rejects household mismatch and profile-map drift", () => {
    const handoff = buildApprovedPlanOccurrenceHandoff(confirmed(), NOW);
    expect(() =>
      validateApprovedPlanOccurrenceHandoff(
        {
          ...handoff,
          occurrence_set: {
            ...handoff.occurrence_set,
            household_id: "other-home",
          },
        },
        new Date(NOW).getTime(),
      ),
    ).toThrow(/household does not match/i);

    expect(() =>
      validateApprovedPlanOccurrenceHandoff(
        {
          ...handoff,
          profile_versions: {},
        },
        new Date(NOW).getTime(),
      ),
    ).toThrow(/exactly match/i);
  });

  it("rejects invalid profile identities and expired handoffs", () => {
    const handoff = buildApprovedPlanOccurrenceHandoff(confirmed(), NOW);
    expect(() =>
      validateApprovedPlanOccurrenceHandoff(
        {
          ...handoff,
          profile_versions: { "recipe-1": "profile:7/version:v1" },
        },
        new Date(NOW).getTime(),
      ),
    ).toThrow(/invalid profile-version identity/i);

    expect(() =>
      validateApprovedPlanOccurrenceHandoff(
        handoff,
        new Date(NOW).getTime() + 31 * 60 * 1000,
      ),
    ).toThrow(/expired/i);
  });

  it("rejects malformed occurrence quantities and duplicate IDs", () => {
    const handoff = buildApprovedPlanOccurrenceHandoff(confirmed(), NOW);
    const occurrence = handoff.occurrence_set.occurrences[0];
    expect(() =>
      validateApprovedPlanOccurrenceHandoff(
        {
          ...handoff,
          occurrence_set: {
            ...handoff.occurrence_set,
            occurrences: [{ ...occurrence, servings: 0 }],
          },
        },
        new Date(NOW).getTime(),
      ),
    ).toThrow(/invalid servings/i);

    expect(() =>
      validateApprovedPlanOccurrenceHandoff(
        {
          ...handoff,
          occurrence_set: {
            ...handoff.occurrence_set,
            occurrences: [occurrence, occurrence],
          },
        },
        new Date(NOW).getTime(),
      ),
    ).toThrow(/duplicated/i);
  });
});
