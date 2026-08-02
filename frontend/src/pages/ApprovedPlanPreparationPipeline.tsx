import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarRange,
  CheckCircle2,
  Clock3,
  FileCheck2,
  Send,
  ShieldCheck,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import {
  consumeApprovedPlanOccurrenceHandoff,
  type ApprovedPlanOccurrenceHandoff,
} from "@/lib/approvedPlanOccurrenceHandoff";
import {
  storeCompiledPlanPreparationHandoff,
} from "@/lib/compiledPlanPreparationHandoff";
import {
  householdPlanApi,
  type ApprovedPlanPreparationCompileView,
} from "@/lib/householdPlanApi";
import { householdApi, type HouseholdRole } from "@/lib/platformApi";
import {
  preparationOperationsApi,
  type ResourceCalendarVersionView,
} from "@/lib/preparationOperationsApi";

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Approved-plan preparation could not be compiled";
}

function canEdit(role?: HouseholdRole | null): boolean {
  return role === "owner" || role === "editor";
}

function shortHash(value: string): string {
  return value.length <= 22
    ? value
    : `${value.slice(0, 12)}…${value.slice(-8)}`;
}

function activeReviewedCalendars(
  calendars: ResourceCalendarVersionView[],
): ResourceCalendarVersionView[] {
  return calendars.filter(
    (value) => value.active && value.evidence_status === "reviewed",
  );
}

