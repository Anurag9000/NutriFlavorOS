import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  FileSearch,
  GitBranch,
  Link2,
  ShieldCheck,
} from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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
import { preparationScheduleDerivationApi } from "@/lib/preparationScheduleDerivationApi";

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Schedule derivation evidence could not be loaded";
}

function hash(value: string | null): string {
  if (!value) return "Not applicable";
  return `${value.slice(0, 14)}…${value.slice(-8)}`;
}

function methodLabel(value: string): string {
  return value === "deterministic_minimal_change_preparation_repair_v1"
    ? "Accepted repair"
    : "Original deterministic scheduler";
}

export default function PreparationScheduleDerivationPage() {
  const [householdId, setHouseholdId] = useState("");
  const [scheduleId, setScheduleId] = useState(0);

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const activeHouseholdId = householdId || households[0]?.id || "";

  const schedulesQ = useQuery({
    queryKey: ["preparation-operations", activeHouseholdId, "derivation-schedules"],
    queryFn: () => preparationOperationsApi.schedules(activeHouseholdId),
    enabled: Boolean(activeHouseholdId),
  });
  const schedules = schedulesQ.data ?? [];
  const activeScheduleId = scheduleId || schedules[0]?.id || 0;

  const evidenceQ = useQuery({
    queryKey: [
      "preparation-operations",
      activeHouseholdId,
      activeScheduleId,
      "derivation",
    ],
    queryFn: () =>
      preparationScheduleDerivationApi.get(activeHouseholdId, activeScheduleId),
    enabled: Boolean(activeHouseholdId && activeScheduleId),
  });

  useEffect(() => {
    setScheduleId(0);
  }, [activeHouseholdId]);

  const evidence = evidenceQ.data;
  const error = householdsQ.error ?? schedulesQ.error ?? evidenceQ.error ?? null;
  const repaired =
    evidence?.derivation_method
    === "deterministic_minimal_change_preparation_repair_v1";

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <p className="text-sm font-medium text-primary">Preparation operations</p>
          <h1 className="text-3xl font-semibold tracking-tight">
            Schedule derivation evidence
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Inspect whether a persisted schedule was produced by the original
            deterministic scheduler or by an explicitly accepted repair. This is
            read-only provenance and does not approve or execute anything.
          </p>
        </div>

        {error && (
          <Alert variant="destructive" role="alert">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Derivation evidence unavailable</AlertTitle>
            <AlertDescription>{messageOf(error)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Select persisted schedule</CardTitle>
            <CardDescription>
              Viewer access is sufficient; evidence is household-scoped and fail-closed.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="derivation-household">Household</Label>
              <select
                id="derivation-household"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={activeHouseholdId}
                onChange={(event) => setHouseholdId(event.target.value)}
              >
                {households.map((value) => (
                  <option key={value.id} value={value.id}>{value.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="derivation-schedule">Schedule</Label>
              <select
                id="derivation-schedule"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={activeScheduleId || ""}
                onChange={(event) => setScheduleId(Number(event.target.value))}
              >
                {schedules.map((value) => (
                  <option key={value.id} value={value.id}>
                    #{value.id} · {value.status} · version {value.version}
                  </option>
                ))}
              </select>
            </div>
          </CardContent>
        </Card>

        {!activeScheduleId ? (
          <Alert>
            <FileSearch className="h-4 w-4" />
            <AlertTitle>No persisted schedule</AlertTitle>
            <AlertDescription>
              Create or accept a preparation schedule before inspecting derivation.
            </AlertDescription>
          </Alert>
        ) : evidenceQ.isLoading ? (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              Resolving cross-record derivation evidence…
            </CardContent>
          </Card>
        ) : evidence ? (
          <>
            <Alert>
              {repaired ? (
                <GitBranch className="h-4 w-4" />
              ) : (
                <ShieldCheck className="h-4 w-4" />
              )}
              <AlertTitle>{methodLabel(evidence.derivation_method)}</AlertTitle>
              <AlertDescription>
                Evidence complete: {String(evidence.evidence_complete)}. Schedule
                status: {evidence.schedule_status}; version {evidence.schedule_version}.
              </AlertDescription>
            </Alert>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Schedule identity</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Schedule</p>
                  <p className="font-medium">#{evidence.schedule_id}</p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Derivation method</p>
                  <Badge variant="outline" className="mt-1">
                    {methodLabel(evidence.derivation_method)}
                  </Badge>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Schedule hash</p>
                  <p className="font-mono text-xs">{hash(evidence.schedule_hash)}</p>
                </div>
              </CardContent>
            </Card>

            {repaired ? (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Link2 className="h-4 w-4" />
                    Accepted repair chain
                  </CardTitle>
                  <CardDescription>
                    These identities were cross-checked across proposal, acceptance,
                    source schedule, and created schedule records.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">Proposal</p>
                      <p className="font-medium">
                        #{evidence.source_repair_proposal_id} · version {evidence.source_repair_proposal_version}
                      </p>
                    </div>
                    <div className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">Acceptance</p>
                      <p className="font-medium">#{evidence.source_repair_acceptance_id}</p>
                    </div>
                    <div className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">Source schedule</p>
                      <p className="font-medium">
                        #{evidence.source_schedule_id} · version {evidence.source_schedule_version}
                      </p>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                    {[
                      ["Source schedule", evidence.source_schedule_hash],
                      ["Source request", evidence.source_schedule_request_hash],
                      ["Target calendar", evidence.target_calendar_content_hash],
                      ["Repair request", evidence.repair_request_hash],
                      ["Repair result", evidence.repair_result_hash],
                      ["Revised request", evidence.revised_request_hash],
                      ["Repaired response", evidence.repaired_response_hash],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md border p-3">
                        <p className="text-xs text-muted-foreground">{label}</p>
                        <p className="font-mono text-xs">{hash(value)}</p>
                      </div>
                    ))}
                  </div>

                  <div className="rounded-md border p-3 text-sm">
                    <p className="text-xs text-muted-foreground">Accepted by</p>
                    <p className="font-medium">{evidence.accepted_by_user_id}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {evidence.accepted_at
                        ? new Date(evidence.accepted_at).toLocaleString()
                        : "Time unavailable"}
                    </p>
                    <p className="mt-2">{evidence.acceptance_reason}</p>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Alert>
                <ShieldCheck className="h-4 w-4" />
                <AlertTitle>No repair proposal or acceptance applies</AlertTitle>
                <AlertDescription>
                  Original deterministic schedules correctly expose null repair
                  fields rather than fabricating proposal or acceptance provenance.
                </AlertDescription>
              </Alert>
            )}
          </>
        ) : null}
      </div>
    </AppLayout>
  );
}
