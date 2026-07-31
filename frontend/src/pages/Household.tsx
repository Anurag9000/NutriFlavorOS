import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import {
  evidenceApi,
  householdApi,
  type Household,
  type HouseholdInvitation,
  type HouseholdMember,
  type HouseholdRole,
  type Leftover,
  type PantryItem,
  type Reservation,
  type StoragePolicy,
} from "@/lib/platformApi";
import {
  AlertCircle,
  CalendarClock,
  Check,
  Clipboard,
  Home,
  PackageOpen,
  ShieldCheck,
  Users,
} from "lucide-react";

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

function splitList(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function optionalIso(value: string): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) throw new Error("Enter a valid date and time");
  return parsed.toISOString();
}

function positiveNumber(value: string, label: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${label} must be greater than zero`);
  }
  return parsed;
}

function nonNegativeNumber(value: string, label: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    throw new Error(`${label} must be zero or greater`);
  }
  return parsed;
}

function idempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

interface OneTimeInvite {
  invitationId: string;
  householdId: string;
  email: string;
  expiresAt: string;
  token: string;
}

interface MemberDraft {
  displayName: string;
  role: Exclude<HouseholdRole, "owner">;
  servingsMultiplier: string;
  allergies: string;
  restrictions: string;
  dislikes: string;
}

const EMPTY_MEMBER: MemberDraft = {
  displayName: "",
  role: "viewer",
  servingsMultiplier: "1",
  allergies: "",
  restrictions: "",
  dislikes: "",
};

export default function HouseholdPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [selectedId, setSelectedId] = useState("");
  const [householdName, setHouseholdName] = useState("");
  const [acceptanceToken, setAcceptanceToken] = useState("");
  const [oneTimeInvite, setOneTimeInvite] = useState<OneTimeInvite | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<Exclude<HouseholdRole, "owner">>("viewer");
  const [memberDraft, setMemberDraft] = useState<MemberDraft>(EMPTY_MEMBER);

  const [ingredient, setIngredient] = useState("");
  const [quantityMin, setQuantityMin] = useState("1");
  const [quantityMax, setQuantityMax] = useState("1");
  const [unit, setUnit] = useState("count");
  const [expiresAt, setExpiresAt] = useState("");
  const [pantryAmounts, setPantryAmounts] = useState<Record<number, string>>({});

  const [leftoverRecipeId, setLeftoverRecipeId] = useState("");
  const [leftoverPortions, setLeftoverPortions] = useState("1");
  const [leftoverCookedAt, setLeftoverCookedAt] = useState(() => {
    const date = new Date();
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    return date.toISOString().slice(0, 16);
  });
  const [leftoverExpiresAt, setLeftoverExpiresAt] = useState("");
  const [leftoverFrozen, setLeftoverFrozen] = useState(false);
  const [leftoverPolicy, setLeftoverPolicy] = useState("");
  const [leftoverNotes, setLeftoverNotes] = useState("");
  const [leftoverAmounts, setLeftoverAmounts] = useState<Record<number, string>>({});

  const [planDays, setPlanDays] = useState("7");

  const householdsQ = useQuery({ queryKey: ["households"], queryFn: householdApi.list });
  const households = householdsQ.data ?? [];
  const effectiveSelectedId = selectedId || households[0]?.id || "";
  const selected = useMemo(
    () => households.find((household) => household.id === effectiveSelectedId),
    [households, effectiveSelectedId],
  );

  useEffect(() => {
    if (oneTimeInvite && oneTimeInvite.householdId !== effectiveSelectedId) {
      setOneTimeInvite(null);
    }
  }, [effectiveSelectedId, oneTimeInvite]);

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
    queryFn: () => householdApi.events(effectiveSelectedId, 100),
    enabled: Boolean(effectiveSelectedId),
  });
  const invitationsQ = useQuery({
    queryKey: ["households", effectiveSelectedId, "invitations"],
    queryFn: () => householdApi.invitations(effectiveSelectedId),
    enabled: Boolean(effectiveSelectedId) && detailQ.data?.role === "owner",
  });
  const policiesQ = useQuery({
    queryKey: ["food-evidence", "storage-policies"],
    queryFn: () => evidenceApi.storagePolicies(),
    staleTime: 30 * 60_000,
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

  const role = detailQ.data?.role ?? selected?.current_role;
  const pageError = householdsQ.error || detailQ.error;
  const policies = (policiesQ.data ?? []).filter(
    (policy) => policy.storage_state === (leftoverFrozen ? "frozen" : "refrigerated"),
  );
  const reservationsByPlan = useMemo(() => {
    const grouped = new Map<number, Reservation[]>();
    for (const reservation of reservationsQ.data ?? []) {
      const current = grouped.get(reservation.plan_id) ?? [];
      current.push(reservation);
      grouped.set(reservation.plan_id, current);
    }
    return [...grouped.entries()].sort(([left], [right]) => right - left);
  }, [reservationsQ.data]);

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

  const acceptInvitation = useMutation({
    mutationFn: () => householdApi.acceptInvitation(acceptanceToken.trim()),
    onSuccess: async () => {
      setAcceptanceToken("");
      await queryClient.invalidateQueries({ queryKey: ["households"] });
      toast({ title: "Invitation accepted" });
    },
    onError: (error) => toast({ title: "Invitation could not be accepted", description: messageOf(error), variant: "destructive" }),
  });

  const invite = useMutation({
    mutationFn: () => householdApi.createInvitation(effectiveSelectedId, {
      email: inviteEmail.trim(),
      role: inviteRole,
      expires_in_hours: 72,
    }),
    onSuccess: async (value: HouseholdInvitation) => {
      setInviteEmail("");
      if (value.acceptance_token) {
        setOneTimeInvite({
          invitationId: value.id,
          householdId: value.household_id,
          email: value.invited_email,
          expiresAt: value.expires_at,
          token: value.acceptance_token,
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["households", effectiveSelectedId, "invitations"] });
      toast({ title: "Invitation created", description: "Copy the one-time token before dismissing it." });
    },
    onError: (error) => toast({ title: "Invitation failed", description: messageOf(error), variant: "destructive" }),
  });

  const revokeInvite = useMutation({
    mutationFn: (invitationId: string) => householdApi.revokeInvitation(effectiveSelectedId, invitationId),
    onSuccess: async (value) => {
      if (oneTimeInvite?.invitationId === value.id) setOneTimeInvite(null);
      await queryClient.invalidateQueries({ queryKey: ["households", effectiveSelectedId, "invitations"] });
      toast({ title: "Invitation revoked" });
    },
    onError: (error) => toast({ title: "Invitation could not be revoked", description: messageOf(error), variant: "destructive" }),
  });

  const addMember = useMutation({
    mutationFn: () => householdApi.addMember(effectiveSelectedId, {
      display_name: memberDraft.displayName.trim(),
      role: memberDraft.role,
      servings_multiplier: positiveNumber(memberDraft.servingsMultiplier, "Serving multiplier"),
      allergies: splitList(memberDraft.allergies),
      dietary_restrictions: splitList(memberDraft.restrictions),
      disliked_ingredients: splitList(memberDraft.dislikes),
      active: true,
    }),
    onSuccess: async () => {
      setMemberDraft(EMPTY_MEMBER);
      await invalidateHousehold();
      toast({ title: "Unlinked household member added" });
    },
    onError: (error) => toast({ title: "Member could not be added", description: messageOf(error), variant: "destructive" }),
  });

  const updateMember = useMutation({
    mutationFn: ({ member, payload }: { member: HouseholdMember; payload: Record<string, unknown> }) =>
      householdApi.updateMember(effectiveSelectedId, member.id, payload),
    onSuccess: invalidateHousehold,
    onError: (error) => toast({ title: "Member update failed", description: messageOf(error), variant: "destructive" }),
  });

  const addPantry = useMutation({
    mutationFn: () => {
      const minimum = nonNegativeNumber(quantityMin, "Minimum quantity");
      const maximum = nonNegativeNumber(quantityMax, "Maximum quantity");
      if (maximum < minimum) throw new Error("Maximum quantity cannot be less than minimum quantity");
      return householdApi.addPantry(effectiveSelectedId, {
        ingredient_name: ingredient.trim(),
        quantity: { quantity_min: minimum, quantity_max: maximum, unit: unit.trim() },
        expires_at: optionalIso(expiresAt),
        source: "manual",
        idempotency_key: idempotencyKey("pantry-create"),
      });
    },
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

  const mutatePantry = useMutation({
    mutationFn: ({ item, action }: { item: PantryItem; action: "consume" | "discard" | "adjust" }) => {
      const amount = action === "adjust"
        ? nonNegativeNumber(pantryAmounts[item.id] ?? "", "Quantity")
        : positiveNumber(pantryAmounts[item.id] ?? "", "Quantity");
      const payload = {
        quantity: { quantity_min: amount, quantity_max: amount, unit: item.unit },
        expected_version: item.version,
        reason: action === "adjust" ? "manual absolute adjustment" : `manual ${action}`,
        idempotency_key: idempotencyKey(`pantry-${action}`),
      };
      if (action === "consume") return householdApi.consumePantry(effectiveSelectedId, item.id, payload);
      if (action === "discard") return householdApi.discardPantry(effectiveSelectedId, item.id, payload);
      return householdApi.adjustPantry(effectiveSelectedId, item.id, payload);
    },
    onSuccess: async (value) => {
      setPantryAmounts((current) => ({ ...current, [value.id]: "" }));
      await invalidateHousehold();
      toast({ title: "Pantry lot updated" });
    },
    onError: (error) => toast({ title: "Pantry mutation failed", description: messageOf(error), variant: "destructive" }),
  });

  const createLeftover = useMutation({
    mutationFn: () => householdApi.addLeftover(effectiveSelectedId, {
      recipe_id: leftoverRecipeId.trim(),
      portions_available: positiveNumber(leftoverPortions, "Portions"),
      cooked_at: optionalIso(leftoverCookedAt),
      expires_at: optionalIso(leftoverExpiresAt),
      frozen: leftoverFrozen,
      storage_policy_key: leftoverPolicy || null,
      notes: leftoverNotes.trim() || null,
      idempotency_key: idempotencyKey("leftover-create"),
    }),
    onSuccess: async () => {
      setLeftoverRecipeId("");
      setLeftoverPortions("1");
      setLeftoverExpiresAt("");
      setLeftoverPolicy("");
      setLeftoverNotes("");
      await invalidateHousehold();
      toast({ title: "Leftover batch recorded" });
    },
    onError: (error) => toast({ title: "Leftover could not be recorded", description: messageOf(error), variant: "destructive" }),
  });

  const consumeLeftover = useMutation({
    mutationFn: (leftover: Leftover) => householdApi.consumeLeftover(effectiveSelectedId, leftover.id, {
      portions: positiveNumber(leftoverAmounts[leftover.id] ?? "", "Portions"),
      expected_version: leftover.version,
      idempotency_key: idempotencyKey("leftover-consume"),
    }),
    onSuccess: async (value) => {
      setLeftoverAmounts((current) => ({ ...current, [value.id]: "" }));
      await invalidateHousehold();
      toast({ title: "Leftover consumption recorded" });
    },
    onError: (error) => toast({ title: "Leftover consumption failed", description: messageOf(error), variant: "destructive" }),
  });

  const generatePlan = useMutation({
    mutationFn: () => {
      const days = Math.trunc(positiveNumber(planDays, "Plan days"));
      if (days > 31) throw new Error("Plan days cannot exceed 31");
      return householdApi.generatePlan(effectiveSelectedId, {
        days,
        reserve_inventory: true,
        reservation_hours: 48,
      });
    },
    onSuccess: async (value) => {
      await invalidateHousehold();
      toast({
        title: "Household plan created",
        description: `${value.target_summary.member_count} active member target(s); pantry coverage ${value.pantry_coverage_score.toFixed(3)}.`,
      });
    },
    onError: (error) => toast({ title: "Planning failed", description: messageOf(error), variant: "destructive" }),
  });

  const mutateReservations = useMutation({
    mutationFn: ({ planId, action }: { planId: number; action: "commit" | "release" }) =>
      action === "commit"
        ? householdApi.commitReservations(effectiveSelectedId, planId, { reason: "explicit household confirmation" })
        : householdApi.releaseReservations(effectiveSelectedId, planId, { reason: "explicit household cancellation" }),
    onSuccess: async (_, variables) => {
      await invalidateHousehold();
      toast({ title: variables.action === "commit" ? "Reserved stock consumed" : "Reservations released" });
    },
    onError: (error) => toast({ title: "Reservation mutation failed", description: messageOf(error), variant: "destructive" }),
  });

  const copyOneTimeToken = async () => {
    if (!oneTimeInvite) return;
    try {
      await navigator.clipboard.writeText(oneTimeInvite.token);
      toast({ title: "Invitation token copied" });
    } catch {
      toast({ title: "Copy failed", description: "Select and copy the displayed token manually.", variant: "destructive" });
    }
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Household and pantry</h1>
          <p className="text-sm text-muted-foreground">
            Role-aware members, transactional lots, reviewed leftovers, reservations, and conservative shopping reconciliation.
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
              <CardDescription>Create, select, or join an accessible household.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                {households.length === 0 && !householdsQ.isLoading && <p className="text-sm text-muted-foreground">No household exists yet.</p>}
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
              <form className="space-y-2 border-t pt-4" onSubmit={(event) => { event.preventDefault(); if (householdName.trim()) createHousehold.mutate(); }}>
                <Label htmlFor="household-name">New household</Label>
                <Input id="household-name" value={householdName} onChange={(event) => setHouseholdName(event.target.value)} maxLength={120} required />
                <Button type="submit" disabled={createHousehold.isPending}>Create household</Button>
              </form>
              <form className="space-y-2 border-t pt-4" onSubmit={(event) => { event.preventDefault(); if (acceptanceToken.trim()) acceptInvitation.mutate(); }}>
                <Label htmlFor="invitation-token">Accept invitation token</Label>
                <Input id="invitation-token" value={acceptanceToken} onChange={(event) => setAcceptanceToken(event.target.value)} autoComplete="off" required />
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

        {oneTimeInvite && oneTimeInvite.householdId === effectiveSelectedId && (
          <Alert>
            <Clipboard className="h-4 w-4" />
            <AlertTitle>One-time invitation token for {oneTimeInvite.email}</AlertTitle>
            <AlertDescription className="space-y-3">
              <p>This token is not stored in plaintext and cannot be retrieved after dismissal. It expires {formatDate(oneTimeInvite.expiresAt)}.</p>
              <code className="block overflow-x-auto rounded bg-muted p-3 text-xs" aria-label="One-time invitation token">{oneTimeInvite.token}</code>
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" onClick={() => void copyOneTimeToken()}><Clipboard className="mr-2 h-4 w-4" />Copy token</Button>
                <Button type="button" size="sm" variant="outline" onClick={() => setOneTimeInvite(null)}>I saved it</Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

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
                  <CardHeader><CardTitle className="text-base">Record a pantry lot</CardTitle><CardDescription>Quantities remain intervals and incompatible unit dimensions are rejected.</CardDescription></CardHeader>
                  <CardContent>
                    <form className="grid gap-3 md:grid-cols-6" onSubmit={(event) => { event.preventDefault(); addPantry.mutate(); }}>
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
                      {canEdit(role) && (
                        <div className="space-y-2 border-t pt-3">
                          <Label htmlFor={`pantry-amount-${item.id}`}>Mutation amount ({item.unit})</Label>
                          <Input id={`pantry-amount-${item.id}`} type="number" min="0" step="any" value={pantryAmounts[item.id] ?? ""} onChange={(event) => setPantryAmounts((current) => ({ ...current, [item.id]: event.target.value }))} />
                          <div className="flex flex-wrap gap-2">
                            <Button type="button" size="sm" variant="outline" onClick={() => mutatePantry.mutate({ item, action: "consume" })}>Consume</Button>
                            <Button type="button" size="sm" variant="outline" onClick={() => mutatePantry.mutate({ item, action: "discard" })}>Discard</Button>
                            <Button type="button" size="sm" variant="outline" onClick={() => mutatePantry.mutate({ item, action: "adjust" })}>Set absolute</Button>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
                {!pantryQ.isLoading && (pantryQ.data?.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No active pantry lots.</p>}
              </div>
            </TabsContent>

            <TabsContent value="members" className="space-y-4">
              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Users className="h-4 w-4" />Members</CardTitle><CardDescription>Owner/editor/viewer roles govern writes. Hard restrictions are unioned across active members.</CardDescription></CardHeader>
                <CardContent className="space-y-3">
                  {(detailQ.data?.members ?? []).map((member) => (
                    <div key={member.id} className="rounded-md border p-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div><p className="font-medium">{member.display_name}</p><p className="text-xs text-muted-foreground">{member.role} · serving multiplier {member.servings_multiplier} · {member.active ? "active" : "inactive"}</p></div>
                        <div className="flex flex-wrap gap-1">{member.allergies.map((value) => <Badge key={value} variant="destructive">{value}</Badge>)}{member.dietary_restrictions.map((value) => <Badge key={value} variant="secondary">{value}</Badge>)}</div>
                      </div>
                      {role === "owner" && member.role !== "owner" && (
                        <div className="mt-3 flex flex-wrap gap-2 border-t pt-3">
                          <Button type="button" size="sm" variant="outline" onClick={() => updateMember.mutate({ member, payload: { active: !member.active } })}>{member.active ? "Deactivate" : "Activate"}</Button>
                          <Button type="button" size="sm" variant="outline" onClick={() => updateMember.mutate({ member, payload: { role: member.role === "editor" ? "viewer" : "editor" } })}>{member.role === "editor" ? "Make viewer" : "Make editor"}</Button>
                        </div>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>

              {role === "owner" && (
                <div className="grid gap-4 lg:grid-cols-2">
                  <Card>
                    <CardHeader><CardTitle className="text-base">Add an unlinked member</CardTitle><CardDescription>Use for a planning-only person without account access.</CardDescription></CardHeader>
                    <CardContent>
                      <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); addMember.mutate(); }}>
                        <div className="space-y-1"><Label htmlFor="member-name">Display name</Label><Input id="member-name" value={memberDraft.displayName} onChange={(event) => setMemberDraft((current) => ({ ...current, displayName: event.target.value }))} required /></div>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="space-y-1"><Label htmlFor="member-role">Role</Label><select id="member-role" value={memberDraft.role} onChange={(event) => setMemberDraft((current) => ({ ...current, role: event.target.value as Exclude<HouseholdRole, "owner"> }))} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"><option value="viewer">Viewer</option><option value="editor">Editor</option></select></div>
                          <div className="space-y-1"><Label htmlFor="member-servings">Serving multiplier</Label><Input id="member-servings" type="number" min="0.01" max="20" step="0.01" value={memberDraft.servingsMultiplier} onChange={(event) => setMemberDraft((current) => ({ ...current, servingsMultiplier: event.target.value }))} required /></div>
                        </div>
                        <div className="space-y-1"><Label htmlFor="member-allergies">Allergies</Label><Textarea id="member-allergies" value={memberDraft.allergies} onChange={(event) => setMemberDraft((current) => ({ ...current, allergies: event.target.value }))} placeholder="Comma or newline separated" /></div>
                        <div className="space-y-1"><Label htmlFor="member-restrictions">Restrictions</Label><Textarea id="member-restrictions" value={memberDraft.restrictions} onChange={(event) => setMemberDraft((current) => ({ ...current, restrictions: event.target.value }))} /></div>
                        <div className="space-y-1"><Label htmlFor="member-dislikes">Disliked ingredients</Label><Textarea id="member-dislikes" value={memberDraft.dislikes} onChange={(event) => setMemberDraft((current) => ({ ...current, dislikes: event.target.value }))} /></div>
                        <Button type="submit" disabled={addMember.isPending}>Add planning member</Button>
                      </form>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader><CardTitle className="text-base">Invite an account</CardTitle><CardDescription>Email-bound, expiring, single-use token; ownership cannot be assigned.</CardDescription></CardHeader>
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
                          <Button className="mt-2" type="button" size="sm" variant="outline" onClick={() => revokeInvite.mutate(invitation.id)}>Revoke</Button>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </div>
              )}
            </TabsContent>

            <TabsContent value="planning" className="space-y-4">
              <Card>
                <CardHeader><CardTitle className="text-base">Household planning and inventory reservation</CardTitle><CardDescription>Inventory is reserved first and consumed only through an explicit commit.</CardDescription></CardHeader>
                <CardContent className="flex flex-wrap items-end gap-3">
                  <div className="space-y-1"><Label htmlFor="plan-days">Days</Label><Input id="plan-days" className="w-28" type="number" min="1" max="31" step="1" value={planDays} onChange={(event) => setPlanDays(event.target.value)} required /></div>
                  <Button type="button" onClick={() => generatePlan.mutate()} disabled={!canEdit(role) || generatePlan.isPending}>Generate and reserve</Button>
                  <Button type="button" variant="outline" onClick={() => shoppingQ.refetch()}>Load reconciled shopping</Button>
                  <Button type="button" variant="outline" onClick={() => batchQ.refetch()}>Load batch preparation</Button>
                </CardContent>
              </Card>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader><CardTitle className="text-base">Active reservations</CardTitle><CardDescription>Commit consumes stock; release makes it available to other plans.</CardDescription></CardHeader>
                  <CardContent className="space-y-3">
                    {reservationsByPlan.map(([planId, reservations]) => (
                      <div key={planId} className="rounded border p-3 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">Plan {planId}</span><Badge variant="outline">{reservations.length} lot allocation(s)</Badge></div>
                        <ul className="mt-2 space-y-1">{reservations.map((reservation) => <li key={reservation.id}>{reservation.canonical_name}: {formatRange(reservation.quantity_min, reservation.quantity_max, reservation.unit)} · expires {formatDate(reservation.expires_at)}</li>)}</ul>
                        {canEdit(role) && <div className="mt-3 flex flex-wrap gap-2"><Button type="button" size="sm" onClick={() => mutateReservations.mutate({ planId, action: "commit" })}>Commit stock</Button><Button type="button" size="sm" variant="outline" onClick={() => mutateReservations.mutate({ planId, action: "release" })}>Release</Button></div>}
                      </div>
                    ))}
                    {!reservationsQ.isLoading && reservationsByPlan.length === 0 && <p className="text-sm text-muted-foreground">No active reservations.</p>}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle className="text-base">Shopping reconciliation</CardTitle></CardHeader>
                  <CardContent className="space-y-2">
                    {shoppingQ.error && <p className="text-sm text-destructive">{messageOf(shoppingQ.error)}</p>}
                    {(shoppingQ.data ?? []).map((item) => <div key={`${item.canonical_name}-${item.unit}`} className="rounded border p-3 text-sm"><div className="flex justify-between gap-2"><span className="font-medium">{item.display_name}</span><Badge variant="outline">{item.coverage_status}</Badge></div><p>Buy {formatRange(item.buy_min, item.buy_max, item.unit)}</p><p className="text-xs text-muted-foreground">Required {formatRange(item.required_min, item.required_max, item.unit)}; pantry {formatRange(item.pantry_min, item.pantry_max, item.unit)}</p>{item.notes.length > 0 && <p className="mt-1 text-xs text-muted-foreground">{item.notes.join(" · ")}</p>}</div>)}
                  </CardContent>
                </Card>
              </div>

              {(batchQ.data?.length ?? 0) > 0 && <Card><CardHeader><CardTitle className="text-base">Batch preparation</CardTitle></CardHeader><CardContent className="space-y-2">{batchQ.data?.map((task) => <div key={task.recipe_id} className="rounded border p-3 text-sm"><p className="font-medium">{task.recipe_name}</p><p>{task.total_portions} portions across {task.occurrences} occurrence(s); prepare day {task.scheduled_day}</p><p className="text-xs text-muted-foreground">Storage status: {task.storage_guidance_status}{task.applicable_storage_policies?.length ? ` · policies: ${task.applicable_storage_policies.join(", ")}` : ""}</p></div>)}</CardContent></Card>}
            </TabsContent>

            <TabsContent value="leftovers" className="space-y-4">
              {canEdit(role) && (
                <Card>
                  <CardHeader><CardTitle className="text-base">Record a leftover batch</CardTitle><CardDescription>Recipe IDs must exist. Expiry is derived only from a matching reviewed safety policy; frozen quality guidance is not treated as a safety expiry.</CardDescription></CardHeader>
                  <CardContent>
                    <form className="grid gap-3 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); createLeftover.mutate(); }}>
                      <div className="space-y-1"><Label htmlFor="leftover-recipe">Recipe ID</Label><Input id="leftover-recipe" value={leftoverRecipeId} onChange={(event) => setLeftoverRecipeId(event.target.value)} required /></div>
                      <div className="space-y-1"><Label htmlFor="leftover-portions">Portions</Label><Input id="leftover-portions" type="number" min="0.01" max="1000" step="0.01" value={leftoverPortions} onChange={(event) => setLeftoverPortions(event.target.value)} required /></div>
                      <div className="space-y-1"><Label htmlFor="leftover-cooked">Cooked at</Label><Input id="leftover-cooked" type="datetime-local" value={leftoverCookedAt} onChange={(event) => setLeftoverCookedAt(event.target.value)} required /></div>
                      <div className="space-y-1"><Label htmlFor="leftover-expiry">Explicit expiry (optional)</Label><Input id="leftover-expiry" type="datetime-local" value={leftoverExpiresAt} onChange={(event) => setLeftoverExpiresAt(event.target.value)} /></div>
                      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={leftoverFrozen} onChange={(event) => { setLeftoverFrozen(event.target.checked); setLeftoverPolicy(""); }} />Frozen</label>
                      <div className="space-y-1"><Label htmlFor="leftover-policy">Reviewed storage policy</Label><select id="leftover-policy" value={leftoverPolicy} onChange={(event) => setLeftoverPolicy(event.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"><option value="">No policy</option>{policies.map((policy: StoragePolicy) => <option key={policy.policy_key} value={policy.policy_key}>{policy.food_category} · {policy.policy_key}</option>)}</select></div>
                      <div className="space-y-1 md:col-span-2"><Label htmlFor="leftover-notes">Notes</Label><Textarea id="leftover-notes" value={leftoverNotes} onChange={(event) => setLeftoverNotes(event.target.value)} maxLength={1000} /></div>
                      <Button className="md:w-fit" type="submit" disabled={createLeftover.isPending}>Record leftovers</Button>
                    </form>
                  </CardContent>
                </Card>
              )}

              <div className="grid gap-3 md:grid-cols-2">
                {(leftoversQ.data ?? []).map((leftover) => (
                  <Card key={leftover.id}>
                    <CardContent className="space-y-3 p-4">
                      <div className="flex justify-between gap-2"><span className="font-medium">Recipe {leftover.recipe_id}</span><Badge variant="outline">{leftover.frozen ? "frozen" : "refrigerated"}</Badge></div>
                      <p>{leftover.portions_available} portions · v{leftover.version}</p>
                      <p className="text-xs text-muted-foreground">Cooked {formatDate(leftover.cooked_at)} · expires {formatDate(leftover.expires_at)} · policy {leftover.storage_policy_key ?? "not assigned"}</p>
                      {leftover.notes && <p className="text-xs text-muted-foreground">{leftover.notes}</p>}
                      {canEdit(role) && <div className="space-y-2 border-t pt-3"><Label htmlFor={`leftover-amount-${leftover.id}`}>Portions consumed</Label><Input id={`leftover-amount-${leftover.id}`} type="number" min="0.01" step="0.01" value={leftoverAmounts[leftover.id] ?? ""} onChange={(event) => setLeftoverAmounts((current) => ({ ...current, [leftover.id]: event.target.value }))} /><Button type="button" size="sm" variant="outline" onClick={() => consumeLeftover.mutate(leftover)}>Consume portions</Button></div>}
                    </CardContent>
                  </Card>
                ))}
                {!leftoversQ.isLoading && (leftoversQ.data?.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No active leftovers.</p>}
              </div>
            </TabsContent>

            <TabsContent value="events">
              <Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarClock className="h-4 w-4" />Inventory audit events</CardTitle></CardHeader><CardContent className="space-y-2">{(eventsQ.data ?? []).map((event) => <div key={event.id} className="grid gap-1 rounded border p-3 text-sm sm:grid-cols-[180px_1fr_auto]"><span className="capitalize">{event.event_type.replaceAll("_", " ")}</span><span>{formatRange(event.quantity_min, event.quantity_max, event.unit)}{event.reason ? ` · ${event.reason}` : ""}</span><span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span></div>)}</CardContent></Card>
            </TabsContent>
          </Tabs>
        )}

        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Safety boundary</AlertTitle>
          <AlertDescription>Household targets and storage policies are planning aids, not medical, allergy, medication-interaction, or food-safety guarantees.</AlertDescription>
        </Alert>
      </div>
    </AppLayout>
  );
}
