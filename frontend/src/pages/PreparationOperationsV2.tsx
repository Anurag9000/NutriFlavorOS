import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarRange,
  CheckCircle2,
  ClipboardCheck,
  FileCode2,
  FileLock2,
  History,
  Link2,
  PlayCircle,
  ShieldCheck,
  XCircle,
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
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { householdApi, type HouseholdRole } from "@/lib/platformApi";
import {
  preparationOperationsApi,
  type PersistedPreparationScheduleView,
  type PreparationScheduleStatus,
  type ResourceCalendarVersionView,
  type ScheduleStateTransitionRequest,
} from "@/lib/preparationOperationsApi";
import {
  canonicalJson,
  consumePreparationOperationsHandoff,
  type PreparationOperationsHandoff,
} from "@/lib/preparationOperationsHandoff";

interface ConfirmationState {
  source: boolean;
  calendar: boolean;
  tasks: boolean;
  boundary: boolean;
}

interface TransitionInput {
  action: "approve" | "cancel" | "invalidate";
  schedule: PersistedPreparationScheduleView;
  reason: string;
  idempotencyKey: string;
}

const EMPTY_CONFIRMATIONS: ConfirmationState = {
  source: false,
  calendar: false,
  tasks: false,
  boundary: false,
};

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Preparation operations request failed";
}

function canEdit(role?: HouseholdRole | null): boolean {
  return role === "owner" || role === "editor";
}

function isOwner(role?: HouseholdRole | null): boolean {
  return role === "owner";
}

function idempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function shortHash(value?: string | null): string {
  if (!value) return "missing";
  return value.length <= 22
    ? value
    : `${value.slice(0, 12)}…${value.slice(-8)}`;
}

function dateLabel(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : "Not recorded";
}

function taskIdSet(values: { task_id: string }[]): string[] {
  return values.map((value) => value.task_id).sort();
}

function reviewIssues(
  handoff: PreparationOperationsHandoff,
  calendar: ResourceCalendarVersionView | null,
): string[] {
  const bundle = handoff.bundle;
  const issues: string[] = [];
  if (handoff.household_id !== bundle.occurrence_set.household_id) {
    issues.push("Handoff and occurrence-document households differ");
  }
  if (!/^[a-f0-9]{64}$/.test(handoff.occurrence_set_hash_preview)) {
    issues.push("Occurrence hash preview is not a lowercase SHA-256 value");
  }
  if ((bundle.source_plan_id == null) !== (bundle.source_plan_version == null)) {
    issues.push("Source plan ID and version must be present together");
  }
  const occurrenceRecipes = [...new Set(
    bundle.occurrence_set.occurrences.map((value) => value.recipe_id),
  )].sort();
  const profileRecipes = Object.keys(bundle.profile_versions).sort();
  if (canonicalJson(occurrenceRecipes) !== canonicalJson(profileRecipes)) {
    issues.push("Preparation-profile recipes do not exactly match occurrence recipes");
  }
  if (bundle.schedule_request.tasks.length === 0) {
    issues.push("Schedule request contains no deterministic tasks");
  }
  if (bundle.schedule_response.unscheduled.length > 0) {
    issues.push("Deterministic response still contains unscheduled tasks");
  }
  if (
    canonicalJson(taskIdSet(bundle.schedule_request.tasks))
    !== canonicalJson(taskIdSet(bundle.schedule_response.scheduled))
  ) {
    issues.push("Scheduled task IDs do not exactly match request task IDs");
  }
  const taskIds = new Set(bundle.schedule_request.tasks.map((value) => value.task_id));
  const unknownDependencies = [...new Set(
    bundle.schedule_request.tasks.flatMap((task) =>
      task.dependencies.filter((dependency) => !taskIds.has(dependency)),
    ),
  )].sort();
  if (unknownDependencies.length) {
    issues.push(`Unknown task dependencies: ${unknownDependencies.join(", ")}`);
  }
  if (calendar) {
    if (calendar.id !== bundle.calendar_version_id) {
      issues.push("Fetched calendar does not match the handoff calendar ID");
    }
    if (!calendar.active || calendar.evidence_status !== "reviewed") {
      issues.push("Selected calendar is no longer active and reviewed");
    }
    if (calendar.horizon_minutes !== bundle.schedule_request.horizon_minutes) {
      issues.push("Schedule horizon differs from the reviewed calendar horizon");
    }
    const calendarIds = calendar.resources
      .map((value) => value.resource_id)
      .sort();
    const requestIds = bundle.schedule_request.resources
      .map((value) => value.resource_id)
      .sort();
    if (canonicalJson(calendarIds) !== canonicalJson(requestIds)) {
      issues.push("Schedule resources differ from the reviewed calendar resources");
    }
  }
  return issues;
}

