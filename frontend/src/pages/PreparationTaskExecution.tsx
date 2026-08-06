import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDot,
  ClipboardCheck,
  History,
  Play,
  ShieldAlert,
  SkipForward,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { householdApi, type HouseholdRole } from "@/lib/platformApi";
import {
  preparationOperationsApi,
  type PreparationTaskExecutionEventType,
  type PreparationTaskExecutionTaskView,
} from "@/lib/preparationOperationsApi";
import {
  preparationTaskExecutionEligibilityApi,
  type PreparationTaskExecutionEligibilityView,
} from "@/lib/preparationTaskExecutionEligibilityApi";

interface TaskDraft {
  actualMinute: string;
  reason: string;
  notes: string;
}

interface TaskMutationVariables {
  task: PreparationTaskExecutionTaskView;
  eventType: PreparationTaskExecutionEventType;
  idempotencyKey: string;
}

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The execution request could not be completed";
}

function canEdit(role?: HouseholdRole | null): boolean {
  return role === "owner" || role === "editor";
}

function eventKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function taskDraftKey(scheduleId: number, taskId: string): string {
  return `${scheduleId}:${taskId}`;
}

function stateLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function defaultMinute(task: PreparationTaskExecutionTaskView): number {
  if (task.state === "in_progress") return task.task.finish_minute;
  return task.task.start_minute;
}

function eligibilityTitle(value: PreparationTaskExecutionEligibilityView): string {
  if (value.reason_code === "source_schedule_has_accepted_replacement") {
    return "Execution blocked by accepted replacement";
  }
  if (value.schedule_status === "completed") return "Completed schedule is read-only";
  return "Schedule is not execution eligible";
}

function eligibilityDescription(
  value: PreparationTaskExecutionEligibilityView,
): string {
  if (value.reason_code === "source_schedule_has_accepted_replacement") {
    return (
      `Source schedule #${value.schedule_id} was superseded by accepted ` +
      `repair proposal #${value.accepted_proposal_id}, acceptance ` +
      `#${value.acceptance_id}, and replacement schedule ` +
      `#${value.replacement_schedule_id}. Source history remains readable, ` +
      "but new task events and schedule completion are prohibited."
    );
  }
  return (
    `Schedule #${value.schedule_id} has status ${value.schedule_status}. ` +
    "Only an approved schedule without an accepted replacement can receive new task events."
  );
}

