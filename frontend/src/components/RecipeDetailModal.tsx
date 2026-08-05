import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useRecipeDetails } from "@/hooks/useApi";
import {
  ChefHat,
  Flame,
  ListChecks,
  Loader2,
  Printer,
  Scale,
  Users,
  Utensils,
} from "lucide-react";

interface RecipeDetailModalProps {
  recipeId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function percent(value: number | undefined, reference: number): number {
  if (!value || value <= 0) return 0;
  return Math.min(100, (value / reference) * 100);
}

export function RecipeDetailModal({
  recipeId,
  open,
  onOpenChange,
}: RecipeDetailModalProps) {
  const { data: recipe, isLoading, error } = useRecipeDetails(recipeId);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);

  useEffect(() => {
    setCompletedSteps([]);
  }, [recipeId]);

  if (!recipeId) return null;

  const toggleStep = (index: number) => {
    setCompletedSteps((previous) =>
      previous.includes(index)
        ? previous.filter((value) => value !== index)
        : [...previous, index],
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[95vh] max-w-4xl gap-0 overflow-hidden border-none p-0 shadow-2xl sm:rounded-xl">
        {isLoading ? (
          <div className="flex h-96 flex-col items-center justify-center gap-4 bg-background">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-muted-foreground">Loading reviewed recipe details…</p>
          </div>
        ) : error || !recipe ? (
          <div className="flex flex-col items-center gap-4 p-12 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
              <Utensils className="h-6 w-6 text-destructive" />
            </div>
            <h3 className="text-lg font-semibold">Recipe not found</h3>
            <p className="text-muted-foreground">
              The reviewed details for this recipe could not be retrieved.
            </p>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        ) : (
          <div className="flex max-h-[95vh] flex-col">
            <div className="group relative h-64 w-full shrink-0 overflow-hidden sm:h-80">
              {recipe.image_url ? (
                <img
                  src={recipe.image_url}
                  alt={recipe.name}
                  className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-slate-900 to-slate-800">
                  <Utensils className="h-20 w-20 text-white/10" />
                </div>
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-background via-background/60 to-transparent" />
              <div className="absolute right-4 top-4">
                <Button
                  size="icon"
                  variant="secondary"
                  className="h-8 w-8 rounded-full bg-background/50 backdrop-blur-md hover:bg-background/80"
                  onClick={() => window.print()}
                  aria-label="Print recipe"
                >
                  <Printer className="h-4 w-4" />
                </Button>
              </div>
              <div className="absolute bottom-6 left-6 right-6">
                <div className="mb-3 flex flex-wrap gap-2">
                  {recipe.cuisine ? <Badge>{recipe.cuisine}</Badge> : null}
                  {recipe.tags?.slice(0, 2).map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <DialogTitle className="text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
                  {recipe.name}
                </DialogTitle>
              </div>
            </div>

            <ScrollArea className="flex-1 bg-background">
              <div className="space-y-8 p-6 sm:p-8">
                <div className="grid grid-cols-2 gap-4 border-b pb-6 sm:grid-cols-4">
                  <div className="flex items-center gap-3 rounded-lg bg-muted/50 p-3">
                    <Flame className="h-5 w-5 text-orange-500" />
                    <div>
                      <p className="text-sm text-muted-foreground">Energy</p>
                      <p className="text-lg font-bold">{recipe.calories} kcal</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 rounded-lg bg-muted/50 p-3">
                    <Users className="h-5 w-5 text-blue-500" />
                    <div>
                      <p className="text-sm text-muted-foreground">Servings</p>
                      <p className="text-lg font-bold">{recipe.servings ?? "—"}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 rounded-lg bg-muted/50 p-3">
                    <ListChecks className="h-5 w-5 text-green-500" />
                    <div>
                      <p className="text-sm text-muted-foreground">Instructions</p>
                      <p className="text-lg font-bold">
                        {recipe.instructions?.length ?? 0} steps
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 rounded-lg bg-muted/50 p-3">
                    <Scale className="h-5 w-5 text-purple-500" />
                    <div>
                      <p className="text-sm text-muted-foreground">Nutrition basis</p>
                      <p className="text-sm font-bold">
                        {(recipe.nutrition_basis ?? "unknown").replaceAll("_", " ")}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid gap-8 lg:grid-cols-3">
                  <div className="space-y-8 lg:col-span-1">
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {recipe.description || "No description supplied."}
                    </p>

                    <div className="space-y-4 rounded-xl border bg-card p-5 shadow-sm">
                      <h3 className="font-semibold">Declared macronutrients</h3>
                      {[
                        ["Protein", recipe.macros?.protein, 50, "bg-blue-500"],
                        ["Carbohydrate", recipe.macros?.carbs, 100, "bg-amber-500"],
                        ["Fat", recipe.macros?.fat, 40, "bg-rose-500"],
                      ].map(([label, rawValue, reference, className]) => {
                        const value = typeof rawValue === "number" ? rawValue : 0;
                        return (
                          <div className="space-y-1" key={String(label)}>
                            <div className="flex justify-between text-xs">
                              <span>{String(label)}</span>
                              <span className="font-medium">{value} g</span>
                            </div>
                            <Progress
                              value={percent(value, Number(reference))}
                              className={`h-2 bg-muted [&>div]:${String(className)}`}
                            />
                          </div>
                        );
                      })}
                      <p className="text-xs text-muted-foreground">
                        These bars are relative display scales, not daily targets or clinical guidance.
                      </p>
                    </div>

                    <div className="space-y-4">
                      <h3 className="flex items-center gap-2 text-lg font-semibold">
                        <ChefHat className="h-5 w-5 text-primary" /> Ingredients
                      </h3>
                      <ul className="grid gap-2">
                        {recipe.ingredients?.length ? (
                          recipe.ingredients.map((ingredient, index) => (
                            <li
                              key={`${ingredient}-${index}`}
                              className="flex items-center gap-3 rounded-lg border border-transparent bg-muted/30 p-3"
                            >
                              <span className="h-2 w-2 shrink-0 rounded-full bg-primary/60" />
                              <span className="text-sm font-medium">{ingredient}</span>
                            </li>
                          ))
                        ) : (
                          <li className="text-sm italic text-muted-foreground">
                            No ingredients listed.
                          </li>
                        )}
                      </ul>
                    </div>
                  </div>

                  <div className="space-y-6 lg:col-span-2">
                    <div className="flex items-center justify-between">
                      <h3 className="flex items-center gap-2 text-lg font-semibold">
                        <Utensils className="h-5 w-5 text-primary" /> Instructions
                      </h3>
                      <Badge variant="outline">
                        {recipe.instructions?.length ?? 0} steps
                      </Badge>
                    </div>
                    <div className="space-y-4">
                      {recipe.instructions?.length ? (
                        recipe.instructions.map((step, index) => {
                          const complete = completedSteps.includes(index);
                          return (
                            <button
                              type="button"
                              key={`${index}-${step}`}
                              onClick={() => toggleStep(index)}
                              className={`flex w-full gap-4 rounded-xl border p-4 text-left transition-all ${
                                complete
                                  ? "border-primary/20 bg-primary/5 opacity-60"
                                  : "border-border/50 bg-card hover:border-primary/50"
                              }`}
                            >
                              <span
                                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
                                  complete
                                    ? "bg-primary text-primary-foreground"
                                    : "bg-primary/10 text-primary"
                                }`}
                              >
                                {index + 1}
                              </span>
                              <span
                                className={`pt-1 leading-relaxed ${
                                  complete
                                    ? "text-muted-foreground line-through"
                                    : "text-card-foreground"
                                }`}
                              >
                                {step}
                              </span>
                            </button>
                          );
                        })
                      ) : (
                        <div className="rounded-xl border bg-muted/30 p-6 text-muted-foreground">
                          No reviewed instructions are available.
                        </div>
                      )}
                    </div>

                    <div className="rounded-xl border bg-muted/20 p-4 text-sm">
                      <p className="font-medium">Evidence</p>
                      <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                        <div>
                          <dt className="text-xs text-muted-foreground">Source</dt>
                          <dd>{recipe.source_name ?? "not reported"}</dd>
                        </div>
                        <div>
                          <dt className="text-xs text-muted-foreground">Version</dt>
                          <dd>{recipe.source_version ?? "not reported"}</dd>
                        </div>
                      </dl>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
