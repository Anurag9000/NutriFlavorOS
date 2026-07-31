import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreparationPage from "@/pages/Preparation";

const mocks = vi.hoisted(() => ({
  profiles: vi.fn(),
  buildTasks: vi.fn(),
  schedule: vi.fn(),
  toast: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock("@/lib/preparationApi", () => ({
  preparationApi: {
    profiles: mocks.profiles,
    buildTasks: mocks.buildTasks,
    schedule: mocks.schedule,
  },
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <PreparationPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.profiles.mockResolvedValue([]);
});

describe("Preparation workspace", () => {
  it("builds an explicit dependency-aware resource schedule request", async () => {
    mocks.schedule.mockResolvedValue({
      method: "deterministic_dependency_aware_resource_scheduler_v2",
      deterministic: true,
      horizon_minutes: 120,
      granularity_minutes: 5,
      scheduled: [
        {
          task_id: "bake",
          start_minute: 30,
          finish_minute: 60,
          duration_minutes: 30,
          priority: 2,
          resource_demands: { oven: 1 },
          dependencies: ["mix"],
          metadata: {},
        },
      ],
      unscheduled: [],
      resource_utilization: { oven: 0.25 },
      resource_peak_usage: { oven: 1 },
      makespan_minutes: 60,
      diagnostics: {
        scheduled_count: 1,
        critical_path_lower_bound_minutes: 60,
      },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("Horizon minutes"), {
      target: { value: "120" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add resource" }));
    fireEvent.change(screen.getByLabelText("Resource ID"), {
      target: { value: "oven" },
    });
    fireEvent.change(screen.getByLabelText("Available until"), {
      target: { value: "120" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Add task" }));
    fireEvent.change(screen.getByLabelText("Task ID"), {
      target: { value: "bake" },
    });
    fireEvent.change(screen.getByLabelText("Duration"), {
      target: { value: "30" },
    });
    fireEvent.change(screen.getByLabelText("Latest finish"), {
      target: { value: "60" },
    });
    fireEvent.change(screen.getByLabelText("Priority"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("Resource demands"), {
      target: { value: "oven:1" },
    });
    fireEvent.change(screen.getByLabelText("Dependencies"), {
      target: { value: "mix" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));

    expect(await screen.findByText("bake")).toBeInTheDocument();
    expect(mocks.schedule).toHaveBeenCalledWith({
      horizon_minutes: 120,
      granularity_minutes: 5,
      resources: [
        {
          resource_id: "oven",
          label: null,
          capacity: 1,
          available_from_minute: 0,
          available_until_minute: 120,
        },
      ],
      tasks: [
        {
          task_id: "bake",
          duration_minutes: 30,
          earliest_start_minute: 0,
          latest_finish_minute: 60,
          priority: 2,
          resource_demands: { oven: 1 },
          dependencies: ["mix"],
          metadata: {},
        },
      ],
    });
    expect(screen.getByText("25.0%")).toBeInTheDocument();
    expect(screen.getByText("After: mix")).toBeInTheDocument();
  });

  it("compiles a reviewed profile into namespaced task drafts", async () => {
    mocks.profiles.mockResolvedValue([
      {
        id: 1,
        recipe_id: "soup",
        schema_version: "1",
        supported_servings_min: 2,
        supported_servings_max: 6,
        task_templates: [],
        source_name: "Reviewed protocol",
        source_url: "https://example.test/soup",
        source_version: "2026-07",
        evidence_status: "reviewed",
        reviewed_at: "2026-07-31T00:00:00Z",
        reviewed_by: "Reviewer",
        active: true,
        created_at: "2026-07-31T00:00:00Z",
        updated_at: "2026-07-31T00:00:00Z",
      },
    ]);
    mocks.buildTasks.mockResolvedValue({
      tasks: [
        {
          task_id: "day1.dinner.simmer",
          duration_minutes: 35,
          earliest_start_minute: 0,
          latest_finish_minute: 120,
          priority: 3,
          resource_demands: { burner: 1 },
          dependencies: ["day1.dinner.chop"],
          metadata: { evidence_status: "reviewed" },
        },
      ],
      unresolved: [],
      profile_versions: { soup: "profile:1/schema:1/source:2026-07" },
      duration_policy: "conservative_max",
      warnings: [],
    });

    renderPage();
    expect(await screen.findByText(/Reviewed protocol/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add occurrence" }));
    fireEvent.change(screen.getByLabelText("Occurrence ID"), {
      target: { value: "day1.dinner" },
    });
    fireEvent.change(screen.getByLabelText("Recipe profile"), {
      target: { value: "soup" },
    });
    fireEvent.change(screen.getByLabelText("Required finish"), {
      target: { value: "120" },
    });
    fireEvent.change(screen.getByLabelText("Servings"), {
      target: { value: "4" },
    });
    fireEvent.change(screen.getByLabelText("Priority"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Compile reviewed tasks" }));

    expect(await screen.findByDisplayValue("day1.dinner.simmer")).toBeInTheDocument();
    expect(screen.getByDisplayValue("day1.dinner.chop")).toBeInTheDocument();
    expect(mocks.buildTasks).toHaveBeenCalledWith(
      [
        {
          occurrence_id: "day1.dinner",
          recipe_id: "soup",
          required_finish_minute: 120,
          servings: 4,
          priority: 3,
        },
      ],
      "conservative_max",
      true,
    );
  });

  it("renders dependency and resource failures without inventing a fallback", async () => {
    mocks.schedule.mockResolvedValue({
      method: "deterministic_dependency_aware_resource_scheduler_v2",
      deterministic: true,
      horizon_minutes: 60,
      granularity_minutes: 5,
      scheduled: [],
      unscheduled: [
        {
          task_id: "pack",
          reason_code: "blocked_by_dependency",
          message: "A prerequisite task was not scheduled",
          missing_resources: [],
          blocked_by: ["freeze"],
          capacity_violations: {},
          metadata: {},
        },
      ],
      resource_utilization: {},
      resource_peak_usage: {},
      makespan_minutes: 0,
      diagnostics: {
        unscheduled_count: 1,
        critical_path_lower_bound_minutes: 30,
      },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("Horizon minutes"), {
      target: { value: "60" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add task" }));
    fireEvent.change(screen.getByLabelText("Task ID"), {
      target: { value: "pack" },
    });
    fireEvent.change(screen.getByLabelText("Dependencies"), {
      target: { value: "freeze" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));

    expect(await screen.findByText(/pack: blocked by dependency/i)).toBeInTheDocument();
    expect(screen.getByText(/Blocked by: freeze/)).toBeInTheDocument();
    expect(screen.getByText("No task could be scheduled.")).toBeInTheDocument();
  });
});