export default function PreparationTaskExecutionPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [householdId, setHouseholdId] = useState("");
  const [scheduleId, setScheduleId] = useState("");
  const [taskDrafts, setTaskDrafts] = useState<Record<string, TaskDraft>>({});
  const [completionReason, setCompletionReason] = useState(
    "Every deterministic task was explicitly completed or skipped",
  );

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
    queryKey: ["preparation-operations", activeHouseholdId, "execution-schedules"],
    queryFn: () =>
      preparationOperationsApi.schedules(activeHouseholdId, [
        "approved",
        "completed",
      ]),
    enabled: Boolean(activeHouseholdId),
  });
  const schedules = schedulesQ.data ?? [];
  const activeScheduleId = Number(scheduleId) || schedules[0]?.id || 0;
  const overviewQ = useQuery({
    queryKey: [
      "preparation-operations",
      activeHouseholdId,
      "task-execution",
      activeScheduleId,
    ],
    queryFn: () =>
      preparationOperationsApi.taskExecution(
        activeHouseholdId,
        activeScheduleId,
      ),
    enabled: Boolean(activeHouseholdId && activeScheduleId),
  });
  const eligibilityQ = useQuery({
    queryKey: [
      "preparation-operations",
      activeHouseholdId,
      "task-execution-eligibility",
      activeScheduleId,
    ],
    queryFn: () =>
      preparationTaskExecutionEligibilityApi.get(
        activeHouseholdId,
        activeScheduleId,
      ),
    enabled: Boolean(activeHouseholdId && activeScheduleId),
  });
  const overview = overviewQ.data;
  const eligibility = eligibilityQ.data;
  const role = detailQ.data?.role;

  useEffect(() => {
    setScheduleId("");
    setTaskDrafts({});
  }, [activeHouseholdId]);

  useEffect(() => {
    if (!overview) return;
    setTaskDrafts((current) => {
      const next: Record<string, TaskDraft> = {};
      for (const task of overview.tasks) {
        const key = taskDraftKey(overview.schedule.id, task.task.task_id);
        next[key] = current[key] ?? {
          actualMinute: String(defaultMinute(task)),
          reason: "",
          notes: "",
        };
      }
      return next;
    });
  }, [overview]);

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: [
          "preparation-operations",
          activeHouseholdId,
          "execution-schedules",
        ],
      }),
      queryClient.invalidateQueries({
        queryKey: [
          "preparation-operations",
          activeHouseholdId,
          "task-execution",
          activeScheduleId,
        ],
      }),
      queryClient.invalidateQueries({
        queryKey: [
          "preparation-operations",
          activeHouseholdId,
          "task-execution-eligibility",
          activeScheduleId,
        ],
      }),
      queryClient.invalidateQueries({
        queryKey: ["preparation-operations", activeHouseholdId, "schedules"],
      }),
    ]);
  };

  const assertExecutionEligible = () => {
    if (!eligibility) {
      throw new Error("Execution eligibility has not been verified yet");
    }
    if (!eligibility.eligible) {
      throw new Error(eligibilityDescription(eligibility));
    }
  };

  const taskMutation = useMutation({
    mutationFn: ({
      task,
      eventType,
      idempotencyKey,
    }: TaskMutationVariables) => {
      if (!overview) throw new Error("Select an execution schedule");
      assertExecutionEligible();
      const key = taskDraftKey(overview.schedule.id, task.task.task_id);
      const draft = taskDrafts[key];
      const actualMinute = Number(draft?.actualMinute);
      if (
        !Number.isInteger(actualMinute)
        || actualMinute < 0
        || actualMinute > overview.schedule.schedule.horizon_minutes
      ) {
        throw new Error(
          `Actual minute must be an integer from 0 to ${overview.schedule.schedule.horizon_minutes}`,
        );
      }
      const plannedMinute =
        eventType === "started"
          ? task.task.start_minute
          : eventType === "completed"
            ? task.task.finish_minute
            : actualMinute;
      const deviation =
        eventType === "skipped" ? 0 : actualMinute - plannedMinute;
      const reason = draft?.reason.trim() || null;
      if ((eventType === "skipped" || deviation !== 0) && !reason) {
        throw new Error(
          "Enter a reason for a skipped task or timing deviation",
        );
      }
      const payload = {
        expected_schedule_version: overview.schedule.version,
        actual_minute: actualMinute,
        reason,
        notes: draft?.notes.trim() || null,
        idempotency_key: idempotencyKey,
        metadata: { source: "preparation_task_execution_ui" },
      };
      const handlers = {
        started: preparationOperationsApi.startTask,
        completed: preparationOperationsApi.completeTask,
        skipped: preparationOperationsApi.skipTask,
      };
      return handlers[eventType](
        activeHouseholdId,
        overview.schedule.id,
        task.task.task_id,
        payload,
      );
    },
    onSuccess: async (value) => {
      await invalidate();
      const key = taskDraftKey(value.schedule.id, value.task.task.task_id);
      setTaskDrafts((current) => ({
        ...current,
        [key]: {
          actualMinute: String(defaultMinute(value.task)),
          reason: "",
          notes: "",
        },
      }));
      toast({
        title: `Task ${stateLabel(value.task.state)}`,
        description: `${value.task.task.task_id} · schedule version ${value.schedule.version}`,
      });
    },
    onError: (error) =>
      toast({
        title: "Task execution event rejected",
        description: messageOf(error),
        variant: "destructive",
      }),
  });

  const completeSchedule = useMutation({
    mutationFn: () => {
      if (!overview) throw new Error("Select an execution schedule");
      assertExecutionEligible();
      const reason = completionReason.trim();
      if (!reason) throw new Error("Enter a schedule completion reason");
      return preparationOperationsApi.complete(
        activeHouseholdId,
        overview.schedule.id,
        {
          expected_version: overview.schedule.version,
          reason,
          idempotency_key: eventKey("schedule-complete"),
          metadata: { source: "preparation_task_execution_ui" },
        },
      );
    },
    onSuccess: async (schedule) => {
      await invalidate();
      toast({
        title: "Schedule completed",
        description: `Schedule #${schedule.id} is terminal with explicit task evidence.`,
      });
    },
    onError: (error) =>
      toast({
        title: "Schedule completion rejected",
        description: messageOf(error),
        variant: "destructive",
      }),
  });

  const selectedSchedule = useMemo(
    () => schedules.find((value) => value.id === activeScheduleId) ?? null,
    [activeScheduleId, schedules],
  );
  const replacementSelectable = Boolean(
    eligibility?.replacement_schedule_id
      && schedules.some(
        (value) => value.id === eligibility.replacement_schedule_id,
      ),
  );
  const pageError =
    householdsQ.error
    || detailQ.error
    || schedulesQ.error
    || overviewQ.error
    || eligibilityQ.error;

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">Preparation task execution</h1>
            <p className="text-sm text-muted-foreground">
              Record only explicit household confirmations against the immutable
              deterministic schedule. Nothing starts, completes, or skips
              automatically.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/preparation/operations">Preparation operations</Link>
          </Button>
        </div>

        <Alert>
          <ClipboardCheck className="h-4 w-4" />
          <AlertTitle>Human-confirmed evidence only</AlertTitle>
          <AlertDescription>
            Actual minutes are relative to the reviewed schedule horizon. This
            ledger does not infer presence, observe appliances, verify cooking,
            measure temperature, or declare food safe.
          </AlertDescription>
        </Alert>

        {pageError && (
          <Alert variant="destructive" role="alert">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Execution workspace unavailable</AlertTitle>
            <AlertDescription>{messageOf(pageError)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Execution scope</CardTitle>
            <CardDescription>
              Select one household and an approved or completed schedule.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="execution-household">Household</Label>
              <select
                id="execution-household"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={activeHouseholdId}
                onChange={(event) => setHouseholdId(event.target.value)}
              >
                {households.map((household) => (
                  <option key={household.id} value={household.id}>
                    {household.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="execution-schedule">Schedule</Label>
              <select
                id="execution-schedule"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={activeScheduleId || ""}
                onChange={(event) => setScheduleId(event.target.value)}
              >
                {schedules.map((schedule) => (
                  <option key={schedule.id} value={schedule.id}>
                    #{schedule.id} · {schedule.status} · version {schedule.version}
                  </option>
                ))}
              </select>
            </div>
            {selectedSchedule && (
              <div className="md:col-span-2 flex flex-wrap gap-2">
                <Badge className="capitalize">{selectedSchedule.status}</Badge>
                <Badge variant="outline">version {selectedSchedule.version}</Badge>
                <Badge variant="outline">
                  {selectedSchedule.schedule.scheduled.length} tasks
                </Badge>
                <Badge variant="outline" className="capitalize">
                  {role ?? "no role"}
                </Badge>
                {eligibility && (
                  <Badge variant={eligibility.eligible ? "default" : "destructive"}>
                    {eligibility.eligible ? "execution eligible" : "execution blocked"}
                  </Badge>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {eligibilityQ.isLoading && activeScheduleId > 0 && (
          <Alert aria-live="polite">
            <ShieldAlert className="h-4 w-4" />
            <AlertTitle>Verifying execution eligibility</AlertTitle>
            <AlertDescription>
              Task controls remain disabled until the authoritative eligibility
              evidence is loaded.
            </AlertDescription>
          </Alert>
        )}

        {eligibility && !eligibility.eligible && (
          <Alert
            variant={
              eligibility.reason_code === "source_schedule_has_accepted_replacement"
                ? "destructive"
                : "default"
            }
            role="status"
          >
            <ShieldAlert className="h-4 w-4" />
            <AlertTitle>{eligibilityTitle(eligibility)}</AlertTitle>
            <AlertDescription className="space-y-3">
              <p>{eligibilityDescription(eligibility)}</p>
              {eligibility.reason_code === "source_schedule_has_accepted_replacement" && (
                <div className="flex flex-wrap gap-2">
                  {replacementSelectable ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        setScheduleId(String(eligibility.replacement_schedule_id))
                      }
                    >
                      Open replacement schedule
                    </Button>
                  ) : (
                    <Button asChild size="sm" variant="outline">
                      <Link to="/preparation/operations">
                        Review replacement schedule
                      </Link>
                    </Button>
                  )}
                  <Badge variant="outline">
                    replacement status {eligibility.replacement_schedule_status}
                  </Badge>
                  <Badge variant="outline">
                    source events {eligibility.task_event_count}
                  </Badge>
                </div>
              )}
            </AlertDescription>
          </Alert>
        )}

        {!schedulesQ.isLoading && schedules.length === 0 && activeHouseholdId && (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>No approved execution schedule</AlertTitle>
            <AlertDescription>
              Persist and approve a replayable preparation schedule before
              recording task execution.
            </AlertDescription>
          </Alert>
        )}

        {overview && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Execution progress</CardTitle>
                <CardDescription>
                  Schedule #{overview.schedule.id} · optimistic version {overview.schedule.version}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <progress
                  className="h-3 w-full"
                  value={overview.terminal_count}
                  max={overview.tasks.length}
                  aria-label="Terminal preparation tasks"
                />
                <div className="grid gap-3 sm:grid-cols-5">
                  {[
                    ["Planned", overview.planned_count],
                    ["In progress", overview.in_progress_count],
                    ["Completed", overview.completed_count],
                    ["Skipped", overview.skipped_count],
                    ["Remaining", overview.remaining_count],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">{label}</p>
                      <p className="text-xl font-semibold">{value}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <div className="space-y-4">
              {overview.tasks.map((taskView) => {
                const task = taskView.task;
                const draftKey = taskDraftKey(overview.schedule.id, task.task_id);
                const draft = taskDrafts[draftKey] ?? {
                  actualMinute: String(defaultMinute(taskView)),
                  reason: "",
                  notes: "",
                };
                const mutable =
                  overview.schedule.status === "approved"
                  && canEdit(role)
                  && eligibility?.eligible === true;
                const fieldSuffix = `${overview.schedule.id}-${task.task_id}`;
                return (
                  <Card key={draftKey}>
                    <CardHeader>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <CardTitle className="text-base">{task.task_id}</CardTitle>
                          <CardDescription>
                            Planned minute {task.start_minute}–{task.finish_minute} · {task.duration_minutes} minutes
                          </CardDescription>
                        </div>
                        <Badge
                          variant={
                            taskView.state === "completed"
                              ? "default"
                              : taskView.state === "skipped"
                                ? "destructive"
                                : "outline"
                          }
                          className="capitalize"
                        >
                          {stateLabel(taskView.state)}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="flex flex-wrap gap-2 text-xs">
                        <Badge variant="outline">
                          Dependencies: {task.dependencies.join(", ") || "none"}
                        </Badge>
                        <Badge variant="outline">
                          Resources: {JSON.stringify(task.resource_demands)}
                        </Badge>
                        {taskView.started_actual_minute !== null && (
                          <Badge variant="outline">
                            Started at {taskView.started_actual_minute}
                          </Badge>
                        )}
                        {taskView.completed_actual_minute !== null && (
                          <Badge variant="outline">
                            Completed at {taskView.completed_actual_minute}
                          </Badge>
                        )}
                        {taskView.skipped_actual_minute !== null && (
                          <Badge variant="outline">
                            Skipped at {taskView.skipped_actual_minute}
                          </Badge>
                        )}
                      </div>

                      {(taskView.state === "planned" || taskView.state === "in_progress") && (
                        <div className="grid gap-3 md:grid-cols-3">
                          <div className="space-y-1">
                            <Label htmlFor={`actual-${fieldSuffix}`}>
                              Actual horizon minute
                            </Label>
                            <Input
                              id={`actual-${fieldSuffix}`}
                              type="number"
                              min="0"
                              max={overview.schedule.schedule.horizon_minutes}
                              step="1"
                              value={draft.actualMinute}
                              disabled={!mutable || taskMutation.isPending}
                              onChange={(event) =>
                                setTaskDrafts((current) => ({
                                  ...current,
                                  [draftKey]: {
                                    ...draft,
                                    actualMinute: event.target.value,
                                  },
                                }))
                              }
                            />
                          </div>
                          <div className="space-y-1 md:col-span-2">
                            <Label htmlFor={`reason-${fieldSuffix}`}>
                              Skip or deviation reason
                            </Label>
                            <Input
                              id={`reason-${fieldSuffix}`}
                              value={draft.reason}
                              disabled={!mutable || taskMutation.isPending}
                              placeholder="Required for skips or any timing difference"
                              onChange={(event) =>
                                setTaskDrafts((current) => ({
                                  ...current,
                                  [draftKey]: {
                                    ...draft,
                                    reason: event.target.value,
                                  },
                                }))
                              }
                            />
                          </div>
                          <div className="space-y-1 md:col-span-3">
                            <Label htmlFor={`notes-${fieldSuffix}`}>Notes</Label>
                            <Textarea
                              id={`notes-${fieldSuffix}`}
                              value={draft.notes}
                              disabled={!mutable || taskMutation.isPending}
                              placeholder="Optional human-entered execution notes"
                              onChange={(event) =>
                                setTaskDrafts((current) => ({
                                  ...current,
                                  [draftKey]: {
                                    ...draft,
                                    notes: event.target.value,
                                  },
                                }))
                              }
                            />
                          </div>
                          <div className="md:col-span-3 flex flex-wrap gap-2">
                            {taskView.state === "planned" && (
                              <Button
                                type="button"
                                disabled={!mutable || taskMutation.isPending}
                                onClick={() =>
                                  taskMutation.mutate({
                                    task: taskView,
                                    eventType: "started",
                                    idempotencyKey: eventKey("task-started"),
                                  })
                                }
                              >
                                <Play className="mr-2 h-4 w-4" />
                                Confirm start
                              </Button>
                            )}
                            {taskView.state === "in_progress" && (
                              <Button
                                type="button"
                                disabled={!mutable || taskMutation.isPending}
                                onClick={() =>
                                  taskMutation.mutate({
                                    task: taskView,
                                    eventType: "completed",
                                    idempotencyKey: eventKey("task-completed"),
                                  })
                                }
                              >
                                <CheckCircle2 className="mr-2 h-4 w-4" />
                                Confirm completion
                              </Button>
                            )}
                            <Button
                              type="button"
                              variant="outline"
                              disabled={!mutable || taskMutation.isPending}
                              onClick={() =>
                                taskMutation.mutate({
                                  task: taskView,
                                  eventType: "skipped",
                                  idempotencyKey: eventKey("task-skipped"),
                                })
                              }
                            >
                              <SkipForward className="mr-2 h-4 w-4" />
                              Confirm skip
                            </Button>
                          </div>
                        </div>
                      )}

                      {taskView.terminal_reason && (
                        <Alert variant={taskView.state === "skipped" ? "destructive" : "default"}>
                          <CircleDot className="h-4 w-4" />
                          <AlertTitle>Terminal reason</AlertTitle>
                          <AlertDescription>{taskView.terminal_reason}</AlertDescription>
                        </Alert>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            {overview.schedule.status === "approved" && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Complete schedule</CardTitle>
                  <CardDescription>
                    Available only after every deterministic task is explicitly completed or skipped.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <Label htmlFor="execution-completion-reason">Completion reason</Label>
                    <Textarea
                      id="execution-completion-reason"
                      value={completionReason}
                      disabled={
                        !canEdit(role)
                        || eligibility?.eligible !== true
                        || completeSchedule.isPending
                      }
                      onChange={(event) => setCompletionReason(event.target.value)}
                    />
                  </div>
                  <Button
                    type="button"
                    disabled={
                      !canEdit(role)
                      || eligibility?.eligible !== true
                      || overview.remaining_count !== 0
                      || completeSchedule.isPending
                    }
                    onClick={() => completeSchedule.mutate()}
                  >
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                    Complete schedule
                  </Button>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <History className="h-4 w-4" />
                  Append-only task event history
                </CardTitle>
                <CardDescription>
                  Planned and actual horizon minutes remain visible with every actor-confirmed transition.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {overview.events.length === 0 && (
                  <p className="text-sm text-muted-foreground">No task events recorded.</p>
                )}
                {overview.events.map((event) => (
                  <div key={event.id} className="rounded-md border p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-medium">
                        {event.task_id} · {event.event_type}
                      </p>
                      <Badge variant="outline">
                        version {event.schedule_version_before}→{event.schedule_version_after}
                      </Badge>
                    </div>
                    <p className="text-muted-foreground">
                      {event.from_state} → {event.to_state} · actual minute {event.actual_minute} · deviation {event.deviation_minutes >= 0 ? "+" : ""}{event.deviation_minutes}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Actor {event.actor_user_id} · {new Date(event.created_at).toLocaleString()}
                    </p>
                    {event.reason && <p className="mt-1">Reason: {event.reason}</p>}
                    {event.notes && <p className="mt-1">Notes: {event.notes}</p>}
                  </div>
                ))}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </AppLayout>
  );
}