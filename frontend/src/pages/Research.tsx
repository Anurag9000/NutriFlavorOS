import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { evidenceApi, researchApi, type StoragePolicy } from "@/lib/platformApi";
import { Beaker, Database, FlaskConical, Info, ShieldCheck } from "lucide-react";

const collections = ["tasks", "datasets", "models", "experiments", "features"] as const;
type CollectionName = (typeof collections)[number];

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The request could not be completed";
}

function label(value: unknown): string {
  if (typeof value !== "string") return "unspecified";
  return value.replaceAll("_", " ");
}

function itemName(item: Record<string, unknown>): string {
  return String(item.name ?? item.title ?? item.id ?? "Unnamed catalog item");
}

function itemId(item: Record<string, unknown>): string {
  return String(item.id ?? item.name ?? crypto.randomUUID());
}

function statusVariant(value: unknown): "default" | "secondary" | "destructive" | "outline" {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized.includes("clinical") || normalized.includes("high")) return "destructive";
  if (normalized.includes("executable") || normalized.includes("implemented")) return "default";
  if (normalized.includes("research") || normalized.includes("optional")) return "secondary";
  return "outline";
}

export default function ResearchPage() {
  const [collection, setCollection] = useState<CollectionName>("models");
  const [query, setQuery] = useState("");
  const [readiness, setReadiness] = useState("");
  const [risk, setRisk] = useState("");

  const catalogQ = useQuery({
    queryKey: ["research", "catalog"],
    queryFn: researchApi.catalog,
    staleTime: 5 * 60_000,
  });
  const collectionQ = useQuery({
    queryKey: ["research", collection, readiness, risk],
    queryFn: () => researchApi.collection(collection, readiness || undefined, risk || undefined),
    staleTime: 5 * 60_000,
  });
  const policiesQ = useQuery({
    queryKey: ["food-evidence", "storage-policies"],
    queryFn: () => evidenceApi.storagePolicies(),
    staleTime: 30 * 60_000,
  });
  const conversionsQ = useQuery({
    queryKey: ["food-evidence", "conversions"],
    queryFn: () => evidenceApi.conversions(),
    staleTime: 30 * 60_000,
  });

  const items = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const values = (collectionQ.data?.items ?? []) as Record<string, unknown>[];
    if (!needle) return values;
    return values.filter((item) => JSON.stringify(item).toLowerCase().includes(needle));
  }, [collectionQ.data, query]);

  const summary = catalogQ.data?.summary ?? {};
  const implemented = catalogQ.data?.implemented_components ?? {};
  const executableCount = Object.keys(implemented).length;

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Research registry</h1>
          <p className="text-sm text-muted-foreground">
            Versioned task, dataset, model, experiment, and feature contracts with explicit implementation and risk states.
          </p>
        </div>

        {(catalogQ.error || collectionQ.error) && (
          <Alert variant="destructive">
            <Info className="h-4 w-4" />
            <AlertTitle>Research registry unavailable</AlertTitle>
            <AlertDescription>{messageOf(catalogQ.error || collectionQ.error)}</AlertDescription>
          </Alert>
        )}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
          {collections.map((name) => {
            const counts = summary[name] ?? {};
            const total = Object.values(counts).reduce((sum, value) => sum + Number(value || 0), 0);
            return (
              <Card key={name}>
                <CardContent className="p-4">
                  <p className="text-xs capitalize text-muted-foreground">{name}</p>
                  <p className="text-2xl font-bold">{total}</p>
                  <p className="text-xs text-muted-foreground">registered contracts</p>
                </CardContent>
              </Card>
            );
          })}
          <Card>
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">Runtime registry</p>
              <p className="text-2xl font-bold">{executableCount}</p>
              <p className="text-xs text-muted-foreground">reported components</p>
            </CardContent>
          </Card>
        </div>

        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Governance boundary</AlertTitle>
          <AlertDescription>
            A catalog entry is not a trained or deployed model. HTTP routes validate metadata and diagnostics only; experiment execution remains an offline, whitelisted workflow with artifact, provenance, evaluation, and promotion gates.
          </AlertDescription>
        </Alert>

        <Tabs defaultValue="catalog" className="space-y-4">
          <TabsList className="flex h-auto flex-wrap justify-start">
            <TabsTrigger value="catalog">Catalog</TabsTrigger>
            <TabsTrigger value="implemented">Implemented components</TabsTrigger>
            <TabsTrigger value="evidence">Food evidence</TabsTrigger>
          </TabsList>

          <TabsContent value="catalog" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Catalog browser</CardTitle>
                <CardDescription>Filter contracts by collection, readiness, risk, or free text.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-4">
                <div className="space-y-1">
                  <Label htmlFor="collection">Collection</Label>
                  <select id="collection" value={collection} onChange={(event) => setCollection(event.target.value as CollectionName)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    {collections.map((name) => <option key={name} value={name}>{name}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="readiness">Readiness</Label>
                  <Input id="readiness" placeholder="e.g. executable" value={readiness} onChange={(event) => setReadiness(event.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="risk">Risk</Label>
                  <Input id="risk" placeholder="e.g. moderate" value={risk} onChange={(event) => setRisk(event.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="catalog-search">Search</Label>
                  <Input id="catalog-search" value={query} onChange={(event) => setQuery(event.target.value)} />
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-3 lg:grid-cols-2">
              {items.map((item) => (
                <Card key={itemId(item)}>
                  <CardHeader className="pb-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <CardTitle className="text-base">{itemName(item)}</CardTitle>
                        <CardDescription>{String(item.id ?? "No identifier")}</CardDescription>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {item.readiness !== undefined && <Badge variant={statusVariant(item.readiness)}>{label(item.readiness)}</Badge>}
                        {item.risk !== undefined && <Badge variant={statusVariant(item.risk)}>{label(item.risk)}</Badge>}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    {typeof item.description === "string" && <p>{item.description}</p>}
                    {typeof item.family === "string" && <p><span className="text-muted-foreground">Family:</span> {label(item.family)}</p>}
                    {Array.isArray(item.tasks) && <p><span className="text-muted-foreground">Tasks:</span> {item.tasks.join(", ")}</p>}
                    {Array.isArray(item.datasets) && <p><span className="text-muted-foreground">Datasets:</span> {item.datasets.join(", ")}</p>}
                    {Array.isArray(item.models) && <p><span className="text-muted-foreground">Models:</span> {item.models.join(", ")}</p>}
                    {typeof item.default_enabled === "boolean" && <p><span className="text-muted-foreground">Default enabled:</span> {item.default_enabled ? "yes" : "no"}</p>}
                  </CardContent>
                </Card>
              ))}
              {!collectionQ.isLoading && items.length === 0 && <p className="text-sm text-muted-foreground">No catalog items match these filters.</p>}
            </div>
          </TabsContent>

          <TabsContent value="implemented" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><FlaskConical className="h-4 w-4" />Runtime capability registry</CardTitle>
                <CardDescription>These entries describe code availability, not benchmark quality or production approval.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(implemented).map(([id, value]) => {
                  const detail = value && typeof value === "object" ? value as Record<string, unknown> : { status: value };
                  return (
                    <div key={id} className="rounded-md border p-3 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <code className="font-medium">{id}</code>
                        <Badge variant={statusVariant(detail.status ?? detail.readiness)}>{label(detail.status ?? detail.readiness)}</Badge>
                      </div>
                      {typeof detail.description === "string" && <p className="mt-2 text-muted-foreground">{detail.description}</p>}
                      {typeof detail.production_enabled === "boolean" && <p className="mt-1 text-xs text-muted-foreground">Production enabled: {detail.production_enabled ? "yes" : "no"}</p>}
                    </div>
                  );
                })}
                {!catalogQ.isLoading && executableCount === 0 && <p className="text-sm text-muted-foreground">No runtime capability metadata was returned.</p>}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="evidence" className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Database className="h-4 w-4" />Ingredient-specific conversions</CardTitle><CardDescription>Only reviewed, ingredient-specific conversion evidence can bridge incompatible units.</CardDescription></CardHeader>
                <CardContent className="space-y-2">
                  {(conversionsQ.data ?? []).map((conversion) => (
                    <div key={conversion.id} className="rounded-md border p-3 text-sm">
                      <div className="flex items-center justify-between gap-2"><span className="font-medium">{conversion.canonical_name}</span><Badge variant="outline">{conversion.evidence_status}</Badge></div>
                      <p>{conversion.from_unit} → {conversion.multiplier_min === conversion.multiplier_max ? conversion.multiplier_min : `${conversion.multiplier_min}–${conversion.multiplier_max}`} {conversion.to_unit}</p>
                      <p className="text-xs text-muted-foreground">{conversion.source_name} · {conversion.source_version}</p>
                    </div>
                  ))}
                  {!conversionsQ.isLoading && (conversionsQ.data?.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No conversion evidence is registered.</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Beaker className="h-4 w-4" />Reviewed storage policies</CardTitle><CardDescription>Policies retain their temperature assumptions, source, review date, and safety scope.</CardDescription></CardHeader>
                <CardContent className="space-y-2">
                  {(policiesQ.data ?? []).map((policy: StoragePolicy) => (
                    <div key={policy.id} className="rounded-md border p-3 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{policy.food_category}</span><Badge variant="outline">{policy.storage_state}</Badge></div>
                      <p>{policy.duration_min_hours ?? "?"}–{policy.duration_max_hours ?? "?"} hours{policy.maximum_temperature_c !== null && policy.maximum_temperature_c !== undefined ? ` at or below ${policy.maximum_temperature_c}°C` : ""}</p>
                      <p className="text-xs text-muted-foreground">{policy.source_name} · reviewed {new Date(policy.reviewed_at).toLocaleDateString()}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{policy.safety_scope}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex justify-end">
          <Button variant="outline" type="button" onClick={() => void Promise.all([catalogQ.refetch(), collectionQ.refetch(), policiesQ.refetch(), conversionsQ.refetch()])}>Refresh registry</Button>
        </div>
      </div>
    </AppLayout>
  );
}