function statusVariant(status: PreparationScheduleStatus) {
  if (status === "approved" || status === "completed") return "default" as const;
  if (status === "invalidated" || status === "cancelled") return "destructive" as const;
  return "outline" as const;
}

export default function PreparationOperationsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const handoffConsumed = useRef(false);
  const [handoff, setHandoff] = useState<PreparationOperationsHandoff | null>(null);
  const [handoffError, setHandoffError] = useState<string | null>(null);
  const [householdId, setHouseholdId] = useState("");
  const [confirmations, setConfirmations] = useState(EMPTY_CONFIRMATIONS);
  const [persistenceNotes, setPersistenceNotes] = useState("");
  const [persisted, setPersisted] = useState<PersistedPreparationScheduleView | null>(null);
  const [selectedScheduleId, setSelectedScheduleId] = useState("");
  const [transitionReason, setTransitionReason] = useState("");

  useEffect(() => {
    if (handoffConsumed.current) return;
    handoffConsumed.current = true;
    try {
      const value = consumePreparationOperationsHandoff();
      setHandoff(value);
      setHouseholdId(value?.household_id ?? "");
      setPersistenceNotes(value?.bundle.notes ?? "");
    } catch (error) {
      setHandoffError(messageOf(error));
    }
  }, []);

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const activeHouseholdId = householdId || households[0]?.id || "";
  const detailQ = useQuery({
    queryKey: ["households", activeHouseholdId, "detail"],
    queryFn: () => householdApi.get(activeHouseholdId),
    enabled: Boolean(activeHouseholdId),
  });
  const schedulesQ = useQuery({
    queryKey: ["preparation-operations", activeHouseholdId, "schedules"],
    queryFn: () => preparationOperationsApi.schedules(activeHouseholdId),
    enabled: Boolean(activeHouseholdId),
  });
  const calendarQ = useQuery({
    queryKey: [
      "preparation-operations",
      handoff?.household_id,
      "calendar",
      handoff?.bundle.calendar_version_id,
    ],
    queryFn: () =>
      preparationOperationsApi.calendar(
        handoff!.household_id,
        handoff!.bundle.calendar_version_id,
      ),
    enabled: Boolean(handoff),
  });
  const schedules = schedulesQ.data ?? [];
  const selectedSchedule = useMemo(() => {
    const requested = Number(selectedScheduleId);
    return schedules.find((value) => value.id === requested)
      ?? persisted
      ?? schedules[0]
      ?? null;
  }, [persisted, schedules, selectedScheduleId]);
  const eventsQ = useQuery({
    queryKey: [
      "preparation-operations",
      activeHouseholdId,
      "schedule-events",
      selectedSchedule?.id,
    ],
    queryFn: () =>
      preparationOperationsApi.events(activeHouseholdId, selectedSchedule!.id),
    enabled: Boolean(activeHouseholdId && selectedSchedule),
  });
  const role = detailQ.data?.role;
  const issues = useMemo(
    () => handoff ? reviewIssues(handoff, calendarQ.data ?? null) : [],
    [calendarQ.data, handoff],
  );
  const allConfirmed = Object.values(confirmations).every(Boolean);

  useEffect(() => {
    setConfirmations(EMPTY_CONFIRMATIONS);
    setPersisted(null);
  }, [handoff, calendarQ.data?.content_hash]);

  useEffect(() => {
    setTransitionReason("");
  }, [activeHouseholdId, selectedSchedule?.id, selectedSchedule?.version]);

  const invalidateSchedules = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["preparation-operations", activeHouseholdId, "schedules"],
      }),
      queryClient.invalidateQueries({
        queryKey: ["preparation-operations", activeHouseholdId, "coverage"],
      }),
    ]);
  };

  const persistMutation = useMutation({
    mutationFn: ({ key }: { key: string }) => {
      if (!handoff) throw new Error("No current operations handoff is available");
      if (activeHouseholdId !== handoff.household_id) {
        throw new Error("Selected household differs from the reviewed handoff");
      }
      if (issues.length) {
        throw new Error("Resolve every structured review issue before persistence");
      }
      if (!allConfirmed) {
        throw new Error("Complete every persistence confirmation");
      }
      return preparationOperationsApi.createSchedule(activeHouseholdId, {
        ...handoff.bundle,
        notes: persistenceNotes.trim() || null,
        idempotency_key: key,
      });
    },
    onSuccess: async (value) => {
      setPersisted(value);
      setSelectedScheduleId(String(value.id));
      await invalidateSchedules();
      toast({
        title: "Preparation schedule draft persisted",
        description: `Schedule #${value.id} version ${value.version} remains unapproved.`,
      });
    },
    onError: async (error) => {
      await invalidateSchedules();
      toast({
        title: "Schedule persistence rejected",
        description: messageOf(error),
        variant: "destructive",
      });
    },
  });

  const transitionMutation = useMutation({
    mutationFn: ({
      action,
      schedule,
      reason,
      idempotencyKey: key,
    }: TransitionInput) => {
      const normalized = reason.trim();
      if (!normalized) throw new Error("Enter a nonblank transition reason");
      const payload: ScheduleStateTransitionRequest = {
        expected_version: schedule.version,
        reason: normalized,
        idempotency_key: key,
        metadata: { source: "structured_preparation_operations_review" },
      };
      if (action === "approve") {
        return preparationOperationsApi.approve(activeHouseholdId, schedule.id, payload);
      }
      if (action === "invalidate") {
        return preparationOperationsApi.invalidate(activeHouseholdId, schedule.id, payload);
      }
      return preparationOperationsApi.cancel(activeHouseholdId, schedule.id, payload);
    },
    onSuccess: async (value) => {
      setPersisted(value);
      await invalidateSchedules();
      await queryClient.invalidateQueries({
        queryKey: [
          "preparation-operations",
          activeHouseholdId,
          "schedule-events",
          value.id,
        ],
      });
      toast({
        title: `Schedule ${value.status}`,
        description: `Schedule #${value.id} is now ${value.status}.`,
      });
    },
    onError: async (error) => {
      await invalidateSchedules();
      toast({
        title: "Schedule transition rejected",
        description: messageOf(error),
        variant: "destructive",
      });
    },
  });

  const pageError =
    handoffError
    ?? (householdsQ.error || detailQ.error || schedulesQ.error || calendarQ.error
      ? messageOf(householdsQ.error || detailQ.error || schedulesQ.error || calendarQ.error)
      : null);

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">Preparation operations</h1>
            <p className="text-sm text-muted-foreground">
              Review exact operational provenance structurally, persist a draft
              explicitly, and keep approval and execution as separate decisions.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/preparation/operations/execution">Task execution</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/preparation/operations/coverage">Coverage</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/preparation/operations/calendars/new">Calendar builder</Link>
            </Button>
          </div>
        </div>

        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Persistence is not approval or execution</AlertTitle>
          <AlertDescription>
            This page never edits deterministic bundle JSON, never persists on
            load, and never approves automatically. The server independently
            replays and verifies occurrence, profile, plan, calendar, request,
            response, and hash provenance.
          </AlertDescription>
        </Alert>

        {pageError && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Preparation operations unavailable</AlertTitle>
            <AlertDescription>{pageError}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Household scope</CardTitle>
            <CardDescription>
              A handoff is bound to one household; ordinary schedule history can
              still be inspected without a handoff.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 max-w-xl">
            <Label htmlFor="operations-household">Household</Label>
            <select
              id="operations-household"
              value={activeHouseholdId}
              disabled={Boolean(handoff)}
              onChange={(event) => setHouseholdId(event.target.value)}
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

        {!handoff && !handoffError && (
          <Alert>
            <FileLock2 className="h-4 w-4" />
            <AlertTitle>No current schedule handoff</AlertTitle>
            <AlertDescription>
              Compile a complete reviewed preparation pipeline and explicitly
              open operations review. Existing schedules remain available below.
            </AlertDescription>
          </Alert>
        )}

        {handoff && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <ClipboardCheck className="h-4 w-4" />
                  Structured persistence review
                </CardTitle>
                <CardDescription>
                  Handoff created {dateLabel(handoff.created_at)} · calendar #{handoff.bundle.calendar_version_id}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-md border p-3">
                    <p className="text-xs text-muted-foreground">Source plan</p>
                    <p className="font-medium">
                      {handoff.bundle.source_plan_id == null
                        ? "Not linked"
                        : `#${handoff.bundle.source_plan_id} v${handoff.bundle.source_plan_version}`}
                    </p>
                  </div>
                  <div className="rounded-md border p-3">
                    <p className="text-xs text-muted-foreground">Occurrences</p>
                    <p className="font-medium">
                      {handoff.bundle.occurrence_set.occurrences.length}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {shortHash(handoff.occurrence_set_hash_preview)}
                    </p>
                  </div>
                  <div className="rounded-md border p-3">
                    <p className="text-xs text-muted-foreground">Profiles</p>
                    <p className="font-medium">
                      {Object.keys(handoff.bundle.profile_versions).length}
                    </p>
                  </div>
                  <div className="rounded-md border p-3">
                    <p className="text-xs text-muted-foreground">Deterministic tasks</p>
                    <p className="font-medium">
                      {handoff.bundle.schedule_request.tasks.length}
                    </p>
                  </div>
                </div>

                {calendarQ.data && (
                  <div className="rounded-md border p-4 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-medium">
                          Calendar {calendarQ.data.calendar_version} · {calendarQ.data.timezone}
                        </p>
                        <p className="text-muted-foreground">
                          {calendarQ.data.horizon_minutes} minutes · {calendarQ.data.resources.length} resources · hash {shortHash(calendarQ.data.content_hash)}
                        </p>
                      </div>
                      <Badge variant={calendarQ.data.active ? "default" : "destructive"}>
                        {calendarQ.data.active ? "active reviewed" : "not active"}
                      </Badge>
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  <h3 className="font-medium">Occurrences and reviewed profiles</h3>
                  {handoff.bundle.occurrence_set.occurrences.map((occurrence) => (
                    <div key={occurrence.occurrence_id} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">{occurrence.occurrence_id}</p>
                      <p className="text-muted-foreground">
                        Recipe {occurrence.recipe_id} · {occurrence.servings} servings · finish minute {occurrence.required_finish_minute} · priority {occurrence.priority}
                      </p>
                      <p className="text-xs text-muted-foreground break-all">
                        {handoff.bundle.profile_versions[occurrence.recipe_id] ?? "Missing profile identity"}
                      </p>
                    </div>
                  ))}
                </div>

                <div className="space-y-3">
                  <h3 className="font-medium">Deterministic task DAG</h3>
                  {handoff.bundle.schedule_request.tasks.map((task) => {
                    const scheduled = handoff.bundle.schedule_response.scheduled.find(
                      (value) => value.task_id === task.task_id,
                    );
                    return (
                      <div key={task.task_id} className="rounded-md border p-3 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-medium">{task.task_id}</p>
                          <Badge variant={scheduled ? "outline" : "destructive"}>
                            {scheduled
                              ? `minute ${scheduled.start_minute}–${scheduled.finish_minute}`
                              : "not scheduled"}
                          </Badge>
                        </div>
                        <p className="text-muted-foreground">
                          Duration {task.duration_minutes} · deadline {task.latest_finish_minute ?? "none"} · dependencies {task.dependencies.join(", ") || "none"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Resources {JSON.stringify(task.resource_demands)}
                        </p>
                      </div>
                    );
                  })}
                </div>

                {issues.length > 0 && (
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertTitle>Structured review blocked</AlertTitle>
                    <AlertDescription>
                      <ul className="list-disc space-y-1 pl-5">
                        {issues.map((issue) => <li key={issue}>{issue}</li>)}
                      </ul>
                    </AlertDescription>
                  </Alert>
                )}

                <fieldset className="space-y-3 rounded-md border p-4">
                  <legend className="px-1 font-medium">Required confirmations</legend>
                  {[
                    ["source", "I reviewed the exact source plan, occurrence document, serving counts, deadlines, and profile identities."],
                    ["calendar", "I reviewed the active calendar, timezone, horizon, resources, capacities, and availability windows."],
                    ["tasks", "I reviewed every task, dependency, duration, demand, deadline, and deterministic scheduled time."],
                    ["boundary", "I understand persistence creates only a draft and does not prove execution, appliance state, temperature, or food safety."],
                  ].map(([key, label]) => (
                    <div key={key} className="flex items-start gap-3">
                      <Checkbox
                        id={`operations-confirm-${key}`}
                        checked={confirmations[key as keyof ConfirmationState]}
                        onCheckedChange={(checked) =>
                          setConfirmations((current) => ({
                            ...current,
                            [key]: checked === true,
                          }))
                        }
                      />
                      <Label htmlFor={`operations-confirm-${key}`} className="font-normal leading-5">
                        {label}
                      </Label>
                    </div>
                  ))}
                </fieldset>

                <div className="space-y-1">
                  <Label htmlFor="operations-persistence-notes">Persistence notes</Label>
                  <Textarea
                    id="operations-persistence-notes"
                    value={persistenceNotes}
                    onChange={(event) => setPersistenceNotes(event.target.value)}
                    placeholder="Optional human review notes retained with the draft"
                  />
                </div>

                <details className="rounded-md border p-4">
                  <summary className="cursor-pointer font-medium flex items-center gap-2">
                    <FileCode2 className="h-4 w-4" />
                    Read-only canonical bundle JSON
                  </summary>
                  <pre
                    aria-label="Schedule bundle JSON"
                    className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-all rounded bg-muted p-3 text-xs"
                  >
                    {JSON.stringify(handoff.bundle, null, 2)}
                  </pre>
                </details>

                <Button
                  type="button"
                  disabled={
                    !canEdit(role)
                    || issues.length > 0
                    || !allConfirmed
                    || persistMutation.isPending
                  }
                  onClick={() =>
                    persistMutation.mutate({
                      key: idempotencyKey("persist-preparation-schedule"),
                    })
                  }
                >
                  <FileLock2 className="mr-2 h-4 w-4" />
                  Persist reviewed schedule draft
                </Button>
                {!canEdit(role) && (
                  <p className="text-sm text-muted-foreground">
                    Editor or owner access is required to persist a draft.
                  </p>
                )}
              </CardContent>
            </Card>
          </>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarRange className="h-4 w-4" />
              Persisted schedule lifecycle
            </CardTitle>
            <CardDescription>
              Approval remains owner-only. Approved work proceeds to explicit task execution.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {schedules.length === 0 && !schedulesQ.isLoading && (
              <p className="text-sm text-muted-foreground">No schedules persisted.</p>
            )}
            {schedules.length > 0 && (
              <div className="space-y-1 max-w-xl">
                <Label htmlFor="operations-schedule">Schedule</Label>
                <select
                  id="operations-schedule"
                  value={selectedSchedule?.id ?? ""}
                  onChange={(event) => setSelectedScheduleId(event.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  {schedules.map((schedule) => (
                    <option key={schedule.id} value={schedule.id}>
                      #{schedule.id} · {schedule.status} · version {schedule.version}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {selectedSchedule && (
              <div className="space-y-4 rounded-md border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">Schedule #{selectedSchedule.id}</p>
                    <p className="text-sm text-muted-foreground">
                      Version {selectedSchedule.version} · replay {selectedSchedule.replay_status ?? "unknown"}
                    </p>
                  </div>
                  <Badge variant={statusVariant(selectedSchedule.status)} className="capitalize">
                    {selectedSchedule.status}
                  </Badge>
                </div>
                <div className="grid gap-2 text-sm sm:grid-cols-2">
                  <p>Calendar hash: {shortHash(selectedSchedule.calendar_content_hash)}</p>
                  <p>Schedule hash: {shortHash(selectedSchedule.schedule_hash)}</p>
                  <p>Occurrence hash: {shortHash(selectedSchedule.occurrence_set_hash)}</p>
                  <p>Created: {dateLabel(selectedSchedule.created_at)}</p>
                  <p>
                    Source plan: {selectedSchedule.source_plan_id == null
                      ? "not linked"
                      : `#${selectedSchedule.source_plan_id} v${selectedSchedule.source_plan_version}`}
                  </p>
                  <p>Tasks: {selectedSchedule.schedule.scheduled.length}</p>
                </div>

                {selectedSchedule.status === "approved" && (
                  <Button asChild>
                    <Link to="/preparation/operations/execution">
                      <PlayCircle className="mr-2 h-4 w-4" />
                      Open task execution
                    </Link>
                  </Button>
                )}

                {(selectedSchedule.status === "draft" || selectedSchedule.status === "approved") && (
                  <div className="space-y-3 border-t pt-4">
                    <div className="space-y-1">
                      <Label htmlFor="operations-transition-reason">Transition reason</Label>
                      <Textarea
                        id="operations-transition-reason"
                        value={transitionReason}
                        onChange={(event) => setTransitionReason(event.target.value)}
                        placeholder="Required human reason"
                      />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {selectedSchedule.status === "draft" && (
                        <Button
                          type="button"
                          disabled={!isOwner(role) || transitionMutation.isPending}
                          onClick={() =>
                            transitionMutation.mutate({
                              action: "approve",
                              schedule: selectedSchedule,
                              reason: transitionReason,
                              idempotencyKey: idempotencyKey("approve-preparation-schedule"),
                            })
                          }
                        >
                          <CheckCircle2 className="mr-2 h-4 w-4" />
                          Approve schedule
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="outline"
                        disabled={!canEdit(role) || transitionMutation.isPending}
                        onClick={() =>
                          transitionMutation.mutate({
                            action: "cancel",
                            schedule: selectedSchedule,
                            reason: transitionReason,
                            idempotencyKey: idempotencyKey("cancel-preparation-schedule"),
                          })
                        }
                      >
                        <XCircle className="mr-2 h-4 w-4" />
                        Cancel schedule
                      </Button>
                      <Button
                        type="button"
                        variant="destructive"
                        disabled={!isOwner(role) || transitionMutation.isPending}
                        onClick={() =>
                          transitionMutation.mutate({
                            action: "invalidate",
                            schedule: selectedSchedule,
                            reason: transitionReason,
                            idempotencyKey: idempotencyKey("invalidate-preparation-schedule"),
                          })
                        }
                      >
                        <AlertTriangle className="mr-2 h-4 w-4" />
                        Invalidate schedule
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {selectedSchedule && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <History className="h-4 w-4" />
                Append-only schedule events
              </CardTitle>
              <CardDescription>
                Lifecycle evidence is separate from task execution evidence.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(eventsQ.data ?? []).map((event) => (
                <div key={event.id} className="rounded-md border p-3 text-sm">
                  <div className="flex flex-wrap justify-between gap-2">
                    <p className="font-medium capitalize">{event.event_type}</p>
                    <Badge variant="outline">
                      {event.from_status ?? "none"} → {event.to_status}
                    </Badge>
                  </div>
                  <p>{event.reason}</p>
                  <p className="text-xs text-muted-foreground">
                    Actor {event.actor_user_id} · {dateLabel(event.created_at)}
                  </p>
                </div>
              ))}
              {!eventsQ.isLoading && (eventsQ.data ?? []).length === 0 && (
                <p className="text-sm text-muted-foreground">No schedule events found.</p>
              )}
            </CardContent>
          </Card>
        )}

        <Alert>
          <Link2 className="h-4 w-4" />
          <AlertTitle>Execution evidence remains separate</AlertTitle>
          <AlertDescription>
            A persisted or approved schedule is not proof of task execution.
            Start, completion, skip, and deviation claims are recorded only in
            the dedicated task execution workspace.
          </AlertDescription>
        </Alert>
      </div>
    </AppLayout>
  );
}
