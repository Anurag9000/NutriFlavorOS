import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreparationPipelinePage from "@/pages/PreparationPipeline";

const mocks = vi.hoisted(() => ({
  profiles: vi.fn(),
  compileAndSchedule: vi.fn(),
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
    compileAndSchedule: mocks.compileAndSchedule,
  },
}));

const profile = {
  id: 1,
  recipe_id: "reviewed-soup",
  profile_version: "2",
  schema_version: "1",
  supported_servings_min: 2,
  supported_servings_max: 6,
  task_templates: [
    {
      template_id: "heat",
      name: "Heat",
      duration_min_minutes: 10,
      duration_max_minutes: 15,
      resource_demands: { burner: 1 },
      dependencies: [],
      active_work: true,
      unattended_allowed: false,
    },
  ],
  source_name: "Reviewed protocol",
  source_url: "https://example.test/reviewed-soup",
  source_version: "2026-08",
  evidence_status: "reviewed",
  reviewed_at: "2026-08-01T00:00:00Z",
  reviewed_by: "Reviewer",
  notes: null,
  content_hash: "a".repeat(64),
  supersedes_profile_id: 3,
  active: true,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <PreparationPipelinePage />
    </QueryClientProvider>,
  );
}

function fillPipelineForm() {
  fireEvent.change(screen.getByLabelText("Horizon minutes"), {
    target: { value: "240" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Add occurrence" }));
  fireEvent.change(screen.getByLabelText("Occurrence ID"), {
    target: { value: "day1.dinner" },
  });
  fireEvent.change(screen.getByLabelText("Reviewed profile"), {
    target: { value: "reviewed-soup" },
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
  fireEvent.click(screen.getByRole("button", { name: "Add resource" }));
  fireEvent.change(screen.getByLabelText("Resource ID"), {
    target: { value: "burner" },
  });
  fireEvent.change(screen.getByLabelText("Capacity"), {
    target: { value: "1" },
  });
  fireEvent.change(screen.getByLabelText("Available until"), {
    target: { value: "240" },
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.profiles.mockResolvedValue([profile]);
});

describe("Reviewed preparation pipeline", () => {
  it("sends a fail-closed request by default", async () => {
    mocks.compileAndSchedule.mockResolvedValue({
      compilation: {
        tasks: [],
        unresolved: [
          {
            occurrence_id: "day1.dinner",
            recipe_id: "reviewed-soup",
            reason_code: "profile_not_reviewed",
            message: "Only reviewed preparation evidence may be compiled",
          },
        ],
        profile_versions: {},
        duration_policy: "conservative_max",
        warnings: [],
      },
      schedule: null,
      partial: false,
      execution_status: "blocked_unresolved",
    });

    renderPage();
    expect(await screen.findByText(/Reviewed protocol/)).toBeInTheDocument();
    expect(screen.getByText(/sha256:/)).toHaveTextContent(profile.content_hash);
    fillPipelineForm();
    fireEvent.click(
      screen.getByRole("button", { name: "Compile and schedule safely" }),
    );

    expect(
      await screen.findByText(/blocked unresolved/i),
    ).toBeInTheDocument();
    expect(mocks.compileAndSchedule).toHaveBeenCalledWith({
      occurrences: [
        {
          occurrence_id: "day1.dinner",
          recipe_id: "reviewed-soup",
          required_finish_minute: 120,
          servings: 4,
          priority: 3,
        },
      ],
      duration_policy: "conservative_max",
      reviewed_only: true,
      allow_partial: false,
      horizon_minutes: 240,
      granularity_minutes: 5,
      resources: [
        {
          resource_id: "burner",
          label: null,
          capacity: 1,
          available_from_minute: 0,
          available_until_minute: 240,
        },
      ],
    });
  });

  it("requires explicit partial opt-in and displays evidence hash", async () => {
    mocks.compileAndSchedule.mockResolvedValue({
      compilation: {
        tasks: [
          {
            task_id: "day1.dinner.heat",
            duration_minutes: 15,
            earliest_start_minute: 0,
            latest_finish_minute: 120,
            priority: 3,
            resource_demands: { burner: 1 },
            dependencies: [],
            metadata: { profile_content_hash: profile.content_hash },
          },
        ],
        unresolved: [],
        profile_versions: {
          "reviewed-soup": `profile:1/version:2/sha256:${profile.content_hash}`,
        },
        duration_policy: "conservative_max",
        warnings: [],
      },
      schedule: {
        method: "deterministic_dependency_aware_resource_scheduler_v2",
        deterministic: true,
        horizon_minutes: 240,
        granularity_minutes: 5,
        scheduled: [
          {
            task_id: "day1.dinner.heat",
            start_minute: 0,
            finish_minute: 15,
            duration_minutes: 15,
            priority: 3,
            resource_demands: { burner: 1 },
            dependencies: [],
            metadata: { profile_content_hash: profile.content_hash },
          },
        ],
        unscheduled: [],
        resource_utilization: { burner: 0.0625 },
        resource_peak_usage: { burner: 1 },
        makespan_minutes: 15,
        diagnostics: {},
      },
      partial: false,
      execution_status: "scheduled",
    });

    renderPage();
    await screen.findByText(/Reviewed protocol/);
    fillPipelineForm();
    fireEvent.click(screen.getByLabelText("Allow partial scheduling"));
    fireEvent.click(
      screen.getByRole("button", { name: "Compile and schedule safely" }),
    );

    expect(await screen.findByText("day1.dinner.heat")).toBeInTheDocument();
    expect(screen.getAllByText(profile.content_hash).length).toBeGreaterThan(0);
    expect(mocks.compileAndSchedule).toHaveBeenCalledWith(
      expect.objectContaining({ allow_partial: true }),
    );
  });
});
