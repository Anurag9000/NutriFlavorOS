import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreparationCalendarBuilderPage from "@/pages/PreparationCalendarBuilder";

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  householdList: vi.fn(),
  householdGet: vi.fn(),
  calendars: vi.fn(),
  createCalendar: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock("@/lib/platformApi", () => ({
  householdApi: {
    list: mocks.householdList,
    get: mocks.householdGet,
  },
}));

vi.mock("@/lib/preparationOperationsApi", () => ({
  preparationOperationsApi: {
    calendars: mocks.calendars,
    createCalendar: mocks.createCalendar,
  },
}));

const household = {
  id: "calendar-home",
  owner_user_id: "owner@example.test",
  name: "Calendar home",
  timezone: "UTC",
  version: 1,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  current_role: "owner",
};

const activeCalendar = {
  id: 7,
  household_id: household.id,
  calendar_version: "calendar-v0",
  horizon_minutes: 240,
  timezone: "UTC",
  evidence_status: "reviewed" as const,
  reviewed_at: "2026-08-01T00:00:00Z",
  reviewed_by: "Earlier reviewer",
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
      resource_id: "burner",
      label: "Stove burner",
      capacity: 1,
      resource_kind: "equipment",
      availability_windows: [{ start_minute: 0, end_minute: 240 }],
      metadata: { source: "legacy_workspace" },
    },
    {
      id: 12,
      calendar_version_id: 7,
      resource_id: "person",
      label: "Available cook",
      capacity: 1,
      resource_kind: "person",
      availability_windows: [{ start_minute: 0, end_minute: 240 }],
      metadata: { source: "older_import" },
    },
  ],
};

const reviewLabels = [
  "I confirmed declared person availability with the household.",
  "I confirmed equipment/workspace availability and capacity.",
  "I confirmed the horizon and timezone (UTC).",
  "I understand activation invalidates dependent draft and approved schedules on the predecessor.",
];

