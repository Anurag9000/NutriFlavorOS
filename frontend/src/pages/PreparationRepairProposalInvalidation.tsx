import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArchiveX,
  FileClock,
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
  preparationRepairProposalApi,
  type PreparationRepairProposalView,
} from "@/lib/preparationRepairProposalApi";

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The proposal invalidation request could not be completed";
}

function requestKey(): string {
  const value = globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `repair-proposal-invalidate:${value}`;
}

function shortHash(value: string): string {
  return `${value.slice(0, 12)}…${value.slice(-6)}`;
}

function staleLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function outcome(value: PreparationRepairProposalView): string {
  const result = value.repair_result;
  return [
    `${result.moved_tasks.length} moved`,
    `${result.added_task_ids.length} added`,
    `${result.removed_task_ids.length} removed`,
    `${result.unscheduled_task_ids.length} unresolved`,
  ].join(" · ");
}

export default function PreparationRepairProposalInvalidationPage() {
  const queryClient = useQueryClient();
  const [householdId, setHouseholdId] = useState("");
  const [selectedId, setSelectedId] = useState(0);
  const [reason, setReason] = useState("");
  const [acknowledgeHistoricalOnly, setAcknowledgeHistoricalOnly] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState(requestKey);

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const activeHouseholdId = householdId || households[0]?.id || "";
  const household = households.find((value) => value.id === activeHouseholdId);
  const isOwner = household?.current_role === "owner";

  const proposalsQ = useQuery({
    queryKey: ["preparation-repair-proposals", activeHouseholdId],
    queryFn: () => preparationRepairProposalApi.list(activeHouseholdId),
    enabled: Boolean(activeHouseholdId),
  });
  const proposals = proposalsQ.data ?? [];
  const proposed = useMemo(
    () => proposals.filter((value) => value.status === "proposed"),
    [proposals],
  );
  const selected = proposed.find((value) => value.id === selectedId) ?? proposed[0];

  const eventsQ = useQuery({
    queryKey: [
      "preparation-repair-proposals",
      activeHouseholdId,
      selected?.id,
      "events",
    ],
    queryFn: () =>
      preparationRepairProposalApi.events(activeHouseholdId, selected!.id),
    enabled: Boolean(activeHouseholdId && selected?.id),
  });

  useEffect(() => {
    setSelectedId(0);
    setReason("");
    setAcknowledgeHistoricalOnly(false);
    setIdempotencyKey(requestKey());
  }, [activeHouseholdId]);

  useEffect(() => {
    if (selected) setSelectedId(selected.id);
    setReason("");
    setAcknowledgeHistoricalOnly(false);
    setIdempotencyKey(requestKey());
  }, [selected?.id]);

  const invalidateMutation = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("Select a proposed repair record");
      if (!isOwner) throw new Error("Only a household owner can invalidate a proposal");
      if (!reason.trim()) throw new Error("An invalidation reason is required");
      if (!acknowledgeHistoricalOnly) {
        throw new Error("Confirm that invalidation keeps historical evidence only");
      }
      return preparationRepairProposalApi.invalidate(
        activeHouseholdId,
        selected.id,
        {
          expected_version: selected.version,
          reason: reason.trim(),
          acknowledge_historical_only: true,
          idempotency_key: idempotencyKey,
          metadata: {
            source: "repair_proposal_invalidation_workspace",
            observed_client_stale_reasons: selected.stale_reasons,
          },
        },
      );
    },
    onSuccess: async (value) => {
      setReason("");
      setAcknowledgeHistoricalOnly(false);
      setIdempotencyKey(requestKey());
      setSelectedId(0);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["preparation-repair-proposals", activeHouseholdId],
        }),
        queryClient.invalidateQueries({
          queryKey: [
            "preparation-repair-proposals",
            activeHouseholdId,
            value.id,
            "events",
          ],
        }),
      ]);
    },
  });

  const error =
    householdsQ.error
    ?? proposalsQ.error
    ?? eventsQ.error
    ?? invalidateMutation.error
    ?? null;

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-primary">Preparation operations</p>
            <h1 className="text-3xl font-semibold tracking-tight">
              Proposal invalidation administration
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              Permanently withdraw one proposed repair record from future acceptance.
              Invalidation keeps immutable history and creates no schedule, approval,
              task event, completion, or source mutation.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/preparation/operations/repair-proposals">
              Repair proposal registry
            </Link>
          </Button>
        </div>

        <Alert>
          <ShieldAlert className="h-4 w-4" />
          <AlertTitle>Owner-only historical transition</AlertTitle>
          <AlertDescription>
            Editors and viewers may inspect this workspace but cannot invalidate.
            The server independently records observed stale reasons and permanently
            prevents later acceptance of the selected proposal.
          </AlertDescription>
        </Alert>

        {error && (
          <Alert variant="destructive" role="alert">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Proposal invalidation failed</AlertTitle>
            <AlertDescription>{messageOf(error)}</AlertDescription>
          </Alert>
        )}

        {invalidateMutation.isSuccess && (
          <Alert role="status" aria-live="polite">
            <ArchiveX className="h-4 w-4" />
            <AlertTitle>Proposal invalidated</AlertTitle>
            <AlertDescription>
              The record is historical-only. No replacement schedule was created.
            </AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Household scope</CardTitle>
            <CardDescription>
              The current role controls whether the invalidation form is available.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="invalidation-household">Household</Label>
              <select
                id="invalidation-household"
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

        <div className="grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.4fr)]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Proposed records</CardTitle>
              <CardDescription>
                Accepted, rejected, and invalidated records are terminal and excluded.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {proposalsQ.isLoading ? (
                <p className="text-sm text-muted-foreground" aria-live="polite">
                  Loading repair proposals…
                </p>
              ) : proposed.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No proposed repair record is available for invalidation.
                </p>
              ) : proposed.map((value) => (
                <button
                  key={value.id}
                  type="button"
                  className="w-full rounded-md border p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => setSelectedId(value.id)}
                  aria-pressed={selected?.id === value.id}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">Proposal #{value.id}</span>
                    <Badge variant={value.current ? "default" : "secondary"}>
                      {value.current ? "current" : "stale"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{outcome(value)}</p>
                </button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Invalidation review</CardTitle>
              <CardDescription>
                Review exact source, hashes, stale evidence, and existing events before
                withdrawing the record.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {!selected ? (
                <p className="text-sm text-muted-foreground">
                  Select a proposed repair record.
                </p>
              ) : (
                <>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">proposal #{selected.id}</Badge>
                    <Badge variant="outline">version {selected.version}</Badge>
                    <Badge variant={selected.current ? "default" : "destructive"}>
                      {selected.current ? "current evidence" : "stale evidence"}
                    </Badge>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">Source schedule</p>
                      <p className="font-medium">
                        #{selected.source_schedule_id} · version {selected.source_schedule_version}
                      </p>
                      <p className="font-mono text-xs">
                        {shortHash(selected.source_schedule_hash)}
                      </p>
                    </div>
                    <div className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">Repair result</p>
                      <p className="font-mono text-xs">
                        {shortHash(selected.repair_result_hash)}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {outcome(selected)}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-md border p-3">
                    <p className="text-sm font-medium">Observed client-side stale evidence</p>
                    {selected.stale_reasons.length === 0 ? (
                      <p className="mt-1 text-sm text-muted-foreground">
                        None currently observed. Owners may still withdraw a current proposal.
                      </p>
                    ) : (
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                        {selected.stale_reasons.map((value) => (
                          <li key={value}>{staleLabel(value)}</li>
                        ))}
                      </ul>
                    )}
                    <p className="mt-2 text-xs text-muted-foreground">
                      The server recomputes and records authoritative stale reasons at mutation time.
                    </p>
                  </div>

                  {!isOwner ? (
                    <Alert>
                      <LockKeyhole className="h-4 w-4" />
                      <AlertTitle>Read-only role</AlertTitle>
                      <AlertDescription>
                        Only a household owner can perform this permanent historical transition.
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <form
                      className="space-y-4 rounded-md border border-destructive/30 p-4"
                      onSubmit={(event) => {
                        event.preventDefault();
                        invalidateMutation.mutate();
                      }}
                    >
                      <div>
                        <p className="text-sm font-medium">Owner invalidation</p>
                        <p className="text-xs text-muted-foreground">
                          This permanently prevents later acceptance but never deletes evidence.
                        </p>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="proposal-invalidation-reason">
                          Invalidation reason
                        </Label>
                        <Textarea
                          id="proposal-invalidation-reason"
                          value={reason}
                          onChange={(event) => {
                            setReason(event.target.value);
                            setIdempotencyKey(requestKey());
                          }}
                          placeholder="Why should this proposal remain historical only?"
                        />
                      </div>
                      <label className="flex gap-3 rounded-md border p-3 text-sm">
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4"
                          checked={acknowledgeHistoricalOnly}
                          onChange={(event) =>
                            setAcknowledgeHistoricalOnly(event.target.checked)
                          }
                        />
                        <span>
                          I understand this keeps immutable history, creates no schedule,
                          and permanently prevents future acceptance of this proposal.
                        </span>
                      </label>
                      <Button
                        type="submit"
                        variant="destructive"
                        disabled={
                          invalidateMutation.isPending
                          || !reason.trim()
                          || !acknowledgeHistoricalOnly
                        }
                      >
                        <ArchiveX className="mr-2 h-4 w-4" />
                        {invalidateMutation.isPending
                          ? "Invalidating proposal…"
                          : "Invalidate proposal"}
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
              if (selected) void eventsQ.refetch();
            }}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh invalidation evidence
          </Button>
        </div>
      </div>
    </AppLayout>
  );
}
