import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock3,
  FileClock,
  FileWarning,
  History,
  LockKeyhole,
  RefreshCw,
  ShieldAlert,
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
import { Textarea } from "@/components/ui/textarea";
import { householdApi } from "@/lib/platformApi";
import {
  preparationOperationsApi,
  type PersistedPreparationScheduleView,
  type PreparationScheduleRequest,
  type ResourceCalendarVersionView,
} from "@/lib/preparationOperationsApi";
import {
  preparationRepairProposalApi,
  type PreparationRepairProposalCreateRequest,
  type PreparationRepairProposalStatus,
  type PreparationRepairProposalView,
} from "@/lib/preparationRepairProposalApi";

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The repair proposal request could not be completed";
}

function idempotencyKey(prefix: string): string {
  const value = globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}:${value}`;
}

function shortHash(value: string): string {
  return `${value.slice(0, 12)}…${value.slice(-6)}`;
}

function parseRequest(raw: string): PreparationScheduleRequest {
  const parsed = JSON.parse(raw) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Revised request must be a JSON object");
  }
  const candidate = parsed as Partial<PreparationScheduleRequest>;
  if (!Number.isInteger(candidate.horizon_minutes) || !candidate.horizon_minutes) {
    throw new Error("Revised request requires a positive integer horizon_minutes");
  }
  if (!Number.isInteger(candidate.granularity_minutes) || !candidate.granularity_minutes) {
    throw new Error("Revised request requires a positive integer granularity_minutes");
  }
  if (!Array.isArray(candidate.resources) || !Array.isArray(candidate.tasks)) {
    throw new Error("Revised request requires resources and tasks arrays");
  }
  return candidate as PreparationScheduleRequest;
}

function proposalOutcomeSummary(proposal: PreparationRepairProposalView): string {
  const result = proposal.repair_result;
  return [
    `${result.preserved_task_ids.length} preserved`,
    `${result.moved_tasks.length} moved`,
    `${result.added_task_ids.length} added`,
    `${result.removed_task_ids.length} removed`,
    `${result.unscheduled_task_ids.length} unresolved`,
  ].join(" · ");
}

function currentRoleCanEdit(role?: string): boolean {
  return role === "owner" || role === "editor";
}

export default function PreparationRepairProposalsPage() {
  const queryClient = useQueryClient();
  const [householdId, setHouseholdId] = useState("");
  const [sourceScheduleId, setSourceScheduleId] = useState("");
  const [targetCalendarId, setTargetCalendarId] = useState("");
  const [revisedRequestRaw, setRevisedRequestRaw] = useState("");
  const [immutableTaskIds, setImmutableTaskIds] = useState<string[]>([]);
  const [strategy, setStrategy] = useState<
    "greedy_min_change" | "bounded_exact_min_change"
  >("greedy_min_change");
  const [notes, setNotes] = useState("");
  const [acknowledgeNonAcceptance, setAcknowledgeNonAcceptance] = useState(false);
  const [acknowledgeNonPersistence, setAcknowledgeNonPersistence] = useState(false);
  const [createKey, setCreateKey] = useState(() => idempotencyKey("repair-proposal"));
  const [selectedProposalId, setSelectedProposalId] = useState(0);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectKey, setRejectKey] = useState(() => idempotencyKey("repair-reject"));

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const activeHouseholdId = householdId || households[0]?.id || "";
  const activeHousehold = households.find((value) => value.id === activeHouseholdId);
  const canEdit = currentRoleCanEdit(activeHousehold?.current_role);

  const schedulesQ = useQuery({
    queryKey: ["preparation-operations", activeHouseholdId, "proposal-sources"],
    queryFn: () =>
      preparationOperationsApi.schedules(activeHouseholdId, ["draft", "approved"]),
    enabled: Boolean(activeHouseholdId),
  });
  const calendarsQ = useQuery({
    queryKey: ["preparation-operations", activeHouseholdId, "proposal-calendars"],
    queryFn: () => preparationOperationsApi.calendars(activeHouseholdId),
    enabled: Boolean(activeHouseholdId),
  });
  const proposalsQ = useQuery({
    queryKey: ["preparation-repair-proposals", activeHouseholdId],
    queryFn: () => preparationRepairProposalApi.list(activeHouseholdId),
    enabled: Boolean(activeHouseholdId),
  });

  const schedules = useMemo(
    () =>
      (schedulesQ.data ?? []).filter(
        (value) =>
          value.replay_status === "replayable" &&
          value.schedule_request !== null &&
          value.schedule.unscheduled.length === 0,
      ),
    [schedulesQ.data],
  );
  const calendars = useMemo(
    () =>
      (calendarsQ.data ?? []).filter(
        (value) => value.active && value.evidence_status === "reviewed",
      ),
    [calendarsQ.data],
  );
  const proposals = proposalsQ.data ?? [];
  const activeScheduleId = Number(sourceScheduleId) || schedules[0]?.id || 0;
  const activeCalendarId = Number(targetCalendarId) || calendars[0]?.id || 0;
  const sourceSchedule = schedules.find((value) => value.id === activeScheduleId);
  const targetCalendar = calendars.find((value) => value.id === activeCalendarId);
  const selectedProposal = proposals.find((value) => value.id === selectedProposalId)
    ?? proposals[0];

  const eventsQ = useQuery({
    queryKey: [
      "preparation-repair-proposals",
      activeHouseholdId,
      selectedProposal?.id,
      "events",
    ],
    queryFn: () =>
      preparationRepairProposalApi.events(
        activeHouseholdId,
        selectedProposal!.id,
      ),
    enabled: Boolean(activeHouseholdId && selectedProposal?.id),
  });

  useEffect(() => {
    setSourceScheduleId("");
    setTargetCalendarId("");
    setSelectedProposalId(0);
    setRevisedRequestRaw("");
    setImmutableTaskIds([]);
    setCreateKey(idempotencyKey("repair-proposal"));
    setRejectKey(idempotencyKey("repair-reject"));
  }, [activeHouseholdId]);

  useEffect(() => {
    if (!sourceSchedule?.schedule_request) {
      setRevisedRequestRaw("");
      setImmutableTaskIds([]);
      return;
    }
    setRevisedRequestRaw(
      JSON.stringify(sourceSchedule.schedule_request, null, 2),
    );
    setImmutableTaskIds([]);
    setCreateKey(idempotencyKey("repair-proposal"));
  }, [sourceSchedule?.id, sourceSchedule?.schedule_request]);

  useEffect(() => {
    if (selectedProposal) {
      setSelectedProposalId(selectedProposal.id);
    }
  }, [selectedProposal?.id]);

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!sourceSchedule || !targetCalendar) {
        throw new Error("Select a source schedule and active reviewed calendar");
      }
      const payload: PreparationRepairProposalCreateRequest = {
        source_schedule_id: sourceSchedule.id,
        expected_source_version: sourceSchedule.version,
        target_calendar_version_id: targetCalendar.id,
        revised_request: parseRequest(revisedRequestRaw),
        immutable_task_ids: immutableTaskIds,
        strategy,
        notes: notes.trim() || null,
        acknowledge_non_acceptance: true,
        acknowledge_non_persistence: true,
        idempotency_key: createKey,
      };
      return preparationRepairProposalApi.create(activeHouseholdId, payload);
    },
    onSuccess: async (proposal) => {
      setSelectedProposalId(proposal.id);
      await queryClient.invalidateQueries({
        queryKey: ["preparation-repair-proposals", activeHouseholdId],
      });
      setCreateKey(idempotencyKey("repair-proposal"));
      setAcknowledgeNonAcceptance(false);
      setAcknowledgeNonPersistence(false);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: async () => {
      if (!selectedProposal) throw new Error("Select a proposal");
      if (!rejectReason.trim()) throw new Error("A rejection reason is required");
      return preparationRepairProposalApi.reject(
        activeHouseholdId,
        selectedProposal.id,
        {
          expected_version: selectedProposal.version,
          reason: rejectReason.trim(),
          idempotency_key: rejectKey,
          metadata: {
            required_acknowledgement_task_count:
              selectedProposal.required_acknowledgement_task_ids.length,
          },
        },
      );
    },
    onSuccess: async (proposal) => {
      setRejectReason("");
      setRejectKey(idempotencyKey("repair-reject"));
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["preparation-repair-proposals", activeHouseholdId],
        }),
        queryClient.invalidateQueries({
          queryKey: [
            "preparation-repair-proposals",
            activeHouseholdId,
            proposal.id,
            "events",
          ],
        }),
      ]);
    },
  });

  const pageError =
    householdsQ.error ?? schedulesQ.error ?? calendarsQ.error ??
    proposalsQ.error ?? eventsQ.error ?? createMutation.error ??
    rejectMutation.error ?? null;

  const toggleImmutable = (taskId: string) => {
    setImmutableTaskIds((current) =>
      current.includes(taskId)
        ? current.filter((value) => value !== taskId)
        : [...current, taskId].sort(),
    );
    setCreateKey(idempotencyKey("repair-proposal"));
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-primary">Preparation operations</p>
            <h1 className="text-3xl font-semibold tracking-tight">
              Repair proposal registry
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              Create immutable server-recomputed review evidence, inspect exact
              hashes and events, and reject unsuitable proposals. This registry
              cannot accept a proposal or create a replacement schedule.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/preparation/operations/repair">
              Advisory repair workspace
            </Link>
          </Button>
        </div>

        <Alert>
          <ShieldAlert className="h-4 w-4" />
          <AlertTitle>Persisted review evidence, not a persisted schedule</AlertTitle>
          <AlertDescription>
            Proposal creation recomputes repair on the server and stores immutable
            evidence. Every proposal remains accepted=false and
            schedule_persistence_performed=false.
          </AlertDescription>
        </Alert>

        {pageError && (
          <Alert variant="destructive" role="alert">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Proposal workspace unavailable</AlertTitle>
            <AlertDescription>{messageOf(pageError)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Household scope</CardTitle>
            <CardDescription>
              Viewers can inspect proposals and events. Editors and owners can
              create or reject proposals.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="proposal-household">Household</Label>
              <select
                id="proposal-household"
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
            <div className="rounded-md border p-3 text-sm">
              <p className="text-xs text-muted-foreground">Current role</p>
              <p className="font-medium capitalize">
                {activeHousehold?.current_role ?? "unavailable"}
              </p>
            </div>
          </CardContent>
        </Card>

        {canEdit && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Create server proposal</CardTitle>
              <CardDescription>
                The backend ignores any client-computed result and recomputes a
                complete repair from the exact source evidence.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-5"
                onSubmit={(event) => {
                  event.preventDefault();
                  createMutation.mutate();
                }}
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor="proposal-source">Source schedule</Label>
                    <select
                      id="proposal-source"
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={activeScheduleId || ""}
                      onChange={(event) => setSourceScheduleId(event.target.value)}
                    >
                      {schedules.map((schedule) => (
                        <option key={schedule.id} value={schedule.id}>
                          #{schedule.id} · {schedule.status} · version {schedule.version}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="proposal-calendar">Target reviewed calendar</Label>
                    <select
                      id="proposal-calendar"
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={activeCalendarId || ""}
                      onChange={(event) => {
                        setTargetCalendarId(event.target.value);
                        setCreateKey(idempotencyKey("repair-proposal"));
                      }}
                    >
                      {calendars.map((calendar) => (
                        <option key={calendar.id} value={calendar.id}>
                          {calendar.calendar_version} · #{calendar.id}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {!sourceSchedule || !targetCalendar ? (
                  <Alert>
                    <FileWarning className="h-4 w-4" />
                    <AlertTitle>Source evidence unavailable</AlertTitle>
                    <AlertDescription>
                      A complete replayable draft/approved schedule and an active
                      reviewed calendar are required.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <>
                    <div className="flex flex-wrap gap-2 text-xs">
                      <Badge variant="outline">
                        source {shortHash(sourceSchedule.schedule_hash)}
                      </Badge>
                      <Badge variant="outline">
                        request {shortHash(sourceSchedule.schedule_request_hash ?? "")}
                      </Badge>
                      <Badge variant="outline">
                        calendar {shortHash(targetCalendar.content_hash)}
                      </Badge>
                    </div>

                    <div className="space-y-1">
                      <Label htmlFor="proposal-revised-request">
                        Strict revised request JSON
                      </Label>
                      <Textarea
                        id="proposal-revised-request"
                        className="min-h-[22rem] font-mono text-xs"
                        value={revisedRequestRaw}
                        onChange={(event) => {
                          setRevisedRequestRaw(event.target.value);
                          setCreateKey(idempotencyKey("repair-proposal"));
                        }}
                      />
                    </div>

                    <fieldset className="space-y-3 rounded-md border p-4">
                      <legend className="px-1 text-sm font-medium">
                        Immutable task placements
                      </legend>
                      <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
                        {sourceSchedule.schedule.scheduled.map((task) => (
                          <label
                            key={task.task_id}
                            className="flex items-start gap-2 rounded-md border p-3 text-sm"
                          >
                            <input
                              type="checkbox"
                              className="mt-1 h-4 w-4"
                              checked={immutableTaskIds.includes(task.task_id)}
                              onChange={() => toggleImmutable(task.task_id)}
                            />
                            <span>
                              <span className="block font-medium">{task.task_id}</span>
                              <span className="text-xs text-muted-foreground">
                                minute {task.start_minute}–{task.finish_minute}
                              </span>
                            </span>
                          </label>
                        ))}
                      </div>
                    </fieldset>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-1">
                        <Label htmlFor="proposal-strategy">Strategy</Label>
                        <select
                          id="proposal-strategy"
                          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                          value={strategy}
                          onChange={(event) => {
                            setStrategy(event.target.value as typeof strategy);
                            setCreateKey(idempotencyKey("repair-proposal"));
                          }}
                        >
                          <option value="greedy_min_change">
                            Greedy preservation-first
                          </option>
                          <option value="bounded_exact_min_change">
                            Bounded exact comparator
                          </option>
                        </select>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="proposal-notes">Review notes</Label>
                        <Textarea
                          id="proposal-notes"
                          value={notes}
                          onChange={(event) => {
                            setNotes(event.target.value);
                            setCreateKey(idempotencyKey("repair-proposal"));
                          }}
                          placeholder="Why is this repair being proposed?"
                        />
                      </div>
                    </div>

                    <div className="space-y-3">
                      <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4"
                          checked={acknowledgeNonAcceptance}
                          onChange={(event) =>
                            setAcknowledgeNonAcceptance(event.target.checked)
                          }
                        />
                        <span>
                          I understand proposal creation is not acceptance or approval.
                        </span>
                      </label>
                      <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4"
                          checked={acknowledgeNonPersistence}
                          onChange={(event) =>
                            setAcknowledgeNonPersistence(event.target.checked)
                          }
                        />
                        <span>
                          I understand no replacement schedule is persisted.
                        </span>
                      </label>
                    </div>

                    <Button
                      type="submit"
                      disabled={
                        createMutation.isPending ||
                        !acknowledgeNonAcceptance ||
                        !acknowledgeNonPersistence
                      }
                    >
                      <FileClock className="mr-2 h-4 w-4" />
                      {createMutation.isPending
                        ? "Creating immutable proposal…"
                        : "Create immutable proposal"}
                    </Button>
                  </>
                )}
              </form>
            </CardContent>
          </Card>
        )}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.4fr)]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Proposal history</CardTitle>
              <CardDescription>
                Current and historical records remain visible with staleness.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {proposals.length === 0 ? (
                <p className="text-sm text-muted-foreground">No proposals recorded.</p>
              ) : (
                proposals.map((proposal) => (
                  <button
                    key={proposal.id}
                    type="button"
                    className="w-full rounded-md border p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    onClick={() => setSelectedProposalId(proposal.id)}
                    aria-pressed={selectedProposal?.id === proposal.id}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">Proposal #{proposal.id}</span>
                      <div className="flex gap-2">
                        <Badge variant="outline" className="capitalize">
                          {proposal.status}
                        </Badge>
                        <Badge variant={proposal.current ? "default" : "destructive"}>
                          {proposal.current ? "current" : "stale"}
                        </Badge>
                      </div>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {proposalOutcomeSummary(proposal)}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Updated {new Date(proposal.updated_at).toLocaleString()}
                    </p>
                  </button>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Selected proposal evidence</CardTitle>
              <CardDescription>
                Exact identities, outcome ledger, staleness, and append-only events.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {!selectedProposal ? (
                <p className="text-sm text-muted-foreground">
                  Select or create a proposal.
                </p>
              ) : (
                <>
                  <Alert variant={selectedProposal.current ? "default" : "destructive"}>
                    {selectedProposal.current ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <AlertTriangle className="h-4 w-4" />
                    )}
                    <AlertTitle>
                      {selectedProposal.current
                        ? "Current review evidence"
                        : "Historical stale evidence"}
                    </AlertTitle>
                    <AlertDescription>
                      Accepted: {String(selectedProposal.accepted)}. Schedule
                      persistence performed: {String(selectedProposal.schedule_persistence_performed)}.
                    </AlertDescription>
                  </Alert>

                  {selectedProposal.stale_reasons.length > 0 && (
                    <div className="rounded-md border border-destructive/30 p-3">
                      <p className="text-sm font-medium">Stale reasons</p>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                        {selectedProposal.stale_reasons.map((value) => (
                          <li key={value}>{value.replaceAll("_", " ")}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="grid gap-3 md:grid-cols-2">
                    {[
                      ["Source schedule", `#${selectedProposal.source_schedule_id} · v${selectedProposal.source_schedule_version}`],
                      ["Target calendar", `#${selectedProposal.target_calendar_version_id}`],
                      ["Source hash", shortHash(selectedProposal.source_schedule_hash)],
                      ["Repair result hash", shortHash(selectedProposal.repair_result_hash)],
                      ["Revised request hash", shortHash(selectedProposal.revised_request_hash)],
                      ["Repaired response hash", shortHash(selectedProposal.repaired_response_hash)],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md border p-3">
                        <p className="text-xs text-muted-foreground">{label}</p>
                        <p className="break-all font-mono text-xs">{value}</p>
                      </div>
                    ))}
                  </div>

                  <div>
                    <p className="text-sm font-medium">Required change acknowledgements</p>
                    {selectedProposal.required_acknowledgement_task_ids.length === 0 ? (
                      <p className="mt-1 text-sm text-muted-foreground">
                        No moved, added, removed, or unresolved task requires acknowledgement.
                      </p>
                    ) : (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {selectedProposal.required_acknowledgement_task_ids.map((taskId) => (
                          <Badge key={taskId} variant="outline">
                            <LockKeyhole className="mr-1 h-3 w-3" />
                            {taskId}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    {[
                      ["Preserved", selectedProposal.repair_result.preserved_task_ids.length],
                      ["Moved", selectedProposal.repair_result.moved_tasks.length],
                      ["Added", selectedProposal.repair_result.added_task_ids.length],
                      ["Removed", selectedProposal.repair_result.removed_task_ids.length],
                      ["Unresolved", selectedProposal.repair_result.unscheduled_task_ids.length],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md border p-3">
                        <p className="text-xs text-muted-foreground">{label}</p>
                        <p className="text-xl font-semibold">{value}</p>
                      </div>
                    ))}
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <History className="h-4 w-4" />
                      <p className="text-sm font-medium">Append-only events</p>
                    </div>
                    <ol className="mt-3 space-y-2">
                      {(eventsQ.data ?? []).map((event) => (
                        <li key={event.id} className="rounded-md border p-3 text-sm">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <Badge variant="outline" className="capitalize">
                              {event.event_type}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {new Date(event.created_at).toLocaleString()}
                            </span>
                          </div>
                          <p className="mt-2">{event.reason}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Version {event.proposal_version_before} → {event.proposal_version_after}
                          </p>
                        </li>
                      ))}
                    </ol>
                  </div>

                  {canEdit && selectedProposal.status === "proposed" && (
                    <form
                      className="space-y-3 rounded-md border p-4"
                      onSubmit={(event) => {
                        event.preventDefault();
                        rejectMutation.mutate();
                      }}
                    >
                      <div>
                        <p className="text-sm font-medium">Reject proposal</p>
                        <p className="text-xs text-muted-foreground">
                          Rejection is versioned and append-only. It does not alter the source schedule.
                        </p>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="proposal-rejection-reason">Reason</Label>
                        <Textarea
                          id="proposal-rejection-reason"
                          value={rejectReason}
                          onChange={(event) => {
                            setRejectReason(event.target.value);
                            setRejectKey(idempotencyKey("repair-reject"));
                          }}
                          placeholder="Why should this proposal not proceed?"
                        />
                      </div>
                      <Button
                        type="submit"
                        variant="destructive"
                        disabled={rejectMutation.isPending || !rejectReason.trim()}
                      >
                        <Ban className="mr-2 h-4 w-4" />
                        {rejectMutation.isPending ? "Rejecting…" : "Reject proposal"}
                      </Button>
                    </form>
                  )}

                  <Alert>
                    <Clock3 className="h-4 w-4" />
                    <AlertTitle>Acceptance remains unavailable</AlertTitle>
                    <AlertDescription>
                      Method-aware replay and accepted-draft persistence are not
                      implemented. This page intentionally exposes no accept,
                      approve, persist, execute, or complete action.
                    </AlertDescription>
                  </Alert>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="flex justify-end">
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              void proposalsQ.refetch();
              if (selectedProposal) void eventsQ.refetch();
            }}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh evidence
          </Button>
        </div>
      </div>
    </AppLayout>
  );
}
