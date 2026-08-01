import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarRange,
  Database,
  FileCheck2,
  History,
  Link2,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";

import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { householdApi } from "@/lib/platformApi";
import { preparationOperationsApi } from "@/lib/preparationOperationsApi";

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Preparation provenance coverage could not be loaded";
}

function percentage(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function CoverageBar({ value, label }: { value: number; label: string }) {
  const bounded = Math.max(0, Math.min(1, value));
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span>{label}</span>
        <span className="font-medium tabular-nums">{percentage(bounded)}</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(bounded * 100)}
      >
        <div
          className="h-full rounded-full bg-primary transition-[width] motion-reduce:transition-none"
          style={{ width: `${bounded * 100}%` }}
        />
      </div>
    </div>
  );
}

function MetricCard({
  title,
  value,
  description,
  icon: Icon,
}: {
  title: string;
  value: number | string;
  description: string;
  icon: typeof Database;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription className="flex items-center gap-2">
          <Icon className="h-4 w-4" aria-hidden="true" />
          {title}
        </CardDescription>
        <CardTitle className="text-2xl tabular-nums">{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

export default function PreparationOperationsCoveragePage() {
  const [selectedId, setSelectedId] = useState("");
  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const householdId = selectedId || households[0]?.id || "";

  useEffect(() => {
    if (selectedId && !households.some((value) => value.id === selectedId)) {
      setSelectedId("");
    }
  }, [households, selectedId]);

  const coverageQ = useQuery({
    queryKey: ["preparation-operations", householdId, "coverage"],
    queryFn: () => preparationOperationsApi.coverage(householdId),
    enabled: Boolean(householdId),
  });
  const coverage = coverageQ.data;
  const error = householdsQ.error || coverageQ.error;
  const statusEntries = useMemo(
    () => Object.entries(coverage?.schedule_status_counts ?? {}),
    [coverage],
  );

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">Preparation provenance coverage</h1>
            <p className="text-sm text-muted-foreground">
              Descriptive denominators for resource calendars, occurrence
              documents, deterministic replay inputs, source-plan links, and
              lifecycle events.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/preparation/operations">Open operations workspace</Link>
          </Button>
        </div>

        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Coverage is not correctness or safety</AlertTitle>
          <AlertDescription>
            A complete document or replay input proves that provenance exists.
            It does not certify recipe quality, appliance state, task execution,
            nutrition accuracy, or food safety. Approval still performs a fresh
            server-side integrity replay.
          </AlertDescription>
        </Alert>

        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Coverage unavailable</AlertTitle>
            <AlertDescription>{messageOf(error)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Household scope</CardTitle>
            <CardDescription>
              Metrics include only records visible within the selected household.
            </CardDescription>
          </CardHeader>
          <CardContent className="max-w-xl space-y-1">
            <Label htmlFor="coverage-household">Household</Label>
            <select
              id="coverage-household"
              value={householdId}
              onChange={(event) => setSelectedId(event.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {households.map((household) => (
                <option key={household.id} value={household.id}>
                  {household.name}
                </option>
              ))}
            </select>
          </CardContent>
        </Card>

        {coverageQ.isLoading && householdId && (
          <p className="text-sm text-muted-foreground" aria-live="polite">
            Loading preparation provenance coverage…
          </p>
        )}

        {coverage && (
          <>
            {coverage.warnings.length > 0 && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Coverage gaps detected</AlertTitle>
                <AlertDescription>
                  <ul className="list-disc space-y-1 pl-5">
                    {coverage.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                title="Calendars"
                value={coverage.calendar_total}
                description={`${coverage.reviewed_calendar_total} reviewed · ${coverage.active_reviewed_calendar_count} active reviewed`}
                icon={CalendarRange}
              />
              <MetricCard
                title="Schedules"
                value={coverage.schedule_total}
                description={`${coverage.replayable_schedule_count} have complete stored replay provenance`}
                icon={Database}
              />
              <MetricCard
                title="Replayable drafts"
                value={coverage.replayable_draft_count}
                description="Stored provenance exists; approval still revalidates every linked input"
                icon={FileCheck2}
              />
              <MetricCard
                title="Lifecycle events"
                value={coverage.event_total}
                description="Append-only creation and transition records"
                icon={History}
              />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Provenance completeness</CardTitle>
                  <CardDescription>
                    Exact stored-document denominators across all persisted
                    schedules in this household.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <CoverageBar
                    value={coverage.occurrence_document_coverage}
                    label="Occurrence documents"
                  />
                  <CoverageBar
                    value={coverage.scheduler_request_coverage}
                    label="Deterministic scheduler requests"
                  />
                  <CoverageBar
                    value={coverage.replayable_schedule_coverage}
                    label="Complete replay provenance"
                  />
                  <div className="flex items-center gap-2 text-sm">
                    <Link2 className="h-4 w-4" aria-hidden="true" />
                    <span>
                      {coverage.source_plan_linked_count} of {coverage.schedule_total}
                      {" "}schedules link an exact source-plan version.
                    </span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Schedule states</CardTitle>
                  <CardDescription>
                    Lifecycle counts are descriptive and include terminal and
                    superseded work.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {statusEntries.map(([status, count]) => (
                      <Badge key={status} variant="outline" className="capitalize">
                        {status}: {count}
                      </Badge>
                    ))}
                  </div>
                  <div className="space-y-2 text-sm text-muted-foreground">
                    <p>
                      Replayable: {coverage.replay_status_counts.replayable}
                    </p>
                    <p>
                      Missing request: {coverage.replay_status_counts.legacy_request_missing}
                    </p>
                    <p>
                      Missing occurrence document:{" "}
                      {coverage.replay_status_counts.legacy_occurrence_set_missing}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}
