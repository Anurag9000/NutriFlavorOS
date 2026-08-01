import { useQuery } from "@tanstack/react-query";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { householdApi, type Leftover } from "@/lib/platformApi";
import { FileWarning, ShieldCheck } from "lucide-react";

function formatDate(value?: string | null): string {
  if (!value) return "not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function shortHash(value: string): string {
  return value.length <= 16 ? value : `${value.slice(0, 12)}…${value.slice(-4)}`;
}

interface LeftoverPolicyProvenanceProps {
  householdId: string;
  leftover: Leftover;
}

export default function LeftoverPolicyProvenance({
  householdId,
  leftover,
}: LeftoverPolicyProvenanceProps) {
  const provenanceQ = useQuery({
    queryKey: [
      "households",
      householdId,
      "leftovers",
      leftover.id,
      "storage-policy",
    ],
    queryFn: () => householdApi.leftoverStoragePolicy(householdId, leftover.id),
    enabled: Boolean(householdId && leftover.storage_policy_key),
    retry: false,
    staleTime: 30 * 60_000,
  });

  if (!leftover.storage_policy_key) {
    return (
      <p className="text-xs text-muted-foreground">
        No immutable storage-policy version was selected for this leftover.
      </p>
    );
  }

  if (provenanceQ.isLoading) {
    return (
      <p className="text-xs text-muted-foreground">
        Loading exact storage-policy provenance…
      </p>
    );
  }

  if (provenanceQ.error || !provenanceQ.data) {
    return (
      <Alert variant="destructive" className="py-2">
        <FileWarning className="h-4 w-4" />
        <AlertTitle className="text-xs">Exact policy provenance unavailable</AlertTitle>
        <AlertDescription className="text-xs">
          This may be a legacy leftover that retained only policy key {leftover.storage_policy_key}.
        </AlertDescription>
      </Alert>
    );
  }

  const policy = provenanceQ.data;
  return (
    <div className="space-y-2 rounded-md border bg-muted/20 p-3 text-xs">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="flex items-center gap-1 font-medium">
            <ShieldCheck className="h-3.5 w-3.5" />Exact policy record #{policy.id}
          </p>
          <p className="text-muted-foreground">
            {policy.policy_key} · version {policy.policy_version}
          </p>
        </div>
        <Badge variant={policy.active ? "default" : "secondary"}>
          {policy.active ? "active reviewed" : "historical inactive"}
        </Badge>
      </div>
      <p>
        {policy.food_category} · {policy.storage_state} · {policy.duration_min_hours ?? "?"}–{policy.duration_max_hours ?? "?"} hours
        {policy.maximum_temperature_c !== null && policy.maximum_temperature_c !== undefined
          ? ` at or below ${policy.maximum_temperature_c}°C`
          : ""}
      </p>
      <p className="text-muted-foreground">
        Reviewed by {policy.reviewed_by ?? "not recorded"} · {formatDate(policy.reviewed_at)}
      </p>
      <p className="text-muted-foreground">
        {policy.source_name} · source {policy.source_version} · scope {policy.safety_scope.replaceAll("_", " ")}
      </p>
      <p className="text-muted-foreground">
        SHA-256 <code title={policy.content_hash}>{shortHash(policy.content_hash)}</code>
      </p>
      {policy.supersedes_policy_id && (
        <p className="text-muted-foreground">
          Supersedes policy record #{policy.supersedes_policy_id}
        </p>
      )}
    </div>
  );
}