export default function ApprovedPlanPreparationPipelinePage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [handoff, setHandoff] =
    useState<ApprovedPlanOccurrenceHandoff | null>(null);
  const [handoffError, setHandoffError] = useState<string | null>(null);
  const [selectedCalendarId, setSelectedCalendarId] = useState("");
  const [granularityMinutes, setGranularityMinutes] = useState("5");
  const [compiled, setCompiled] =
    useState<ApprovedPlanPreparationCompileView | null>(null);
  const [compiledFingerprint, setCompiledFingerprint] = useState("");

  useEffect(() => {
    try {
      const value = consumeApprovedPlanOccurrenceHandoff();
      setHandoff(value);
      if (!value) {
        setHandoffError(
          "No current approved-plan occurrence handoff is available",
        );
      }
    } catch (error) {
      setHandoffError(messageOf(error));
    }
  }, []);

  const householdId = handoff?.household_id ?? "";
  const detailQ = useQuery({
    queryKey: ["households", householdId, "detail"],
    queryFn: () => householdApi.get(householdId),
    enabled: Boolean(householdId),
  });
  const calendarsQ = useQuery({
    queryKey: ["preparation-operations", householdId, "calendars"],
    queryFn: () => preparationOperationsApi.calendars(householdId),
    enabled: Boolean(householdId),
  });
  const calendars = useMemo(
    () => activeReviewedCalendars(calendarsQ.data ?? []),
    [calendarsQ.data],
  );
  const selectedCalendar = useMemo(() => {
    const requested = Number(selectedCalendarId);
    return calendars.find((value) => value.id === requested)
      ?? calendars[0]
      ?? null;
  }, [calendars, selectedCalendarId]);
  const role = detailQ.data?.role;

  useEffect(() => {
    setCompiled(null);
    setCompiledFingerprint("");
  }, [selectedCalendar?.id, granularityMinutes]);

  const currentFingerprint = useMemo(
    () =>
      JSON.stringify({
        household_id: handoff?.household_id ?? null,
        source_plan_id: handoff?.source_plan_id ?? null,
        source_plan_version: handoff?.source_plan_version ?? null,
        occurrence_set_version:
          handoff?.occurrence_set.occurrence_set_version ?? null,
        profile_versions: handoff?.profile_versions ?? null,
        calendar_version_id: selectedCalendar?.id ?? null,
        granularity_minutes: Number(granularityMinutes),
      }),
    [granularityMinutes, handoff, selectedCalendar?.id],
  );
  const compiledIsCurrent =
    compiled !== null && compiledFingerprint === currentFingerprint;

  const compile = useMutation({
    mutationFn: () => {
      if (!handoff) {
        throw new Error("Approved-plan occurrence handoff is missing");
      }
      if (!selectedCalendar) {
        throw new Error("Select an active reviewed resource calendar");
      }
      const granularity = Number(granularityMinutes);
      if (!Number.isInteger(granularity) || granularity < 1 || granularity > 60) {
        throw new Error("Granularity must be an integer from 1 to 60 minutes");
      }
      return householdPlanApi.compilePreparation(
        handoff.household_id,
        handoff.source_plan_id,
        {
          expected_plan_version: handoff.source_plan_version,
          calendar_version_id: selectedCalendar.id,
          occurrence_set: handoff.occurrence_set,
          profile_versions: handoff.profile_versions,
          granularity_minutes: granularity,
        },
      );
    },
    onSuccess: (value) => {
      setCompiled(value);
      setCompiledFingerprint(currentFingerprint);
      toast({
        title: value.partial
          ? "Preparation compiled with unresolved work"
          : "Preparation compiled deterministically",
        description: value.partial
          ? `${value.schedule_response.unscheduled.length} tasks remain unscheduled.`
          : `${value.schedule_response.scheduled.length} tasks are ready for operations review.`,
        variant: value.partial ? "destructive" : "default",
      });
    },
    onError: (error) =>
      toast({
        title: "Preparation compilation failed",
        description: messageOf(error),
        variant: "destructive",
      }),
  });

  const openOperations = async () => {
    if (!compiled || !compiledIsCurrent) {
      toast({
        title: "Recompile current inputs",
        description: "The compiled output no longer matches the selected review inputs.",
        variant: "destructive",
      });
      return;
    }
    try {
      await storeCompiledPlanPreparationHandoff(compiled);
      navigate("/preparation/operations");
    } catch (error) {
      toast({
        title: "Operations handoff blocked",
        description: messageOf(error),
        variant: "destructive",
      });
    }
  };

  const pageError = detailQ.error || calendarsQ.error;

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">
              Approved-plan preparation pipeline
            </h1>
            <p className="text-sm text-muted-foreground">
              Recheck the exact approved plan and reviewed profiles, select the
              active household calendar, and compile a deterministic schedule
              before a separate operations handoff.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/household/plans/occurrences">
                Confirm occurrences
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/preparation/operations/calendars/new">
                Calendar builder
              </Link>
            </Button>
          </div>
        </div>

        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Compilation is reviewable and non-persisted</AlertTitle>
          <AlertDescription>
            Opening this page consumes the one-time occurrence handoff. Nothing
            compiles automatically. The server rechecks plan approval, profile
            identities, serving ranges, and the active calendar. Operations
            persistence remains a separate explicit action with another replay.
          </AlertDescription>
        </Alert>

        {(handoffError || pageError) && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Approved-plan preparation unavailable</AlertTitle>
            <AlertDescription>
              {handoffError ?? messageOf(pageError)}
            </AlertDescription>
          </Alert>
        )}

        {!handoff && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Start from confirmed occurrences</CardTitle>
              <CardDescription>
                Return to the approved-plan occurrence workspace, confirm the
                current document, and explicitly open this pipeline again.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild>
                <Link to="/household/plans/occurrences">
                  Open approved-plan occurrences
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}

        {handoff && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileCheck2 className="h-4 w-4" />
                  Exact approved-plan occurrence input
                </CardTitle>
                <CardDescription>
                  Source plan #{handoff.source_plan_id} · version {handoff.source_plan_version}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className="capitalize">
                    {role ?? "no role"}
                  </Badge>
                  <Badge variant="outline">
                    {handoff.occurrence_set.occurrence_set_version}
                  </Badge>
                  <Badge variant="outline">
                    {handoff.occurrence_set.duration_policy}
                  </Badge>
                  <Badge variant="outline">
                    {handoff.occurrence_set.occurrences.length} occurrences
                  </Badge>
                </div>
                <div className="grid gap-3 lg:grid-cols-2">
                  {handoff.occurrence_set.occurrences.map((occurrence) => (
                    <div key={occurrence.occurrence_id} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">{occurrence.occurrence_id}</p>
                      <p className="text-muted-foreground">
                        Recipe {occurrence.recipe_id} · {occurrence.servings} servings
                      </p>
                      <p className="text-muted-foreground">
                        Finish minute {occurrence.required_finish_minute} · priority {occurrence.priority}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Profile {handoff.profile_versions[occurrence.recipe_id]}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <CalendarRange className="h-4 w-4" />
                  Active reviewed resource calendar
                </CardTitle>
                <CardDescription>
                  Only active reviewed calendars can be compiled.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="approved-pipeline-calendar">Calendar</Label>
                  <select
                    id="approved-pipeline-calendar"
                    value={selectedCalendar?.id ?? ""}
                    onChange={(event) => setSelectedCalendarId(event.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    {calendars.map((calendar) => (
                      <option key={calendar.id} value={calendar.id}>
                        {calendar.calendar_version} · {calendar.resources.length} resources · {calendar.horizon_minutes} minutes
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="approved-pipeline-granularity">
                    Scheduling granularity minutes
                  </Label>
                  <Input
                    id="approved-pipeline-granularity"
                    type="number"
                    min="1"
                    max="60"
                    step="1"
                    value={granularityMinutes}
                    onChange={(event) => setGranularityMinutes(event.target.value)}
                  />
                </div>
                {selectedCalendar && (
                  <div className="md:col-span-2 space-y-2 rounded-md border p-3 text-sm">
                    <p className="font-medium">
                      {selectedCalendar.calendar_version} · {selectedCalendar.timezone}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Calendar SHA-256 {shortHash(selectedCalendar.content_hash)}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {selectedCalendar.resources.map((resource) => (
                        <Badge key={resource.resource_id} variant="outline">
                          {resource.label}: capacity {resource.capacity}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                <div className="md:col-span-2">
                  <Button
                    type="button"
                    disabled={
                      !canEdit(role)
                      || !selectedCalendar
                      || compile.isPending
                    }
                    onClick={() => compile.mutate()}
                  >
                    <Clock3 className="mr-2 h-4 w-4" />
                    Compile deterministic preparation schedule
                  </Button>
                  {!canEdit(role) && (
                    <p className="mt-2 text-sm text-muted-foreground">
                      Editor or owner access is required to compile preparation.
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>

            {!calendarsQ.isLoading && calendars.length === 0 && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>No active reviewed calendar</AlertTitle>
                <AlertDescription>
                  Register and activate a reviewed household resource calendar
                  before compiling preparation.
                </AlertDescription>
              </Alert>
            )}
          </>
        )}

        {compiledIsCurrent && compiled && (
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <CheckCircle2 className="h-4 w-4" />
                    Deterministic compilation result
                  </CardTitle>
                  <CardDescription>
                    Calendar {compiled.calendar_version} · source plan #{compiled.source_plan_id} version {compiled.source_plan_version}
                  </CardDescription>
                </div>
                <Badge variant={compiled.partial ? "destructive" : "default"}>
                  {compiled.execution_status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {compiled.warnings.map((warning) => (
                <Alert key={warning} variant={compiled.partial ? "destructive" : "default"}>
                  <AlertDescription>{warning}</AlertDescription>
                </Alert>
              ))}
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Scheduled tasks</p>
                  <p className="text-xl font-semibold">
                    {compiled.schedule_response.scheduled.length}
                  </p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Unscheduled tasks</p>
                  <p className="text-xl font-semibold">
                    {compiled.schedule_response.unscheduled.length}
                  </p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Makespan</p>
                  <p className="text-xl font-semibold">
                    {compiled.schedule_response.makespan_minutes} min
                  </p>
                </div>
              </div>
              <div className="space-y-2">
                {compiled.schedule_response.scheduled.map((task) => (
                  <div key={task.task_id} className="rounded-md border p-3 text-sm">
                    <div className="flex flex-wrap justify-between gap-2">
                      <span className="font-medium">{task.task_id}</span>
                      <span className="text-muted-foreground">
                        minute {task.start_minute}–{task.finish_minute}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Resources {JSON.stringify(task.resource_demands)} · dependencies {task.dependencies.join(", ") || "none"}
                    </p>
                  </div>
                ))}
                {compiled.schedule_response.unscheduled.map((task) => (
                  <div key={task.task_id} className="rounded-md border border-destructive p-3 text-sm">
                    <p className="font-medium">{task.task_id}</p>
                    <p className="text-destructive">
                      {task.reason_code}: {task.message}
                    </p>
                  </div>
                ))}
              </div>
              <Button
                type="button"
                disabled={compiled.partial}
                onClick={openOperations}
              >
                <Send className="mr-2 h-4 w-4" />
                Open preparation operations review
              </Button>
              {compiled.partial && (
                <p className="text-sm text-muted-foreground">
                  Resolve every unscheduled task before an operations handoff can be staged.
                </p>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
