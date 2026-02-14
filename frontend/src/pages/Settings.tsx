import { useState, useEffect } from "react";
import AppLayout from "@/components/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/contexts/AuthContext";
import { useUserProfile, useUpdateProfile, useAddHealthCondition, useAddMedication } from "@/hooks/useApi";
import { useToast } from "@/hooks/use-toast";
import { Plus, X, AlertTriangle, Activity } from "lucide-react";

const tabs = ["Profile", "Health", "Dietary", "App"] as const;

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<typeof tabs[number]>("Profile");
  const { user } = useAuth();
  const userId = user?.id ?? "usr_1";
  const { toast } = useToast();

  // API hooks
  const profileQ = useUserProfile(userId);
  const updateMutation = useUpdateProfile();
  const addConditionMutation = useAddHealthCondition();
  const addMedMutation = useAddMedication();

  // Local form state
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [age, setAge] = useState(30);
  const [weight, setWeight] = useState(70);
  const [height, setHeight] = useState(170);
  const [gender, setGender] = useState("male");
  const [activityLevel, setActivityLevel] = useState(1.4);
  const [goal, setGoal] = useState("maintenance");
  const [calorieTarget, setCalorieTarget] = useState(2100);
  const [proteinTarget, setProteinTarget] = useState(130);
  const [allergies, setAllergies] = useState("");
  const [restrictions, setRestrictions] = useState("");
  const [cuisines, setCuisines] = useState("");
  const [tastePrefs, setTastePrefs] = useState("");
  const [foodsToAvoid, setFoodsToAvoid] = useState("");
  const [conditions, setConditions] = useState<string[]>([]);
  const [medications, setMedications] = useState<string[]>([]);
  const [newCondition, setNewCondition] = useState("");
  const [newMedication, setNewMedication] = useState("");

  // Populate form from API data
  useEffect(() => {
    if (profileQ.data) {
      const p = profileQ.data;
      if (p.name) setName(p.name);
      setAge(p.age ?? 30);
      setWeight(p.weight_kg ?? 70);
      setHeight(p.height_cm ?? 170);
      setGender(p.gender ?? "male");
      setActivityLevel(p.activity_level ?? 1.4);
      setGoal(p.goal ?? "maintenance");
      setRestrictions(p.dietary_restrictions?.join(", ") ?? "");
      setConditions(p.health_conditions ?? []);
      setMedications(p.medications ?? []);
    }
  }, [profileQ.data]);

  // BMR/TDEE calculation (Mifflin-St Jeor)
  const bmr = gender === "female"
    ? 10 * weight + 6.25 * height - 5 * age - 161
    : 10 * weight + 6.25 * height - 5 * age + 5;
  const tdee = Math.round(bmr * activityLevel);

  // Save profile
  const handleSaveProfile = async () => {
    try {
      await updateMutation.mutateAsync({
        userId,
        profile: {
          name,
          age,
          weight_kg: weight,
          height_cm: height,
          gender: gender as "male" | "female" | "other",
          activity_level: activityLevel,
          goal: goal as "weight_loss" | "maintenance" | "muscle_gain",
          dietary_restrictions: restrictions.split(",").map((s) => s.trim()).filter(Boolean),
          health_conditions: conditions,
          medications,
        },
      });
      toast({ title: "Profile saved", description: "Your profile has been updated" });
    } catch {
      toast({ title: "Save failed", description: "Backend unavailable", variant: "destructive" });
    }
  };

  // Add health condition
  const handleAddCondition = async () => {
    if (!newCondition.trim()) return;
    try {
      const result = await addConditionMutation.mutateAsync({ userId, condition: newCondition });
      setConditions((prev) => [...new Set([...prev, newCondition])]);
      toast({
        title: "Condition added",
        description: result.dataset_verified
          ? `${newCondition} — verified in DietRx database`
          : `${newCondition} — added (not in database yet)`,
      });
      setNewCondition("");
    } catch {
      setConditions((prev) => [...new Set([...prev, newCondition])]);
      setNewCondition("");
    }
  };

  // Add medication
  const handleAddMedication = async () => {
    if (!newMedication.trim()) return;
    try {
      await addMedMutation.mutateAsync({ userId, medication: newMedication });
      setMedications((prev) => [...new Set([...prev, newMedication])]);
      toast({ title: "Medication added", description: `${newMedication} — drug-food interactions will be checked` });
      setNewMedication("");
    } catch {
      setMedications((prev) => [...new Set([...prev, newMedication])]);
      setNewMedication("");
    }
  };

  const removeCondition = (c: string) => setConditions((prev) => prev.filter((x) => x !== c));
  const removeMedication = (m: string) => setMedications((prev) => prev.filter((x) => x !== m));

  return (
    <AppLayout>
      <div className="space-y-6 max-w-3xl mx-auto">
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-muted-foreground text-sm">Manage your profile and preferences</p>
        </div>

        <div className="flex gap-2 overflow-x-auto pb-2">
          {tabs.map((t) => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${activeTab === t ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground hover:bg-accent"
                }`}
            >{t}</button>
          ))}
        </div>

        {activeTab === "Profile" && (
          <Card>
            <CardHeader><CardTitle className="text-base">Profile Information</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2"><Label>Name</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
              <div className="space-y-2"><Label>Email</Label><Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" /></div>
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2"><Label>Age</Label><Input type="number" value={age} onChange={(e) => setAge(+e.target.value)} /></div>
                <div className="space-y-2"><Label>Weight (kg)</Label><Input type="number" value={weight} onChange={(e) => setWeight(+e.target.value)} /></div>
                <div className="space-y-2"><Label>Height (cm)</Label><Input type="number" value={height} onChange={(e) => setHeight(+e.target.value)} /></div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Gender</Label>
                  <select value={gender} onChange={(e) => setGender(e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>Goal</Label>
                  <select value={goal} onChange={(e) => setGoal(e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="weight_loss">Weight Loss</option>
                    <option value="maintenance">Maintenance</option>
                    <option value="muscle_gain">Muscle Gain</option>
                  </select>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Activity Level</Label>
                <select value={activityLevel} onChange={(e) => setActivityLevel(+e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value={1.2}>Sedentary (1.2)</option>
                  <option value={1.375}>Light (1.375)</option>
                  <option value={1.4}>Moderate-Light (1.4)</option>
                  <option value={1.55}>Moderate (1.55)</option>
                  <option value={1.725}>Heavy (1.725)</option>
                  <option value={1.9}>Very Heavy (1.9)</option>
                </select>
              </div>

              {/* BMR / TDEE Display */}
              <Card className="border-primary/20">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium">Calculated Targets</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-center">
                    <div>
                      <p className="text-xl font-bold">{Math.round(bmr)}</p>
                      <p className="text-xs text-muted-foreground">BMR (kcal/day)</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-primary">{tdee}</p>
                      <p className="text-xs text-muted-foreground">TDEE (kcal/day)</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Button onClick={handleSaveProfile} disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "Saving…" : "Save Changes"}
              </Button>
            </CardContent>
          </Card>
        )}

        {activeTab === "Health" && (
          <div className="space-y-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Health Preferences</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2"><Label>Daily Calorie Target</Label><Input type="number" value={calorieTarget} onChange={(e) => setCalorieTarget(+e.target.value)} /></div>
                <div className="space-y-2"><Label>Protein Target (g)</Label><Input type="number" value={proteinTarget} onChange={(e) => setProteinTarget(+e.target.value)} /></div>
                <div className="space-y-2"><Label>Allergies</Label><Input placeholder="e.g. Peanuts, Shellfish" value={allergies} onChange={(e) => setAllergies(e.target.value)} /></div>
                <div className="space-y-2"><Label>Dietary Restrictions</Label><Input placeholder="e.g. Gluten-free, Vegetarian" value={restrictions} onChange={(e) => setRestrictions(e.target.value)} /></div>
                <Button onClick={handleSaveProfile} disabled={updateMutation.isPending}>Save Changes</Button>
              </CardContent>
            </Card>

            {/* Health Conditions */}
            <Card>
              <CardHeader><CardTitle className="text-base">Health Conditions</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">Add health conditions for personalized meal planning. Validated against DietRx database.</p>
                <div className="flex gap-2">
                  <Input placeholder="e.g. Diabetes, Hypertension" value={newCondition} onChange={(e) => setNewCondition(e.target.value)} />
                  <Button size="sm" onClick={handleAddCondition} disabled={addConditionMutation.isPending}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {conditions.map((c) => (
                    <span key={c} className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-destructive/10 text-destructive text-xs font-medium">
                      <AlertTriangle className="h-3 w-3" />
                      {c}
                      <button onClick={() => removeCondition(c)}><X className="h-3 w-3" /></button>
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Medications */}
            <Card>
              <CardHeader><CardTitle className="text-base">Medications</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">Add medications to check for drug–food interactions in your meal plans.</p>
                <div className="flex gap-2">
                  <Input placeholder="e.g. Metformin, Warfarin" value={newMedication} onChange={(e) => setNewMedication(e.target.value)} />
                  <Button size="sm" onClick={handleAddMedication} disabled={addMedMutation.isPending}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {medications.map((m) => (
                    <span key={m} className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-taste/10 text-taste text-xs font-medium">
                      {m}
                      <button onClick={() => removeMedication(m)}><X className="h-3 w-3" /></button>
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {activeTab === "Dietary" && (
          <Card>
            <CardHeader><CardTitle className="text-base">Dietary Preferences</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2"><Label>Favorite Cuisines</Label><Input placeholder="e.g. Mediterranean, Japanese, Mexican" value={cuisines} onChange={(e) => setCuisines(e.target.value)} /></div>
              <div className="space-y-2"><Label>Taste Preferences</Label><Input placeholder="e.g. Spicy, Savory, Umami" value={tastePrefs} onChange={(e) => setTastePrefs(e.target.value)} /></div>
              <div className="space-y-2"><Label>Foods to Avoid</Label><Input placeholder="e.g. Cilantro, Liver" value={foodsToAvoid} onChange={(e) => setFoodsToAvoid(e.target.value)} /></div>
              <Button onClick={handleSaveProfile} disabled={updateMutation.isPending}>Save Changes</Button>
            </CardContent>
          </Card>
        )}

        {activeTab === "App" && (
          <Card>
            <CardHeader><CardTitle className="text-base">App Preferences</CardTitle></CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div><Label>Dark Mode</Label><p className="text-xs text-muted-foreground">Use dark theme</p></div>
                <Switch defaultChecked />
              </div>
              <div className="flex items-center justify-between">
                <div><Label>Notifications</Label><p className="text-xs text-muted-foreground">Meal reminders & insights</p></div>
                <Switch defaultChecked />
              </div>
              <div className="flex items-center justify-between">
                <div><Label>Metric Units</Label><p className="text-xs text-muted-foreground">Use kg, g, ml instead of lbs, oz</p></div>
                <Switch />
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