function renderPage(role: "owner" | "viewer" = "owner") {
  mocks.householdGet.mockResolvedValue({
    household: { ...household, current_role: role },
    role,
    members: [],
    active_servings_multiplier: 0,
    planning_status: "ready",
  });
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <PreparationCalendarBuilderPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

async function completeReview() {
  for (const label of reviewLabels) {
    fireEvent.click(screen.getByLabelText(label));
  }
  await waitFor(() =>
    expect(
      screen.getByRole("button", {
        name: "Activate reviewed calendar version",
      }),
    ).toBeEnabled(),
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.householdList.mockResolvedValue([household]);
  mocks.calendars.mockResolvedValue([activeCalendar]);
  mocks.createCalendar.mockImplementation(async (_householdId, payload) => ({
    ...activeCalendar,
    id: 8,
    calendar_version: payload.calendar_version,
    reviewed_at: payload.reviewed_at,
    reviewed_by: payload.reviewed_by,
    notes: payload.notes,
    resources: payload.resources.map((resource: Record<string, unknown>, index: number) => ({
      id: 20 + index,
      calendar_version_id: 8,
      ...resource,
    })),
  }));
});

describe("Reviewed resource calendar builder", () => {
  it("ignores metadata-only predecessor differences", async () => {
    renderPage();

    expect(
      await screen.findByText("Reviewed resource calendar builder"),
    ).toBeInTheDocument();
    expect(screen.getByText("Added: 0")).toBeInTheDocument();
    expect(screen.getByText("Changed: 0")).toBeInTheDocument();
    expect(screen.getByText("Removed: 0")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Activate reviewed calendar version",
      }),
    ).toBeDisabled();
  });

  it("activates a reviewed canonical resource calendar only after every confirmation", async () => {
    renderPage();
    await screen.findByText("Reviewed resource calendar builder");

    fireEvent.change(screen.getByLabelText("Reviewed by"), {
      target: { value: "Household owner" },
    });
    await completeReview();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Activate reviewed calendar version",
      }),
    );

    await waitFor(() => expect(mocks.createCalendar).toHaveBeenCalledTimes(1));
    const [householdId, payload] = mocks.createCalendar.mock.calls[0];
    expect(householdId).toBe(household.id);
    expect(payload.evidence_status).toBe("reviewed");
    expect(payload.activate).toBe(true);
    expect(payload.reviewed_by).toBe("Household owner");
    expect(payload.reviewed_at).toMatch(/Z$/);
    expect(payload.idempotency_key).toMatch(/^calendar-builder-/);
    expect(payload.resources.map((value: { resource_id: string }) => value.resource_id)).toEqual([
      "burner",
      "person",
    ]);
    expect(payload.resources[0].availability_windows).toEqual([
      { start_minute: 0, end_minute: 240 },
    ]);
    expect(payload.resources[0].metadata).toEqual({
      source: "structured_calendar_builder",
    });
  });

  it("resets human confirmations whenever the reviewed draft changes", async () => {
    renderPage();
    await screen.findByText("Reviewed resource calendar builder");

    fireEvent.change(screen.getByLabelText("Reviewed by"), {
      target: { value: "Household owner" },
    });
    await completeReview();

    const firstResource = screen.getByText("Resource 1").closest("fieldset");
    expect(firstResource).not.toBeNull();
    fireEvent.change(within(firstResource as HTMLElement).getByLabelText("Label"), {
      target: { value: "Primary available cook" },
    });

    await waitFor(() =>
      expect(
        screen.getByRole("button", {
          name: "Activate reviewed calendar version",
        }),
      ).toBeDisabled(),
    );
    for (const label of reviewLabels) {
      expect(screen.getByLabelText(label)).not.toBeChecked();
    }
  });

  it("rejects overlapping windows with an explicit validation error", async () => {
    renderPage();
    await screen.findByText("Reviewed resource calendar builder");

    const firstResource = screen.getByText("Resource 1").closest("fieldset");
    expect(firstResource).not.toBeNull();
    fireEvent.click(
      within(firstResource as HTMLElement).getByRole("button", {
        name: "Add window",
      }),
    );
    const resource = within(firstResource as HTMLElement);
    fireEvent.change(resource.getByLabelText("Window 1 end minute"), {
      target: { value: "180" },
    });
    fireEvent.change(resource.getByLabelText("Window 2 start minute"), {
      target: { value: "120" },
    });
    fireEvent.change(resource.getByLabelText("Window 2 end minute"), {
      target: { value: "240" },
    });
    fireEvent.change(screen.getByLabelText("Reviewed by"), {
      target: { value: "Household owner" },
    });
    await completeReview();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Activate reviewed calendar version",
      }),
    );

    expect(
      await screen.findByText(/Availability windows for person cannot overlap/),
    ).toBeInTheDocument();
    expect(mocks.createCalendar).not.toHaveBeenCalled();
    expect(
      screen.getByText(/Resolve resource or window validation errors to compare/),
    ).toBeInTheDocument();
  });

  it("imports a canonical draft without activating it automatically", async () => {
    renderPage();
    await screen.findByText("Reviewed resource calendar builder");

    const document = {
      document_version: "preparation-resource-calendar-draft-v1",
      calendar_version: "imported-v2",
      horizon_minutes: 180,
      timezone: "UTC",
      notes: "Imported for review",
      resources: [
        {
          resource_id: "person",
          label: "Available cook",
          capacity: 1,
          resource_kind: "person",
          availability_windows: [
            { start_minute: 0, end_minute: 30 },
            { start_minute: 60, end_minute: 180 },
          ],
          metadata: { ignored: "input metadata is normalized" },
        },
      ],
    };
    fireEvent.change(screen.getByLabelText("Calendar draft JSON"), {
      target: { value: JSON.stringify(document) },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Load JSON into builder" }),
    );

    expect(await screen.findByDisplayValue("imported-v2")).toBeInTheDocument();
    expect(screen.getByDisplayValue("180")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Imported for review")).toBeInTheDocument();
    expect(screen.getByLabelText("Window 1 end minute")).toHaveValue(30);
    expect(screen.getByLabelText("Window 2 start minute")).toHaveValue(60);
    expect(mocks.createCalendar).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", {
        name: "Activate reviewed calendar version",
      }),
    ).toBeDisabled();
  });

  it("keeps activation unavailable to a viewer", async () => {
    renderPage("viewer");

    expect(
      await screen.findByText(/owner access is required/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Activate reviewed calendar version",
      }),
    ).toBeDisabled();
  });
});
