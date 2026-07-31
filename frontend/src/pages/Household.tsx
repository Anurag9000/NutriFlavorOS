import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import {
  householdApi,
  type Household,
  type HouseholdRole,
  type PantryItem,
  PlatformApiError,
} from "@/lib/platformApi";
import { AlertCircle, CalendarClock, Home, PackageOpen, Users } from "lucide-react";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The request could not be completed";
}

function formatRange(min: number, max: number, unit: string): string {
  return min === max ? `${min} ${unit}` : `${min}–${max} ${unit}`;
}

function formatDate(value?: string | null): string {
  if (!value) return "Not specified";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function canEdit(role?: HouseholdRole | null): boolean {
  return role === "editor" || role === "owner";
}

export default function HouseholdPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selectedId, setSelectedId] = useState<string>("");
  const [householdName, setHouseholdName] = useState("");
  const [ingredient, setIngredient] = useState("");
  const [quantityMin, setQuantityMin] = useState("1");
  const [quantityMax, setQuantityMax] = useState("1");
  const [unit, setUnit] = useState("count");
  const [expiresAt, setExpiresAt] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<Exclude<HouseholdRole, "owner">>("viewer");
  const [acceptanceToken, setAcceptanceToken] = useState("");
  const [planDays, setPlanDays] = useState("7");

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });

  const households = householdsQ.data ?? [];
  const effectiveSelectedId = selectedId || households[0]?.id || "";
  const selected = useMemo(
    () => households.find((household) => household.id === effectiveSelectedId),
    [households, effectiveSelectedId],
  );

  const detailQ = useQuery({
    queryKey: ["households", effectiveSelectedId, "detail"],
    queryFn: () => householdApi.get(effectiveSelectedId),
    enabled: Boolean(effectiveSelectedId),
  });
  const pantryQ = useQuery({
    queryKey: ["households", effectiveSelectedId, "pantry"],
    queryFn: () => householdApi.pantry(effectiveSelectedId),
    enabled: Boolean(effectiveSelectedId),
  });
  const leftoversQ = useQuery({
    queryKey: ["households", effectiveSelectedId, "leftovers"],
    queryFn: () => householdApi.leftovers(effectiveSelectedId),
    enabled: Boolean(effectiveSelectedId),
  });
  const reservationsQ = useQuery({
    queryKey: ["households", effectiveSelectedId, "reservations"],
    queryFn: () => householdApi.reservations(effectiveSelectedId),
    enabled: Boolean(effectiveSelectedId),
  });
  const eventsQ = useQuery({
    queryKey: ["households", effectiveSelectedId, "events"],
    queryFn: () => householdApi.events(effectiveSelectedId, 50),
    enabled: Boolean(effectiveSelectedId),
  });
  const invitationsQ = useQuery({
    queryKey: ["households", effectiveSelectedId, "invitations"],
    queryFn: () => householdApi.invitations(effectiveSelectedId),
    enabled: Boolean(effectiveSelectedId) && detailQ.data?.role === "owner",
  });
  const shoppingQ = useQuery({
    queryKey: ["households", effectiveSelectedId, "shopping"],
    queryFn: () => householdApi.reconcileShopping(effectiveSelectedId),
    enabled: false,
    retry: false,
  });
  const batchQ = useQuery({
    queryKey: ["households", effectiveSelectedId, "batch-prep"],
    queryFn: () => householdApi.batchPrep(effectiveSelectedId),
    enabled: false,
    retry: false,
  });

  const invalidateHousehold = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["households"] }),
      queryClient.invalidateQueries({ queryKey: ["households", effectiveSelectedId] }),
    ]);
  };

  const createHousehold = useMutation({
    mutationFn: () => householdApi.create(householdName.trim()),
    onSuccess: async (value) => {
      setHouseholdName("");
      setSelectedId(value.id);
      await invalidateHousehold();
      toast({ title: "Household created", description: value.name });
    },
    onError: (error) => toast({ title: "Household creation failed", description: messageOf(error), variant: "destructive" }),
  });

  const addPantry = useMutation({
    mutationFn: () => householdApi.addPantry(effectiveSelectedId, {
      ingredient_name: ingredient.trim(),
      quantity: {
        quantity_min: Number(quantityMin),
        quantity_max: Number(quantityMax),
        unit: unit.trim(),
      },
      expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      source: "manual",
      idempotency_key: crypto.randomUUID(),
    }),
    onSuccess: async () => {
      setIngredient("");
      setQuantityMin("1");
      setQuantityMax("1");
      setExpiresAt("");
      await invalidateHousehold();
      toast({ title: "Pantry lot recorded" });
    },
    onError: (error) => toast({ title: "Pantry update failed", description: messageOf(error), variant: "destructive" }),
  });

  const invite = useMutation({
    mutationFn: () => householdApi.createInvitation(effectiveSelectedId, {
      email: inviteEmail.trim(),
      role: inviteRole,
      expires_in_hours: 72,
    }),
    onSuccess: async (value) => {
      setInviteEmail("");
      await queryClient.invalidateQueries({ queryKey: ["households", effectiveSelectedId, "invitations"] });
      toast({
        title: "Invitation created",
        description: value.acceptance_token
          ? "Copy the one-time token now; it is not stored in plaintext."
          : "Invitation created.",
      });
    },
    onError: (error) => toast({ title: "Invitation failed", description: messageOf(error), variant: "destructive" }),
  });

  const acceptInvitation = useMutation({
    mutationFn: () => householdApi.acceptInvitation(acceptanceToken.trim()),
    onSuccess: async () => {
      setAcceptanceToken("");
      await queryClient.invalidateQueries({ queryKey: ["households"] });
      toast({ title: "Invitation accepted" });
    },
    onError: (error) => toast({ title: "Invitation could not be accepted", description: messageOf(error), variant: "destructive" }),
  });

  const generatePlan = useMutation({
    mutationFn: () => householdApi.generatePlan(effectiveSelectedId, {
      days: Number(planDays),
      reserve_inventory: true,
      reservation_hours: 48,
    }),
    onSuccess: async (value) => {
      await invalidateHousehold();
      toast({
        title: "Household plan created",
        description: `${value.target_summary.member_count} active member target(s); pantry coverage score ${value.pantry_coverage_score.toFixed(3)}.`,
      });
    },
    onError: (error) => toast({ title: "Planning failed", description: messageOf(error), variant: "destructive" }),
  });

  const consumePantry = useMutation({
    mutationFn: ({ item, amount }: { item: PantryItem; amount: number }) => householdApi.consumePantry(effectiveSelectedId, item.id, {
      quantity: { quantity_min: amount, quantity_max: amount, unit: item.unit },
      expected_version: item.version,
      reason: "manual consumption",
      idempotency_key: crypto.randomUUID(),
    }),
    onSuccess: invalidateHousehold,
    onError: (error) => toast({ title: "Consumption failed", description: messageOf(error), variant: "destructive" }),
  });

  const role = detailQ.data?.role ?? selected?.current_role;
  const pageError = householdsQ.error || detailQ.error;

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Household and pantry</h1>
          <p className="text-sm text-muted-foreground">
            Transactional lots, member roles, leftovers, plan reservations, and conservative shopping reconciliation.
          </p>
        </div>

        {pageError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Household data unavailable</AlertTitle>
            <AlertDescription>{messageOf(pageError)}</AlertDescription>
          </Alert>
        )}

        <div className="grid gap-4 lg:grid-cols-[1fr_2fr]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Households</CardTitle>
              <CardDescription>Create or select a household you can access.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                {households.length === 0 && <p className="text-sm text-muted-foreground">No household exists yet.</p>}
                {households.map((household: Household) => (
                  <button
                    type="button"
                    key={household.id}
                    onClick={() => setSelectedId(household.id)}
                    className={`w-full rounded-md border p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${household.id === effectiveSelectedId ? "border-primary bg-primary/5" : "border-border"}`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-medium">{household.name}</span>
                      <Badge variant="outline">{household.current_role ?? "member"}</Badge>
                    </span>
                    <span className="mt-1 block text-xs text-muted-foreground">{household.timezone}</span>
                  </button>
                ))}
              </div>
              <form
                className="space-y-2 border-t pt-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (householdName.trim()) createHousehold.mutate();
                }}
              >
                <Label htmlFor="household-name">New household</Label>
                <Input id="household-name" value={householdName} onChange={(event) => setHouseholdName(event.target.value)} maxLength={120} required />
                <Button type="submit" disabled={createHousehold.isPending}>Create household</Button>
              </form>
              <form
                className="space-y-2 border-t pt-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (acceptanceToken.trim()) acceptInvitation.mutate();
                }}
              >
                <Label htmlFor="invitation-token">Accept invitation token</Label>
                <Input id="invitation-token" value={acceptanceToken} onChange={(event) => setAcceptanceToken(event.target.value)} autoComplete="off" />
                <Button type="submit" variant="outline" disabled={acceptInvitation.isPending}>Accept invitation</Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><Home className="h-4 w-4" />{detailQ.data?.household.name ?? "Select a household"}</CardTitle>
              <CardDescription>{detailQ.data?.planning_status ?? "Household details will appear here."}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-3">
              <div><p className="text-xs text-muted-foreground">Your role</p><p className="font-medium capitalize">{role ?? "—"}</p></div>
              <div><p className="text-xs text-muted-foreground">Active members</p><p className="font-medium">{detailQ.data?.members.filter((member) => member.active).length ?? 0}</p></div>
              <div><p className="text-xs text-muted-foreground">Serving multiplier</p><p className="font-medium">{detailQ.data?.active_servings_multiplier ?? 0}</p></div>
            </CardContent>
          </Card>
        </div>

        {effectiveSelectedId && (
          <Tabs defaultValue="pantry" className="space-y-4">
            <TabsList className="flex h-auto flex-wrap justify-start">
              <TabsTrigger value="pantry">Pantry</TabsTrigger>
              <TabsTrigger value="members">Members</TabsTrigger>
              <TabsTrigger value="planning">Planning</TabsTrigger>
              <TabsTrigger value="leftovers">Leftovers</TabsTrigger>
              <TabsTrigger value="events">Audit events</TabsTrigger>
            </TabsList>

            <TabsContent value="pantry" className="space-y-4">
              {canEdit(role) && (
                <Card>
                  <CardHeader><CardTitle className="text-base">Record a pantry lot</CardTitle><CardDescription>Quantities are stored as intervals; incompatible unit dimensions are rejected.</CardDescription></CardHeader>
                  <CardContent>
                    <form
                      className="grid gap-3 md:grid-cols-6"
                      onSubmit={(event) => {
                        event.preventDefault();
                        addPantry.mutate();
                      }}
                    >
                      <div className="space-y-1 md:col-span-2"><Label htmlFor="ingredient">Ingredient</Label><Input id="ingredient" value={ingredient} onChange={(event) => setIngredient(event.target.value)} required /></div>
                      <div className="space-y-1"><Label htmlFor="quantity-min">Minimum</Label><Input id="quantity-min" type="number" min="0" step="any" value={quantityMin} onChange={(event) => setQuantityMin(event.target.value)} required /></div>
                      <div className="space-y-1"><Label htmlFor="quantity-max">Maximum</Label><Input id="quantity-max" type="number" min="0" step="any" value={quantityMax} onChange={(event) => setQuantityMax(event.target.value)} required /></div>
                      <div className="space-y-1"><Label htmlFor="unit">Unit</Label><Input id="unit" value={unit} onChange={(event) => setUnit(event.target.value)} required /></div>
                      <div className="space-y-1"><Label htmlFor="expiry">Expiry</Label><Input id="expiry" type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} /></div>
                      <Button className="md:col-span-6 md:w-fit" type="submit" disabled={addPantry.isPending}>Add lot</Button>
                    </form>
                  </CardContent>
                </Card>
              )}
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {(pantryQ.data ?? []).map((item) => (
                  <Card key={item.id}>
                    <CardContent className="space-y-3 p-4">
                      <div className="flex items-start justify-between gap-2"><div><p className="font-medium">{item.display_name}</p><p className="text-xs text-muted-foreground">{item.canonical_name}</p></div><Badge variant="outline">v{item.version}</Badge></div>
                      <p className="text-lg font-semibold">{formatRange(item.quantity_min, item.quantity_max, item.unit)}</p>
                      <p className="text-xs text-muted-foreground">Expires: {formatDate(item.expires_at)}</p>
                      {canEdit(role) && item.quantity_max > 0 && (
                        <Button type="button" size="sm" variant="outline" onClick={() => consumePantry.mutate({ item, amount: Math.min(1, item.quantity_min || item.quantity_max) })} disabled={consumePantry.isPending}>Consume one unit</Button>
                      )}
                    </CardContent>
                  </Card>
                ))}
                {!pantryQ.isLoading && (pantryQ.data?.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No active pantry lots.</p>}
              </div>
            </TabsContent>

            <TabsContent value="members" className="space-y-4">
              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Users className="h-4 w-4" />Members</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {(detailQ.data?.members ?? []).map((member) => (
                    <div key={member.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3">
                      <div><p className="font-medium">{member.display_name}</p><p className="text-xs text-muted-foreground">{member.role} · serving multiplier {member.servings_multiplier} · {member.active ? "active" : "inactive"}</p></div>
                      <div className="flex flex-wrap gap-1">{member.allergies.map((value) => <Badge key={value} variant="destructive">{value}</Badge>)}{member.dietary_restrictions.map((value) => <Badge key={value} variant="secondary">{value}</Badge>)}</div>
                    </div>
                  ))}
                </CardContent>
              </Card>
              {role === "owner" && (
                <Card>
                  <CardHeader><CardTitle className="text-base">Invite a member</CardTitle><CardDescription>Invitations are email-bound, expiring, and single-use. Ownership cannot be assigned here.</CardDescription></CardHeader>
                  <CardContent className="space-y-4">
                    <form className="grid gap-3 sm:grid-cols-[1fr_140px_auto]" onSubmit={(event) => { event.preventDefault(); invite.mutate(); }}>
                      <Input aria-label="Invitee email" type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} required />
                      <select aria-label="Invitation role" value={inviteRole} onChange={(event) => setInviteRole(event.target.value as Exclude<HouseholdRole, "owner">)} className="rounded-md border border-input bg-background px-3 py-2 text-sm"><option value="viewer">Viewer</option><option value="editor">Editor</option></select>
                      <Button type="submit" disabled={invite.isPending}>Create invite</Button>
                    </form>
                    {(invitationsQ.data ?? []).map((invitation) => (
                      <div key={invitation.id} className="rounded-md border p-3 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2"><span>{invitation.invited_email}</span><Badge variant="outline">{invitation.role}</Badge></div>
                        <p className="mt-1 text-xs text-muted-foreground">Expires {formatDate(invitation.expires_at)}</p>
                        {invitation.acceptance_token && <code className="mt-2 block overflow-x-auto rounded bg-muted p-2 text-xs">{invitation.acceptance_token}</code>}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="planning" className="space-y-4">
              <Card>
                <CardHeader><CardTitle className="text-base">Household planning and inventory reservation</CardTitle><CardDescription>Hard restrictions are unioned across active members. Inventory is reserved first and consumed only through an explicit commit.</CardDescription></CardHeader>
                <CardContent className="flex flex-wrap items-end gap-3">
                  <div className="space-y-1"><Label htmlFor="plan-days">Days</Label><Input id="plan-days" className="w-28" type="number" min="1" max="31" value={planDays} onChange={(event) => setPlanDays(event.target.value)} /></div>
                  <Button type="button" onClick={() => generatePlan.mutate()} disabled={!canEdit(role) || generatePlan.isPending}>Generate and reserve</Button>
                  <Button type="button" variant="outline" onClick={() => shoppingQ.refetch()}>Load reconciled shopping</Button>
                  <Button type="button" variant="outline" onClick={() => batchQ.refetch()}>Load batch preparation</Button>
                </CardContent>
              </Card>
              <div className="grid gap-4 lg:grid-cols-2">
                <Card><CardHeader><CardTitle className="text-base">Active reservations</CardTitle></CardHeader><CardContent className="space-y-2">{(reservationsQ.data ?? []).map((reservation) => <div key={reservation.id} className="rounded border p-3 text-sm"><div className="flex justify-between gap-2"><span className="font-medium">{reservation.canonical_name}</span><Badge variant="outline">{reservation.status}</Badge></div><p>{formatRange(reservation.quantity_min, reservation.quantity_max, reservation.unit)}</p><p className="text-xs text-muted-foreground">Expires {formatDate(reservation.expires_at)}</p></div>)}{!reservationsQ.isLoading && (reservationsQ.data?.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No active reservations.</p>}</CardContent></Card>
                <Card><CardHeader><CardTitle className="text-base">Shopping reconciliation</CardTitle></CardHeader><CardContent className="space-y-2">{shoppingQ.error && <p className="text-sm text-destructive">{messageOf(shoppingQ.error)}</p>}{(shoppingQ.data ?? []).map((item) => <div key={`${item.canonical_name}-${item.unit}`} className="rounded border p-3 text-sm"><div className="flex justify-between gap-2"><span className="font-medium">{item.display_name}</span><Badge variant="outline">{item.coverage_status}</Badge></div><p>Buy {formatRange(item.buy_min, item.buy_max, item.unit)}</p><p className="text-xs text-muted-foreground">Required {formatRange(item.required_min, item.required_max, item.unit)}; pantry {formatRange(item.pantry_min, item.pantry_max, item.unit)}</p></div>)}</CardContent></Card>
              </div>
              {(batchQ.data?.length ?? 0) > 0 && <Card><CardHeader><CardTitle className="text-base">Batch preparation</CardTitle></CardHeader><CardContent className="space-y-2">{batchQ.data?.map((task) => <div key={task.recipe_id} className="rounded border p-3 text-sm"><p className="font-medium">{task.recipe_name}</p><p>{task.total_portions} portions across {task.occurrences} occurrence(s); prepare day {task.scheduled_day}</p><p className="text-xs text-muted-foreground">Storage status: {task.storage_guidance_status}</p></div>)}</CardContent></Card>}
            </TabsContent>

            <TabsContent value="leftovers">
              <Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><PackageOpen className="h-4 w-4" />Leftovers</CardTitle><CardDescription>No shelf life is inferred without a reviewed storage policy.</CardDescription></CardHeader><CardContent className="space-y-2">{(leftoversQ.data ?? []).map((leftover) => <div key={leftover.id} className="rounded border p-3 text-sm"><div className="flex justify-between gap-2"><span className="font-medium">Recipe {leftover.recipe_id}</span><Badge variant="outline">{leftover.frozen ? "frozen" : "refrigerated"}</Badge></div><p>{leftover.portions_available} portions</p><p className="text-xs text-muted-foreground">Cooked {formatDate(leftover.cooked_at)} · expires {formatDate(leftover.expires_at)} · policy {leftover.storage_policy_key ?? "not assigned"}</p></div>)}{!leftoversQ.isLoading && (leftoversQ.data?.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No active leftovers.</p>}</CardContent></Card>
            </TabsContent>

            <TabsContent value="events">
              <Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarClock className="h-4 w-4" />Inventory audit events</CardTitle></CardHeader><CardContent className="space-y-2">{(eventsQ.data ?? []).map((event) => <div key={event.id} className="grid gap-1 rounded border p-3 text-sm sm:grid-cols-[160px_1fr_auto]"><span className="capitalize">{event.event_type.replaceAll("_", " ")}</span><span>{formatRange(event.quantity_min, event.quantity_max, event.unit)}{event.reason ? ` · ${event.reason}` : ""}</span><span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span></div>)}</CardContent></Card>
            </TabsContent>
          </Tabs>
        )}

        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Safety boundary</AlertTitle>
          <AlertDescription>Household targets and storage policies are planning aids, not medical, allergy, medication-interaction, or food-safety guarantees.</AlertDescription>
        </Alert>
      </div>
    </AppLayout>
  );
}
