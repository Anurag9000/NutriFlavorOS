import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  FileClock,
  FileWarning,
  History,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
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
  type PreparationScheduleRequest,
} from "@/lib/preparationOperationsApi";
import {
  preparationRepairProposalApi,
  type PreparationRepairProposalAcceptRequest,
  type PreparationRepairProposalCreateRequest,
  type PreparationRepairProposalView,
} from "@/lib/preparationRepairProposalApi";

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The repair proposal request could not be completed";
}

function requestKey(prefix: string): string {
  const value = globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}:${value}`;
}

function shortHash(value: string | null | undefined): string {
  if (!value) return "not available";
  return value.length > 22
    ? `${value.slice(0, 12)}…${value.slice(-6)}`
    : value;
}

function parseRequest(raw: string): PreparationScheduleRequest {
  const parsed = JSON.parse(raw) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Revised request must be a JSON object");
  }
  const value = parsed as Partial<PreparationScheduleRequest>;
  if (!Number.isInteger(value.horizon_minutes) || Number(value.horizon_minutes) <= 0) {
    throw new Error("Revised request requires positive integer horizon_minutes");
  }
  if (
    !Number.isInteger(value.granularity_minutes)
    || Number(value.granularity_minutes) <= 0
  ) {
    throw new Error("Revised request requires positive integer granularity_minutes");
  }
  if (!Array.isArray(value.resources) || !Array.isArray(value.tasks)) {
    throw new Error("Revised request requires resources and tasks arrays");
  }
  return value as PreparationScheduleRequest;
}

function canEdit(role?: string): boolean {
  return role === "owner" || role === "editor";
}

function outcome(value: PreparationRepairProposalView): string {
  const result = value.repair_result;
  return [
    `${result.preserved_task_ids.length} preserved`,
    `${result.moved_tasks.length} moved`,
    `${result.added_task_ids.length} added`,
    `${result.removed_task_ids.length} removed`,
    `${result.unscheduled_task_ids.length} unresolved`,
  ].join(" · ");
}

export default function PreparationRepairProposalsPage() {
  const queryClient = useQueryClient();
  const [householdId, setHouseholdId] = useState("");
  const [sourceId, setSourceId] = useState(0);
  const [calendarId, setCalendarId] = useState(0);
  const [requestRaw, setRequestRaw] = useState("");
  const [immutableTaskIds, setImmutableTaskIds] = useState<string[]>([]);
  const [strategy, setStrategy] = useState<
    "greedy_min_change" | "bounded_exact_min_change"
  >("greedy_min_change");
  const [notes, setNotes] = useState("");
  const [acknowledgeProposalOnly, setAcknowledgeProposalOnly] = useState(false);
  const [acknowledgeNoPersistence, setAcknowledgeNoPersistence] = useState(false);
  const [creationKey, setCreationKey] = useState(() => requestKey("repair-proposal"));
  const [selectedId, setSelectedId] = useState(0);
  const [acknowledgedTaskIds, setAcknowledgedTaskIds] = useState<string[]>([]);
  const [acceptReason, setAcceptReason] = useState("");
  const [acknowledgeDraftOnly, setAcknowledgeDraftOnly] = useState(false);
  const [acceptKey, setAcceptKey] = useState(() => requestKey("repair-accept"));
  const [rejectReason, setRejectReason] = useState("");
  const [rejectKey, setRejectKey] = useState(() => requestKey("repair-reject"));

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const activeHouseholdId = householdId || households[0]?.id || "";
  const household = households.find((value) => value.id === activeHouseholdId);
  const editable = canEdit(household?.current_role);

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
          value.replay_status === "replayable"
          && value.schedule_request !== null
          && value.schedule.unscheduled.length === 0,
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
  const source = schedules.find((value) => value.id === sourceId) ?? schedules[0];
  const calendar = calendars.find((value) => value.id === calendarId) ?? calendars[0];
  const selected = proposals.find((value) => value.id === selectedId) ?? proposals[0];

  const eventsQ = useQuery({
    queryKey: ["preparation-repair-proposals", activeHouseholdId, selected?.id, "events"],
    queryFn: () => preparationRepairProposalApi.events(activeHouseholdId, selected!.id),
    enabled: Boolean(activeHouseholdId && selected?.id),
  });
  const acceptanceQ = useQuery({
    queryKey: [
      "preparation-repair-proposals",
      activeHouseholdId,
      selected?.id,
      "acceptance",
    ],
    queryFn: () => preparationRepairProposalApi.acceptance(activeHouseholdId, selected!.id),
    enabled: Boolean(
      activeHouseholdId && selected?.id && selected.status === "accepted",
    ),
  });

  useEffect(() => {
    setSourceId(0);
    setCalendarId(0);
    setSelectedId(0);
    setRequestRaw("");
    setImmutableTaskIds([]);
    setAcknowledgedTaskIds([]);
    setCreationKey(requestKey("repair-proposal"));
    setAcceptKey(requestKey("repair-accept"));
    setRejectKey(requestKey("repair-reject"));
  }, [activeHouseholdId]);

  useEffect(() => {
    if (!source?.schedule_request) {
      setRequestRaw("");
      setImmutableTaskIds([]);
      return;
    }
    setRequestRaw(JSON.stringify(source.schedule_request, null, 2));
    setImmutableTaskIds([]);
    setCreationKey(requestKey("repair-proposal"));
  }, [source?.id, source?.schedule_request]);

  useEffect(() => {
    if (selected) setSelectedId(selected.id);
    setAcknowledgedTaskIds([]);
    setAcceptReason("");
    setAcknowledgeDraftOnly(false);
    setAcceptKey(requestKey("repair-accept"));
    setRejectReason("");
    setRejectKey(requestKey("repair-reject"));
  }, [selected?.id]);

  const invalidateProposalQueries = async (proposalId?: number) => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["preparation-repair-proposals", activeHouseholdId],
      }),
      proposalId
        ? queryClient.invalidateQueries({
            queryKey: ["preparation-repair-proposals", activeHouseholdId, proposalId],
          })
        : Promise.resolve(),
      queryClient.invalidateQueries({
        queryKey: ["preparation-operations", activeHouseholdId],
      }),
    ]);
  };

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!source || !calendar) {
        throw new Error("Select a replayable source and active reviewed calendar");
      }
      const payload: PreparationRepairProposalCreateRequest = {
        source_schedule_id: source.id,
        expected_source_version: source.version,
        target_calendar_version_id: calendar.id,
        revised_request: parseRequest(requestRaw),
        immutable_task_ids: immutableTaskIds,
        strategy,
        notes: notes.trim() || null,
        acknowledge_non_acceptance: true,
        acknowledge_non_persistence: true,
        idempotency_key: creationKey,
      };
      return preparationRepairProposalApi.create(activeHouseholdId, payload);
    },
    onSuccess: async (proposal) => {
      setSelectedId(proposal.id);
      setAcknowledgeProposalOnly(false);
      setAcknowledgeNoPersistence(false);
      setCreationKey(requestKey("repair-proposal"));
      await invalidateProposalQueries(proposal.id);
    },
  });

  const acceptMutation = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("Select a proposal");
      if (!acceptReason.trim()) throw new Error("An acceptance reason is required");
      const payload: PreparationRepairProposalAcceptRequest = {
        expected_proposal_version: selected.version,
        expected_source_schedule_version: selected.source_schedule_version,
        expected_source_schedule_hash: selected.source_schedule_hash,
        expected_source_schedule_request_hash: selected.source_schedule_request_hash,
        expected_target_calendar_content_hash: selected.target_calendar_content_hash,
        expected_repair_request_hash: selected.repair_request_hash,
        expected_repair_result_hash: selected.repair_result_hash,
        expected_revised_request_hash: selected.revised_request_hash,
        expected_repaired_response_hash: selected.repaired_response_hash,
        acknowledged_task_ids: [...acknowledgedTaskIds].sort(),
        reason: acceptReason.trim(),
        acknowledge_creates_new_draft_only: true,
        idempotency_key: acceptKey,
        metadata: {
          required_acknowledgement_task_count:
            selected.required_acknowledgement_task_ids.length,
        },
      };
      return preparationRepairProposalApi.accept(
        activeHouseholdId,
        selected.id,
        payload,
      );
    },
    onSuccess: async (result) => {
      setAcknowledgedTaskIds([]);
      setAcceptReason("");
      setAcknowledgeDraftOnly(false);
      setAcceptKey(requestKey("repair-accept"));
      await invalidateProposalQueries(result.proposal.id);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("Select a proposal");
      if (!rejectReason.trim()) throw new Error("A rejection reason is required");
      return preparationRepairProposalApi.reject(activeHouseholdId, selected.id, {
        expected_version: selected.version,
        reason: rejectReason.trim(),
        idempotency_key: rejectKey,
        metadata: {
          required_acknowledgement_task_count:
            selected.required_acknowledgement_task_ids.length,
        },
      });
    },
    onSuccess: async (proposal) => {
      setRejectReason("");
      setRejectKey(requestKey("repair-reject"));
      await invalidateProposalQueries(proposal.id);
    },
  });

  const pageError =
    householdsQ.error
    ?? schedulesQ.error
    ?? calendarsQ.error
    ?? proposalsQ.error
    ?? eventsQ.error
    ?? acceptanceQ.error
    ?? createMutation.error
    ?? acceptMutation.error
    ?? rejectMutation.error
    ?? null;

  const exactAcknowledgements = selected
    ? acknowledgedTaskIds.length === selected.required_acknowledgement_task_ids.length
      && selected.required_acknowledgement_task_ids.every((value) =>
        acknowledgedTaskIds.includes(value))
    : false;

  const toggle = (
    taskId: string,
    values: string[],
    setter: (values: string[]) => void,
  ) => {
    setter(
      values.includes(taskId)
        ? values.filter((value) => value !== taskId)
        : [...values, taskId].sort(),
    );
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
              Create advisory proposal evidence, review every changed task, and
              explicitly create a separate draft. Draft acceptance never performs
              owner approval or task execution.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/preparation/operations/repair">Advisory repair</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/preparation/operations">Schedule approval</Link>
            </Button>
          </div>
        </div>

        <Alert>
          <ShieldAlert className="h-4 w-4" />
          <AlertTitle>Two explicit lifecycle decisions</AlertTitle>
          <AlertDescription>
            Proposal creation remains non-persistent. Acceptance creates one new
            draft only. An owner must separately approve that draft after
            method-aware replay.
          </AlertDescription>
        </Alert>

        {pageError && (
          <Alert variant="destructive" role="alert">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Repair proposal operation failed</AlertTitle>
            <AlertDescription>{messageOf(pageError)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Household scope</CardTitle>
            <CardDescription>
              Viewers inspect evidence. Editors and owners create, accept, or reject.
              Only owners approve the resulting draft.
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
                {households.map((value) => (
                  <option key={value.id} value={value.id}>{value.name}</option>
                ))}
              </select>
            </div>
            <div className="rounded-md border p-3 text-sm">
              <p className="text-xs text-muted-foreground">Current role</p>
              <p className="font-medium capitalize">
                {household?.current_role ?? "unavailable"}
              </p>
            </div>
          </CardContent>
        </Card>

        {editable && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">1. Create advisory proposal</CardTitle>
              <CardDescription>
                The server recomputes complete repair and stores review evidence only.
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
                      value={source?.id ?? ""}
                      onChange={(event) => setSourceId(Number(event.target.value))}
                    >
                      {schedules.map((value) => (
                        <option key={value.id} value={value.id}>
                          #{value.id} · {value.status} · version {value.version}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="proposal-calendar">Target reviewed calendar</Label>
                    <select
                      id="proposal-calendar"
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={calendar?.id ?? ""}
                      onChange={(event) => {
                        setCalendarId(Number(event.target.value));
                        setCreationKey(requestKey("repair-proposal"));
                      }}
                    >
                      {calendars.map((value) => (
                        <option key={value.id} value={value.id}>
                          {value.calendar_version} · #{value.id}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {!source || !calendar ? (
                  <Alert>
                    <FileWarning className="h-4 w-4" />
                    <AlertTitle>Complete replay evidence required</AlertTitle>
                    <AlertDescription>
                      Select a replayable draft or approved source and the active
                      reviewed calendar.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <>
                    <div className="flex flex-wrap gap-2 text-xs">
                      <Badge variant="outline">source {shortHash(source.schedule_hash)}</Badge>
                      <Badge variant="outline">
                        request {shortHash(source.schedule_request_hash)}
                      </Badge>
                      <Badge variant="outline">calendar {shortHash(calendar.content_hash)}</Badge>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="proposal-revised-request">Strict revised request JSON</Label>
                      <Textarea
                        id="proposal-revised-request"
                        className="min-h-[20rem] font-mono text-xs"
                        value={requestRaw}
                        onChange={(event) => {
                          setRequestRaw(event.target.value);
                          setCreationKey(requestKey("repair-proposal"));
                        }}
                      />
                    </div>
                    <fieldset className="space-y-3 rounded-md border p-4">
                      <legend className="px-1 text-sm font-medium">Immutable placements</legend>
                      <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
                        {source.schedule.scheduled.map((task) => (
                          <label key={task.task_id} className="flex gap-2 rounded-md border p-3 text-sm">
                            <input
                              type="checkbox"
                              className="mt-1 h-4 w-4"
                              checked={immutableTaskIds.includes(task.task_id)}
                              onChange={() => {
                                toggle(task.task_id, immutableTaskIds, setImmutableTaskIds);
                                setCreationKey(requestKey("repair-proposal"));
                              }}
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
                        <Label htmlFor="proposal-strategy">Repair strategy</Label>
                        <select
                          id="proposal-strategy"
                          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                          value={strategy}
                          onChange={(event) => {
                            setStrategy(event.target.value as typeof strategy);
                            setCreationKey(requestKey("repair-proposal"));
                          }}
                        >
                          <option value="greedy_min_change">Greedy preservation-first</option>
                          <option value="bounded_exact_min_change">Bounded exact comparator</option>
                        </select>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="proposal-notes">Proposal notes</Label>
                        <Textarea
                          id="proposal-notes"
                          value={notes}
                          onChange={(event) => {
                            setNotes(event.target.value);
                            setCreationKey(requestKey("repair-proposal"));
                          }}
                        />
                      </div>
                    </div>
                    <label className="flex gap-3 rounded-md border p-3 text-sm">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4"
                        checked={acknowledgeProposalOnly}
                        onChange={(event) => setAcknowledgeProposalOnly(event.target.checked)}
                      />
                      <span>Proposal creation is not acceptance or owner approval.</span>
                    </label>
                    <label className="flex gap-3 rounded-md border p-3 text-sm">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4"
                        checked={acknowledgeNoPersistence}
                        onChange={(event) => setAcknowledgeNoPersistence(event.target.checked)}
                      />
                      <span>Proposal creation does not persist a replacement schedule.</span>
                    </label>
                    <Button
                      type="submit"
                      disabled={
                        createMutation.isPending
                        || !acknowledgeProposalOnly
                        || !acknowledgeNoPersistence
                      }
                    >
                      <FileClock className="mr-2 h-4 w-4" />
                      {createMutation.isPending ? "Creating proposal…" : "Create advisory proposal"}
                    </Button>
                  </>
                )}
              </form>
            </CardContent>
          </Card>
        )}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.5fr)]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Proposal history</CardTitle>
              <CardDescription>Immutable records remain readable after acceptance or rejection.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {proposals.length === 0 ? (
                <p className="text-sm text-muted-foreground">No repair proposals recorded.</p>
              ) : proposals.map((value) => (
                <button
                  key={value.id}
                  type="button"
                  className="w-full rounded-md border p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => setSelectedId(value.id)}
                  aria-pressed={selected?.id === value.id}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">Proposal #{value.id}</span>
                    <div className="flex gap-2">
                      <Badge variant="outline" className="capitalize">{value.status}</Badge>
                      <Badge variant={value.current ? "default" : "secondary"}>
                        {value.current ? "current" : "historical"}
                      </Badge>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{outcome(value)}</p>
                </button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Selected proposal evidence</CardTitle>
              <CardDescription>
                Exact source identities, changed tasks, lifecycle events, and draft acceptance.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {!selected ? (
                <p className="text-sm text-muted-foreground">Select or create a proposal.</p>
              ) : (
                <>
                  <Alert variant={selected.status === "invalidated" ? "destructive" : "default"}>
                    {selected.status === "accepted" ? (
                      <ShieldCheck className="h-4 w-4" />
                    ) : selected.current ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <AlertTriangle className="h-4 w-4" />
                    )}
                    <AlertTitle className="capitalize">Proposal {selected.status}</AlertTitle>
                    <AlertDescription>
                      Draft persistence: {String(selected.schedule_persistence_performed)}.
                      Owner approval is a separate action.
                    </AlertDescription>
                  </Alert>

                  {selected.stale_reasons.length > 0 && selected.status === "proposed" && (
                    <div className="rounded-md border border-destructive/30 p-3">
                      <p className="text-sm font-medium">Cannot accept while stale</p>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                        {selected.stale_reasons.map((value) => (
                          <li key={value}>{value.replaceAll("_", " ")}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="grid gap-3 md:grid-cols-2">
                    {[
                      ["Source schedule", `#${selected.source_schedule_id} · v${selected.source_schedule_version}`],
                      ["Target calendar", `#${selected.target_calendar_version_id}`],
                      ["Source hash", shortHash(selected.source_schedule_hash)],
                      ["Repair request", shortHash(selected.repair_request_hash)],
                      ["Repair result", shortHash(selected.repair_result_hash)],
                      ["Repaired response", shortHash(selected.repaired_response_hash)],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md border p-3">
                        <p className="text-xs text-muted-foreground">{label}</p>
                        <p className="break-all font-mono text-xs">{value}</p>
                      </div>
                    ))}
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    {[
                      ["Preserved", selected.repair_result.preserved_task_ids.length],
                      ["Moved", selected.repair_result.moved_tasks.length],
                      ["Added", selected.repair_result.added_task_ids.length],
                      ["Removed", selected.repair_result.removed_task_ids.length],
                      ["Unresolved", selected.repair_result.unscheduled_task_ids.length],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md border p-3">
                        <p className="text-xs text-muted-foreground">{label}</p>
                        <p className="text-xl font-semibold">{value}</p>
                      </div>
                    ))}
                  </div>

                  {editable && selected.status === "proposed" && selected.current && (
                    <form
                      className="space-y-4 rounded-md border p-4"
                      onSubmit={(event) => {
                        event.preventDefault();
                        acceptMutation.mutate();
                      }}
                    >
                      <div>
                        <p className="text-sm font-medium">2. Accept into a new draft</p>
                        <p className="text-xs text-muted-foreground">
                          Acknowledge every moved, added, removed, or unresolved task.
                        </p>
                      </div>
                      <fieldset className="space-y-2">
                        <legend className="text-sm font-medium">Required changed-task acknowledgements</legend>
                        {selected.required_acknowledgement_task_ids.length === 0 ? (
                          <p className="text-sm text-muted-foreground">No changed task requires acknowledgement.</p>
                        ) : selected.required_acknowledgement_task_ids.map((taskId) => (
                          <label key={taskId} className="flex gap-3 rounded-md border p-3 text-sm">
                            <input
                              type="checkbox"
                              className="mt-1 h-4 w-4"
                              checked={acknowledgedTaskIds.includes(taskId)}
                              onChange={() => {
                                toggle(taskId, acknowledgedTaskIds, setAcknowledgedTaskIds);
                                setAcceptKey(requestKey("repair-accept"));
                              }}
                            />
                            <span>
                              <LockKeyhole className="mr-1 inline h-3 w-3" />
                              I reviewed the change to {taskId}.
                            </span>
                          </label>
                        ))}
                      </fieldset>
                      <div className="space-y-1">
                        <Label htmlFor="repair-accept-reason">Acceptance reason</Label>
                        <Textarea
                          id="repair-accept-reason"
                          value={acceptReason}
                          onChange={(event) => {
                            setAcceptReason(event.target.value);
                            setAcceptKey(requestKey("repair-accept"));
                          }}
                          placeholder="Why should this become a separately approvable draft?"
                        />
                      </div>
                      <label className="flex gap-3 rounded-md border p-3 text-sm">
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4"
                          checked={acknowledgeDraftOnly}
                          onChange={(event) => setAcknowledgeDraftOnly(event.target.checked)}
                        />
                        <span>
                          I understand this creates one new draft only; it does not
                          approve, execute, or complete the schedule.
                        </span>
                      </label>
                      <Button
                        type="submit"
                        disabled={
                          acceptMutation.isPending
                          || !exactAcknowledgements
                          || !acceptReason.trim()
                          || !acknowledgeDraftOnly
                        }
                      >
                        <ShieldCheck className="mr-2 h-4 w-4" />
                        {acceptMutation.isPending ? "Creating draft…" : "Accept and create draft"}
                      </Button>
                    </form>
                  )}

                  {selected.status === "accepted" && (
                    <div className="space-y-3 rounded-md border p-4">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4" />
                        <p className="text-sm font-medium">Accepted draft evidence</p>
                      </div>
                      {acceptanceQ.isLoading ? (
                        <p className="text-sm text-muted-foreground">Loading acceptance evidence…</p>
                      ) : acceptanceQ.data ? (
                        <>
                          <div className="grid gap-3 md:grid-cols-2">
                            <div className="rounded-md border p-3">
                              <p className="text-xs text-muted-foreground">Created draft</p>
                              <p className="font-medium">#{acceptanceQ.data.created_schedule_id}</p>
                              <p className="text-xs text-muted-foreground">status draft · version 1</p>
                            </div>
                            <div className="rounded-md border p-3">
                              <p className="text-xs text-muted-foreground">Draft schedule hash</p>
                              <p className="break-all font-mono text-xs">
                                {acceptanceQ.data.created_schedule_hash}
                              </p>
                            </div>
                          </div>
                          <Alert>
                            <ShieldAlert className="h-4 w-4" />
                            <AlertTitle>Owner approval still required</AlertTitle>
                            <AlertDescription>
                              The accepted result is only a draft. Open Preparation
                              Operations for separate method-aware owner approval.
                            </AlertDescription>
                          </Alert>
                          <Button asChild variant="outline">
                            <Link to="/preparation/operations">Review draft for approval</Link>
                          </Button>
                        </>
                      ) : null}
                    </div>
                  )}

                  {editable && selected.status === "proposed" && (
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
                          Rejection is versioned and never changes the source schedule.
                        </p>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="repair-reject-reason">Rejection reason</Label>
                        <Textarea
                          id="repair-reject-reason"
                          value={rejectReason}
                          onChange={(event) => {
                            setRejectReason(event.target.value);
                            setRejectKey(requestKey("repair-reject"));
                          }}
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

                  <div>
                    <div className="flex items-center gap-2">
                      <History className="h-4 w-4" />
                      <p className="text-sm font-medium">Append-only proposal events</p>
                    </div>
                    <ol className="mt-3 space-y-2">
                      {(eventsQ.data ?? []).map((event) => (
                        <li key={event.id} className="rounded-md border p-3 text-sm">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <Badge variant="outline" className="capitalize">{event.event_type}</Badge>
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
              if (selected) {
                void eventsQ.refetch();
                if (selected.status === "accepted") void acceptanceQ.refetch();
              }
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
