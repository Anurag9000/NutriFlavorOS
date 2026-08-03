import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Download,
  FileJson,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

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
import {
  preparationScheduleSupportExportApi,
  serializeSupportExport,
  supportExportFilename,
} from "@/lib/preparationScheduleSupportExportApi";

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The support evidence snapshot could not be generated";
}

function shortHash(value: string): string {
  return `${value.slice(0, 16)}…${value.slice(-10)}`;
}

export default function PreparationScheduleSupportExportPage() {
  const [householdId, setHouseholdId] = useState("");
  const [scheduleId, setScheduleId] = useState(0);
  const [downloadMessage, setDownloadMessage] = useState("");

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const activeHouseholdId = householdId || households[0]?.id || "";

  const schedulesQ = useQuery({
    queryKey: ["preparation-operations", activeHouseholdId, "support-schedules"],
    queryFn: () => preparationOperationsApi.schedules(activeHouseholdId),
    enabled: Boolean(activeHouseholdId),
  });
  const schedules = schedulesQ.data ?? [];
  const activeScheduleId = scheduleId || schedules[0]?.id || 0;

  const exportM = useMutation({
    mutationFn: () =>
      preparationScheduleSupportExportApi.get(
        activeHouseholdId,
        activeScheduleId,
      ),
    onSuccess: () => setDownloadMessage("Read-only snapshot generated."),
  });

  useEffect(() => {
    setScheduleId(0);
    setDownloadMessage("");
    exportM.reset();
    // Reset only when household scope changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeHouseholdId]);

  const selectSchedule = (value: number) => {
    setScheduleId(value);
    setDownloadMessage("");
    exportM.reset();
  };

  const download = () => {
    const value = exportM.data;
    if (!value) return;
    const blob = new Blob([serializeSupportExport(value)], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = supportExportFilename(value);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setDownloadMessage(`Downloaded ${anchor.download}.`);
  };

  const error = householdsQ.error ?? schedulesQ.error ?? exportM.error ?? null;
  const value = exportM.data;
  const proposalEventCount = value
    ? Object.values(value.repair_proposal_events).reduce(
        (total, events) => total + events.length,
        0,
      )
    : 0;

  return (
    <AppLayout>
      <main id="main-content" className="mx-auto max-w-6xl space-y-6">
        <div>
          <p className="text-sm font-medium text-primary">Preparation operations</p>
          <h1 className="text-3xl font-semibold tracking-tight">
            Preparation schedule support export
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Generate one server-authoritative, hash-addressed evidence snapshot for
            a persisted schedule. Nothing is generated automatically, and this page
            never changes lifecycle or task state.
          </p>
        </div>

        {error && (
          <Alert variant="destructive" role="alert">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Support export unavailable</AlertTitle>
            <AlertDescription>{messageOf(error)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Select evidence scope</CardTitle>
            <CardDescription>
              Household viewer access is sufficient. Cross-household resources remain
              undisclosed.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="support-export-household">Household</Label>
              <select
                id="support-export-household"
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
              <Label htmlFor="support-export-schedule">Schedule</Label>
              <select
                id="support-export-schedule"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={activeScheduleId || ""}
                onChange={(event) => selectSchedule(Number(event.target.value))}
                disabled={!schedules.length}
              >
                {schedules.map((schedule) => (
                  <option key={schedule.id} value={schedule.id}>
                    #{schedule.id} · {schedule.status} · version {schedule.version}
                  </option>
                ))}
              </select>
            </div>
          </CardContent>
        </Card>

        {!activeScheduleId ? (
          <Alert>
            <FileJson className="h-4 w-4" />
            <AlertTitle>No persisted schedule</AlertTitle>
            <AlertDescription>
              Create or accept a preparation schedule before generating support evidence.
            </AlertDescription>
          </Alert>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Generate snapshot</CardTitle>
              <CardDescription>
                PostgreSQL exports use one repeatable-read, read-only transaction.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button
                type="button"
                onClick={() => exportM.mutate()}
                disabled={exportM.isPending}
              >
                {exportM.isPending ? (
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ShieldCheck className="mr-2 h-4 w-4" />
                )}
                {exportM.isPending
                  ? "Generating read-only snapshot…"
                  : value
                    ? "Generate fresh snapshot"
                    : "Generate read-only snapshot"}
              </Button>
              <p className="text-sm text-muted-foreground" aria-live="polite">
                {downloadMessage}
              </p>
            </CardContent>
          </Card>
        )}

        {value && (
          <>
            <Alert>
              <ShieldCheck className="h-4 w-4" />
              <AlertTitle>Server evidence snapshot ready</AlertTitle>
              <AlertDescription>
                Schedule #{value.schedule_id}, status {value.schedule.status}, version {value.schedule.version}.
                The server reports no mutation, execution verification, or food-safety verification.
              </AlertDescription>
            </Alert>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Snapshot identity</CardTitle>
                <CardDescription>
                  Download preserves the complete response object and server evidence hash.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-md border p-3">
                    <p className="text-xs text-muted-foreground">Evidence hash</p>
                    <p className="font-mono text-sm" title={value.evidence_hash}>
                      {shortHash(value.evidence_hash)}
                    </p>
                  </div>
                  <div className="rounded-md border p-3">
                    <p className="text-xs text-muted-foreground">Database snapshot</p>
                    <p className="text-sm font-medium">
                      {value.database_dialect} · {value.snapshot_isolation}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Read only: {String(value.snapshot_read_only)}
                    </p>
                  </div>
                  <div className="rounded-md border p-3">
                    <p className="text-xs text-muted-foreground">Derivation</p>
                    <p className="text-sm font-medium">
                      {value.derivation.derivation_method}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Evidence complete: {String(value.derivation.evidence_complete)}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2" aria-label="Evidence counts">
                  <Badge variant="secondary">
                    {value.schedule_events.length} schedule events
                  </Badge>
                  <Badge variant="secondary">
                    {value.task_execution.events.length} task events
                  </Badge>
                  <Badge variant="secondary">
                    {value.related_repair_proposals.length} repair proposals
                  </Badge>
                  <Badge variant="secondary">
                    {value.repair_acceptances.length} acceptances
                  </Badge>
                  <Badge variant="secondary">
                    {proposalEventCount} proposal events
                  </Badge>
                </div>

                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Execution eligibility</p>
                  <p className="text-sm font-medium">
                    {value.task_execution_eligibility.reason_code}
                  </p>
                  {value.task_execution_eligibility.replacement_schedule_id && (
                    <p className="text-xs text-muted-foreground">
                      Replacement schedule #{value.task_execution_eligibility.replacement_schedule_id}
                    </p>
                  )}
                </div>

                <Button type="button" variant="outline" onClick={download}>
                  <Download className="mr-2 h-4 w-4" />
                  Download JSON evidence
                </Button>
              </CardContent>
            </Card>

            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Interpretation boundary</AlertTitle>
              <AlertDescription>
                Mutation performed: false. Actual execution verified: false. Food safety
                verified: false. This package records stored evidence only.
              </AlertDescription>
            </Alert>
          </>
        )}
      </main>
    </AppLayout>
  );
}
