import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/AuthContext";
import { useUpdateProfile, useUserProfile } from "@/hooks/useApi";
import { useToast } from "@/hooks/use-toast";
import type { UserProfile } from "@/lib/api";
import { AlertCircle, CheckCircle2 } from "lucide-react";

function listFromText(value: string): string[] {
  return value.split(/[,\n]/).map((entry) => entry.trim()).filter(Boolean);
}

function textFromList(value?: string[]): string {
  return (value ?? []).join(", ");
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The request could not be completed";
}

export default function SettingsPage() {
  const { user, refreshSession } = useAuth();
  const userId = user?.id ?? "";
  const { toast } = useToast();
  const profileQ = useUserProfile(user?.profileComplete ? userId : "");
  const updateProfile = useUpdateProfile();

  const [name, setName] = useState(user?.name ?? "");
  const [age, setAge] = useState("");
  const [weight, setWeight] = useState("");
  const [height, setHeight] = useState("");
  const [gender, setGender] = useState<UserProfile["gender"] | "">("");
  const [activity, setActivity] = useState("");
  const [goal, setGoal] = useState<UserProfile["goal"] | "">("");
  const [liked, setLiked] = useState("");
  const [disliked, setDisliked] = useState("");
  const [allergies, setAllergies] = useState("");
  const [restrictions, setRestrictions] = useState("");
  const [conditions, setConditions] = useState("");
  const [medications, setMedications] = useState("");

  useEffect(() => {
    const profile = profileQ.data;
    if (!profile) return;
    setName(profile.name ?? user?.name ?? "");
    setAge(String(profile.age));
    setWeight(String(profile.weight_kg));
    setHeight(String(profile.height_cm));
    setGender(profile.gender);
    setActivity(String(profile.activity_level));
    setGoal(profile.goal);
    setLiked(textFromList(profile.liked_ingredients));
    setDisliked(textFromList(profile.disliked_ingredients));
    setAllergies(textFromList(profile.allergies));
    setRestrictions(textFromList(profile.dietary_restrictions));
    setConditions(textFromList(profile.health_conditions));
    setMedications(textFromList(profile.medications));
  }, [profileQ.data, user?.name]);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!gender || !goal) {
      toast({ title: "Required fields missing", description: "Select sex/gender and planning goal.", variant: "destructive" });
      return;
    }
    const profile: UserProfile = {
      name: name.trim() || undefined,
      age: Number(age),
      weight_kg: Number(weight),
      height_cm: Number(height),
      gender,
      activity_level: Number(activity),
      goal,
      liked_ingredients: listFromText(liked),
      disliked_ingredients: listFromText(disliked),
      allergies: listFromText(allergies),
      dietary_restrictions: listFromText(restrictions),
      health_conditions: listFromText(conditions),
      medications: listFromText(medications),
    };
    try {
      await updateProfile.mutateAsync({ userId, profile });
      await refreshSession();
      toast({ title: "Profile saved", description: "Backend-derived planning targets are now available." });
    } catch (error) {
      toast({ title: "Profile validation failed", description: messageOf(error), variant: "destructive" });
    }
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-4xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Profile and planning inputs</h1>
          <p className="text-sm text-muted-foreground">All physiological and preference inputs must be supplied explicitly. No demographic defaults are inserted.</p>
        </div>

        {!user?.profileComplete && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Profile completion required</AlertTitle>
            <AlertDescription>Missing fields: {user?.missingProfileFields.length ? user.missingProfileFields.join(", ") : "required planning inputs"}.</AlertDescription>
          </Alert>
        )}

        <form onSubmit={save} className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base">Identity and physiological inputs</CardTitle><CardDescription>These values are used for planning-target calculations. Review them before saving.</CardDescription></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2"><Label htmlFor="profile-name">Name</Label><Input id="profile-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={120} /></div>
              <div className="space-y-2"><Label htmlFor="profile-email">Email</Label><Input id="profile-email" value={user?.email ?? ""} readOnly aria-readonly="true" /></div>
              <div className="space-y-2"><Label htmlFor="age">Age</Label><Input id="age" type="number" min="18" max="120" value={age} onChange={(event) => setAge(event.target.value)} required /></div>
              <div className="space-y-2"><Label htmlFor="weight">Weight (kg)</Label><Input id="weight" type="number" min="0.1" max="500" step="0.1" value={weight} onChange={(event) => setWeight(event.target.value)} required /></div>
              <div className="space-y-2"><Label htmlFor="height">Height (cm)</Label><Input id="height" type="number" min="0.1" max="300" step="0.1" value={height} onChange={(event) => setHeight(event.target.value)} required /></div>
              <div className="space-y-2"><Label htmlFor="gender">Sex/gender input</Label><select id="gender" value={gender} onChange={(event) => setGender(event.target.value as UserProfile["gender"])} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" required><option value="">Select</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other / calculation not sex-specific</option></select></div>
              <div className="space-y-2"><Label htmlFor="activity">Activity factor</Label><Input id="activity" type="number" min="1" max="3" step="0.025" value={activity} onChange={(event) => setActivity(event.target.value)} required /><p className="text-xs text-muted-foreground">Enter the factor you intend the backend to use; do not leave an assumed default.</p></div>
              <div className="space-y-2"><Label htmlFor="goal">Planning goal</Label><select id="goal" value={goal} onChange={(event) => setGoal(event.target.value as UserProfile["goal"])} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" required><option value="">Select</option><option value="weight_loss">Weight loss</option><option value="maintenance">Maintenance</option><option value="muscle_gain">Muscle gain</option></select></div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Dietary constraints and preferences</CardTitle><CardDescription>Allergies are stored separately from dislikes so hard safety filters do not depend on string prefixes.</CardDescription></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2"><Label htmlFor="allergies">Allergies</Label><Textarea id="allergies" value={allergies} onChange={(event) => setAllergies(event.target.value)} placeholder="Comma or newline separated" /></div>
              <div className="space-y-2"><Label htmlFor="restrictions">Dietary restrictions</Label><Textarea id="restrictions" value={restrictions} onChange={(event) => setRestrictions(event.target.value)} placeholder="Comma or newline separated" /></div>
              <div className="space-y-2"><Label htmlFor="liked">Liked ingredients</Label><Textarea id="liked" value={liked} onChange={(event) => setLiked(event.target.value)} placeholder="Comma or newline separated" /></div>
              <div className="space-y-2"><Label htmlFor="disliked">Disliked ingredients</Label><Textarea id="disliked" value={disliked} onChange={(event) => setDisliked(event.target.value)} placeholder="Comma or newline separated" /></div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Health-context disclosures</CardTitle><CardDescription>Stored for transparency only. Current planning is not clinically validated for conditions, medications, contraindications, or interactions.</CardDescription></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2"><Label htmlFor="conditions">Health conditions</Label><Textarea id="conditions" value={conditions} onChange={(event) => setConditions(event.target.value)} placeholder="Comma or newline separated" /></div>
              <div className="space-y-2"><Label htmlFor="medications">Medications</Label><Textarea id="medications" value={medications} onChange={(event) => setMedications(event.target.value)} placeholder="Comma or newline separated" /></div>
            </CardContent>
          </Card>

          {profileQ.data && (
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CheckCircle2 className="h-4 w-4" />Persisted planning targets</CardTitle><CardDescription>Targets are computed and persisted by the backend when you save the profile.</CardDescription></CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                <Badge variant="outline">{profileQ.data.target_calories ?? "—"} kcal</Badge>
                <Badge variant="outline">{profileQ.data.target_protein_g ?? "—"} g protein</Badge>
                <Badge variant="outline">{profileQ.data.target_carbs_g ?? "—"} g carbohydrate</Badge>
                <Badge variant="outline">{profileQ.data.target_fat_g ?? "—"} g fat</Badge>
              </CardContent>
            </Card>
          )}

          <Button type="submit" disabled={updateProfile.isPending}>{updateProfile.isPending ? "Validating and saving…" : "Save explicit profile"}</Button>
        </form>
      </div>
    </AppLayout>
  );
}
