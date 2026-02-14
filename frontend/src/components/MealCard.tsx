
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Leaf, ArrowLeftRight, ExternalLink, Star } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export interface MealProps {
    id: string;
    name: string;
    type: "breakfast" | "lunch" | "dinner" | "snack";
    calories: number;
    protein: number;
    carbs: number;
    fat: number;
    sustainabilityScore: number;
}

interface MealCardProps {
    meal: MealProps;
    label: string;
    currentRating?: number;
    onRate: (id: string, rating: number) => void;
    onSwap: (type: string) => void;
    onClick: (id: string) => void;
    isSwapping?: boolean;
}

const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
};

export function MealCard({ meal, label, currentRating = 0, onRate, onSwap, onClick, isSwapping }: MealCardProps) {
    return (
        <motion.div
            variants={itemVariants}
            initial="hidden"
            animate="visible"
            exit="hidden"
            whileHover={{ scale: 1.02 }}
            className="w-full"
        >
            <Card className="group border-border/60 overflow-hidden hover:border-primary/50 hover:shadow-lg transition-all duration-300">
                <CardContent className="p-5">
                    <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 space-y-2">
                            <div className="flex items-center justify-between">
                                <Badge variant="secondary" className="text-xs uppercase tracking-wider font-semibold opacity-70">
                                    {label}
                                </Badge>
                                <div className="flex items-center gap-1 text-sustainability text-xs font-medium bg-green-500/10 px-2 py-0.5 rounded-full">
                                    <Leaf className="h-3 w-3" />
                                    <span>{meal.sustainabilityScore}/10 Eco</span>
                                </div>
                            </div>

                            {/* Clickable Title Group */}
                            <div
                                className="group/title flex items-center gap-2 cursor-pointer w-fit"
                                onClick={() => onClick(meal.id)}
                            >
                                <h3 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-foreground to-foreground/70 group-hover/title:from-primary group-hover/title:to-purple-500 transition-all">
                                    {meal.name}
                                </h3>
                                <ExternalLink className="h-4 w-4 opacity-0 -translate-x-2 group-hover/title:opacity-100 group-hover/title:translate-x-0 transition-all duration-300 text-primary" />
                            </div>

                            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground font-medium">
                                <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-orange-500" /> {meal.calories} cal</span>
                                <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-blue-500" /> {meal.protein}g P</span>
                                <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-amber-500" /> {meal.carbs}g C</span>
                                <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-rose-500" /> {meal.fat}g F</span>
                            </div>

                            {/* Star rating */}
                            <div className="flex items-center gap-1 pt-2">
                                <span className="text-xs text-muted-foreground mr-1">Rate:</span>
                                {[1, 2, 3, 4, 5].map((star) => (
                                    <motion.button
                                        key={star}
                                        whileHover={{ scale: 1.2 }}
                                        whileTap={{ scale: 0.9 }}
                                        onClick={(e) => { e.stopPropagation(); onRate(meal.id, star); }}
                                        className="focus:outline-none"
                                    >
                                        <Star
                                            className={`h-4 w-4 transition-colors ${star <= currentRating ? "text-yellow-500 fill-yellow-500" : "text-muted-foreground/30 hover:text-yellow-500/50"}`}
                                        />
                                    </motion.button>
                                ))}
                            </div>
                        </div>

                        <div className="flex flex-col items-end justify-between h-full min-h-[80px]">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => onSwap(meal.type)}
                                disabled={isSwapping}
                                className="text-xs hover:bg-primary/10 hover:text-primary transition-colors"
                            >
                                <ArrowLeftRight className={`h-3 w-3 mr-1 ${isSwapping ? "animate-spin" : ""}`} />
                                Swap
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </motion.div>
    );
}
