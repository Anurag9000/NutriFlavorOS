
import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useRecipeDetails } from "@/hooks/useApi";
import { Loader2, Flame, Utensils, Printer, ChefHat, Timer, Users, Leaf } from "lucide-react";

interface RecipeDetailModalProps {
    recipeId: string | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function RecipeDetailModal({ recipeId, open, onOpenChange }: RecipeDetailModalProps) {
    const { data: recipe, isLoading, error } = useRecipeDetails(recipeId);
    const [completedSteps, setCompletedSteps] = useState<number[]>([]);

    // Reset progress when recipe changes
    useEffect(() => {
        setCompletedSteps([]);
    }, [recipeId]);

    if (!recipeId) return null;

    const toggleStep = (index: number) => {
        setCompletedSteps(prev =>
            prev.includes(index)
                ? prev.filter(i => i !== index)
                : [...prev, index]
        );
    };

    const handlePrint = () => {
        window.print();
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl max-h-[95vh] flex flex-col p-0 gap-0 overflow-hidden sm:rounded-xl border-none shadow-2xl">
                {isLoading ? (
                    <div className="h-96 flex flex-col items-center justify-center gap-4 bg-background">
                        <Loader2 className="h-10 w-10 animate-spin text-primary" />
                        <p className="text-muted-foreground animate-pulse">Consulting the Chef AI...</p>
                    </div>
                ) : error || (recipe && !recipe.id) ? (
                    <div className="p-12 text-center flex flex-col items-center gap-4">
                        <div className="h-12 w-12 rounded-full bg-destructive/10 flex items-center justify-center">
                            <Utensils className="h-6 w-6 text-destructive" />
                        </div>
                        <h3 className="text-lg font-semibold">Recipe Not Found</h3>
                        <p className="text-muted-foreground">We couldn't retrieve the details for this recipe.</p>
                        <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
                    </div>
                ) : recipe ? (
                    <>
                        {/* Hero Section */}
                        <div className="relative h-64 sm:h-80 w-full shrink-0 overflow-hidden group">
                            {/* Image */}
                            {recipe.image_url ? (
                                <img
                                    src={recipe.image_url}
                                    alt={recipe.name}
                                    className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                                />
                            ) : (
                                <div className="h-full w-full bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center">
                                    <Utensils className="h-20 w-20 text-white/10" />
                                </div>
                            )}

                            {/* Overlay Gradient */}
                            <div className="absolute inset-0 bg-gradient-to-t from-background via-background/60 to-transparent" />

                            {/* Top Actions */}
                            <div className="absolute top-4 right-4 flex gap-2">
                                <Button size="icon" variant="secondary" className="h-8 w-8 rounded-full bg-background/50 hover:bg-background/80 backdrop-blur-md transition-colors" onClick={handlePrint}>
                                    <Printer className="h-4 w-4" />
                                </Button>
                            </div>

                            {/* Title & Badges */}
                            <div className="absolute bottom-6 left-6 right-6">
                                <div className="flex flex-wrap gap-2 mb-3">
                                    {recipe.cuisine && (
                                        <Badge className="bg-primary/90 hover:bg-primary backdrop-blur-md border-none text-white shadow-sm">
                                            {recipe.cuisine}
                                        </Badge>
                                    )}
                                    {recipe.tags?.slice(0, 2).map(tag => (
                                        <Badge key={tag} variant="secondary" className="bg-background/50 backdrop-blur-md border-none">
                                            {tag}
                                        </Badge>
                                    ))}
                                </div>
                                <DialogTitle className="text-3xl sm:text-4xl font-bold text-foreground leading-tight tracking-tight shadow-black drop-shadow-sm">
                                    {recipe.name}
                                </DialogTitle>
                            </div>
                        </div>

                        {/* Content Scroll Area */}
                        <ScrollArea className="flex-1 bg-background">
                            <div className="p-6 sm:p-8 space-y-8">

                                {/* Quick Stats Grid */}
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pb-6 border-b">
                                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
                                        <div className="h-10 w-10 rounded-full bg-background flex items-center justify-center shadow-sm text-orange-500">
                                            <Flame className="h-5 w-5" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-muted-foreground">Calories</p>
                                            <p className="text-lg font-bold">{recipe.calories}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
                                        <div className="h-10 w-10 rounded-full bg-background flex items-center justify-center shadow-sm text-blue-500">
                                            <Users className="h-5 w-5" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-muted-foreground">Servings</p>
                                            <p className="text-lg font-bold">{recipe.servings || 1}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
                                        <div className="h-10 w-10 rounded-full bg-background flex items-center justify-center shadow-sm text-green-500">
                                            <Timer className="h-5 w-5" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-muted-foreground">Prep Time</p>
                                            <p className="text-lg font-bold">{recipe.readyInMinutes || '?'} min</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
                                        <div className="h-10 w-10 rounded-full bg-background flex items-center justify-center shadow-sm text-purple-500">
                                            <Leaf className="h-5 w-5" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-muted-foreground">Score</p>
                                            <p className="text-lg font-bold">{recipe.healthScore || 'N/A'}</p>
                                        </div>
                                    </div>
                                </div>

                                {/* Main Content Grid */}
                                <div className="grid lg:grid-cols-3 gap-8">

                                    {/* Left Column: Description & Ingredients */}
                                    <div className="lg:col-span-1 space-y-8">
                                        <div className="prose prose-sm dark:prose-invert text-muted-foreground leading-relaxed"
                                            dangerouslySetInnerHTML={{ __html: recipe.description }}
                                        />

                                        {/* Macro Breakdown Visual */}
                                        <div className="space-y-4 p-5 rounded-xl bg-card border shadow-sm">
                                            <h3 className="font-semibold flex items-center gap-2">
                                                <div className="h-1.5 w-1.5 rounded-full bg-primary" />
                                                Macros
                                            </h3>
                                            <div className="space-y-3">
                                                <div className="space-y-1">
                                                    <div className="flex justify-between text-xs">
                                                        <span>Protein</span>
                                                        <span className="font-medium">{recipe.macros?.protein || 0}g</span>
                                                    </div>
                                                    <Progress value={((recipe.macros?.protein || 0) / 50) * 100} className="h-2 bg-muted [&>div]:bg-blue-500" />
                                                </div>
                                                <div className="space-y-1">
                                                    <div className="flex justify-between text-xs">
                                                        <span>Carbs</span>
                                                        <span className="font-medium">{recipe.macros?.carbohydrates || recipe.macros?.carbs || 0}g</span>
                                                    </div>
                                                    <Progress value={((recipe.macros?.carbohydrates || recipe.macros?.carbs || 0) / 100) * 100} className="h-2 bg-muted [&>div]:bg-amber-500" />
                                                </div>
                                                <div className="space-y-1">
                                                    <div className="flex justify-between text-xs">
                                                        <span>Fat</span>
                                                        <span className="font-medium">{recipe.macros?.fat || 0}g</span>
                                                    </div>
                                                    <Progress value={((recipe.macros?.fat || 0) / 40) * 100} className="h-2 bg-muted [&>div]:bg-rose-500" />
                                                </div>
                                            </div>
                                        </div>

                                        {/* Ingredients List */}
                                        <div className="space-y-4">
                                            <h3 className="text-lg font-semibold flex items-center gap-2">
                                                <ChefHat className="h-5 w-5 text-primary" />
                                                Ingredients
                                            </h3>
                                            <ul className="grid gap-2">
                                                {recipe.ingredients?.map((ing, i) => (
                                                    <li key={i} className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-transparent hover:border-border transition-colors">
                                                        <div className="h-2 w-2 rounded-full bg-primary/60 shrink-0" />
                                                        <span className="text-sm font-medium">{ing}</span>
                                                    </li>
                                                ))}
                                                {(!recipe.ingredients || recipe.ingredients.length === 0) && (
                                                    <li className="text-sm text-muted-foreground italic">No ingredients listed.</li>
                                                )}
                                            </ul>
                                        </div>
                                    </div>

                                    {/* Right Column: Instructions */}
                                    <div className="lg:col-span-2 space-y-6">
                                        <div className="flex items-center justify-between">
                                            <h3 className="text-lg font-semibold flex items-center gap-2">
                                                <Utensils className="h-5 w-5 text-primary" />
                                                Instructions
                                            </h3>
                                            <Badge variant="outline" className="text-xs font-normal">
                                                {Array.isArray(recipe.instructions) ? recipe.instructions.length : 1} Steps
                                            </Badge>
                                        </div>

                                        <div className="space-y-4">
                                            {Array.isArray(recipe.instructions) && recipe.instructions.length > 0 ? (
                                                recipe.instructions.map((step, i) => (
                                                    <div
                                                        key={i}
                                                        onClick={() => toggleStep(i)}
                                                        className={`group flex gap-4 p-4 rounded-xl border transition-all cursor-pointer ${completedSteps.includes(i)
                                                            ? "bg-primary/5 border-primary/20 opacity-60"
                                                            : "bg-card border-border/50 hover:border-primary/50 hover:shadow-md"
                                                            }`}
                                                    >
                                                        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-bold text-sm ring-4 ring-background transition-colors ${completedSteps.includes(i)
                                                            ? "bg-primary text-primary-foreground"
                                                            : "bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground"
                                                            }`}>
                                                            {i + 1}
                                                        </div>
                                                        <p className={`text-base leading-relaxed pt-1 transition-all ${completedSteps.includes(i) ? "text-muted-foreground line-through" : "text-card-foreground"
                                                            }`}>
                                                            {step}
                                                        </p>
                                                    </div>
                                                ))
                                            ) : (
                                                <div className="p-6 rounded-xl bg-muted/30 border text-muted-foreground whitespace-pre-line leading-relaxed">
                                                    {typeof recipe.instructions === 'string' && recipe.instructions ? recipe.instructions : "No instructions available."}
                                                </div>
                                            )}
                                        </div>

                                        {/* Micronutrients Grid */}
                                        {recipe.nutrition && (
                                            <div className="pt-8 border-t mt-8">
                                                <h3 className="font-semibold mb-4 text-sm uppercase tracking-wider text-muted-foreground">Micronutrients</h3>
                                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                                    {Object.entries(recipe.nutrition)
                                                        .filter(([key]) => !['calories', 'protein', 'fat', 'carbohydrates', 'sugar', 'fiber', 'sodium'].includes(key.toLowerCase()))
                                                        .slice(0, 8).map(([key, val]) => (
                                                            <div key={key} className="p-3 rounded-lg bg-muted/20 border text-center">
                                                                <p className="text-xs text-muted-foreground capitalize mb-1">{key.replace(/_/g, " ")}</p>
                                                                <p className="font-semibold">{String(val)}</p>
                                                            </div>
                                                        ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </ScrollArea>
                    </>
                ) : null}
            </DialogContent>
        </Dialog>
    );
}
