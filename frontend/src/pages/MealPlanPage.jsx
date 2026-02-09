import React, { useState, useEffect } from 'react';
import { useMealPlan } from '../contexts/MealPlanContext';
import { useUser } from '../contexts/UserContext';
import MealCard from '../components/meals/MealCard';
import RecipeDetailModal from '../components/meals/RecipeDetailModal';
import { Calendar, RefreshCw, ChevronDown, ChevronUp, Search, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { motion, AnimatePresence } from 'framer-motion';
import RecipeSearch from '../components/meals/RecipeSearch';

export default function MealPlanPage() {
    const { currentPlan, regenerateDayPlan, swapMealSlot, createPlan, loading, fetchMealPlan } = useMealPlan();
    const { profile } = useUser();
    const [selectedRecipe, setSelectedRecipe] = useState(null);
    const [expandedDays, setExpandedDays] = useState([0]); // Day 1 expanded by default
    const [showSearch, setShowSearch] = useState(false);

    useEffect(() => {
        if (profile?.id && !currentPlan) {
            // Check if fetchMealPlan exists before calling, otherwise try createPlan
            if (fetchMealPlan) {
                fetchMealPlan(profile.id);
            } else if (createPlan) {
                createPlan(profile.id);
            }
        }
    }, [profile]);

    const toggleDay = (index) => {
        setExpandedDays(prev =>
            prev.includes(index)
                ? prev.filter(i => i !== index)
                : [...prev, index]
        );
    };

    const handleRegeneratePlan = async () => {
        const loadingToastId = toast.loading("Regenerating plan...");
        try {
            if (!profile?.id) {
                toast.error("User profile needed to generate plan", { id: loadingToastId });
                return;
            }
            if (createPlan) {
                await createPlan(profile.id);
            }
            toast.success('Plan regenerated!', { id: loadingToastId });
        } catch (error) {
            console.error("Failed to regenerate plan:", error);
            toast.error("Failed to regenerate plan", { id: loadingToastId });
        }
    };

    const handleSwapMeal = async (dayIndex, mealSlot) => {
        if (!profile?.id) return;

        const toastId = toast.loading('Swapping meal...');
        try {
            await swapMealSlot(profile.id, dayIndex, mealSlot);
            toast.success('Meal swapped!', { id: toastId });
        } catch (error) {
            console.error(error);
            toast.error('Failed to swap meal', { id: toastId });
        }
    };

    if (!currentPlan) {
        return (
            <div className="flex flex-col items-center justify-center p-12 text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4"></div>
                <p className="text-gray-400">Generating your personalized meal plan...</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-enter">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold mb-2">7-Day Meal Plan</h1>
                    <p className="text-gray-400">Your personalized weekly nutrition plan</p>
                </div>
            </div>

            {/* Header Controls */}
            <div className="flex justify-between items-center bg-white/5 p-4 rounded-xl border border-white/10">
                <div className="flex gap-3">
                    <button
                        onClick={handleRegeneratePlan}
                        className="btn-secondary flex items-center gap-2"
                        disabled={loading}
                    >
                        <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
                        Regenerate Week
                    </button>
                    <button
                        onClick={() => setShowSearch(true)}
                        className="btn-primary flex items-center gap-2"
                    >
                        <Search size={18} />
                        Find Recipes
                    </button>
                </div>
            </div>

            {/* Weekly Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-white/5 rounded-xl border border-white/10 text-center">
                    <p className="text-sm text-gray-400">Avg. Daily Calories</p>
                    <p className="text-2xl font-bold text-primary">{currentPlan.summary.avg_calories}</p>
                </div>
                <div className="p-4 bg-white/5 rounded-xl border border-white/10 text-center">
                    <p className="text-sm text-gray-400">Protein Target</p>
                    <p className="text-2xl font-bold text-blue-400">{currentPlan.summary.macro_split.protein}%</p>
                </div>
                <div className="p-4 bg-white/5 rounded-xl border border-white/10 text-center">
                    <p className="text-sm text-gray-400">Projected Health Score</p>
                    <p className="text-2xl font-bold text-emerald-400">92/100</p>
                </div>
                <div className="p-4 bg-white/5 rounded-xl border border-white/10 text-center">
                    <p className="text-sm text-gray-400">Carbon Saved</p>
                    <p className="text-2xl font-bold text-green-400">~12kg</p>
                </div>
            </div>

            {/* Days List */}
            <div className="space-y-6">
                {currentPlan.days.map((day, dayIndex) => (
                    <motion.div
                        key={dayIndex}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: dayIndex * 0.1 }}
                        className="card overflow-hidden"
                    >
                        {/* Day Header */}
                        <div
                            className="p-4 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors"
                            onClick={() => toggleDay(dayIndex)}
                        >
                            <div className="flex items-center gap-4">
                                <div className="p-2 bg-primary/20 text-primary rounded-lg">
                                    <Calendar size={20} />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-lg">Day {dayIndex + 1}</h3>
                                    <p className="text-sm text-gray-400">
                                        {day.total_stats.calories} kcal • {day.total_stats.protein_g}g Protein
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="hidden md:flex gap-2">
                                    <span className={`px-2 py-1 rounded text-xs border ${day.scores.health_match > 0.8 ? 'border-green-500/30 text-green-400' : 'border-yellow-500/30 text-yellow-400'
                                        }`}>
                                        Health: {(day.scores.health_match * 100).toFixed(0)}%
                                    </span>
                                    <span className="px-2 py-1 rounded text-xs border border-blue-500/30 text-blue-400">
                                        Taste: {(day.scores.taste_match * 100).toFixed(0)}%
                                    </span>
                                </div>
                                <button className="p-1">
                                    {expandedDays.includes(dayIndex) ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                                </button>
                            </div>
                        </div>

                        {/* Expandable Content */}
                        <AnimatePresence>
                            {expandedDays.includes(dayIndex) && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: 'auto', opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                >
                                    <div className="p-4 pt-0 grid grid-cols-1 md:grid-cols-3 gap-6 border-t border-white/10 mt-2">
                                        {Object.entries(day.meals).map(([slot, recipe]) => (
                                            <div key={slot} className="flex flex-col gap-2 relative group">
                                                <div className="flex justify-between items-center mb-1">
                                                    <span className="text-sm font-semibold text-gray-500 uppercase tracking-wider">{slot}</span>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleSwapMeal(dayIndex, slot);
                                                        }}
                                                        className="p-1.5 bg-white/10 hover:bg-white/20 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                                                        title="Swap this meal"
                                                    >
                                                        <RefreshCw size={12} />
                                                    </button>
                                                </div>
                                                <div onClick={() => setSelectedRecipe({ ...recipe, slot, dayIndex })} className="cursor-pointer transition-transform hover:scale-[1.02]">
                                                    <MealCard recipe={recipe} slot={slot} />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="p-4 border-t border-white/10 bg-black/20 flex justify-end">
                                        <button
                                            onClick={() => regenerateDayPlan(profile.id, dayIndex)}
                                            className="text-sm text-gray-400 hover:text-white flex items-center gap-2 transition-colors"
                                        >
                                            <RefreshCw size={14} /> Regenerate this day
                                        </button>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </motion.div>
                ))}
            </div>

            {/* Recipe Details Modal using the same component as Dashboard */}
            {selectedRecipe && (
                <RecipeDetailModal
                    recipe={selectedRecipe}
                    onClose={() => setSelectedRecipe(null)}
                    onSwap={() => {
                        if (selectedRecipe.slot && selectedRecipe.dayIndex !== undefined) {
                            handleSwapMeal(selectedRecipe.dayIndex, selectedRecipe.slot);
                            setSelectedRecipe(null);
                        }
                    }}
                />
            )}

            {/* Search Overlay */}
            <AnimatePresence>
                {showSearch && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/90 backdrop-blur-sm z-50 overflow-y-auto"
                    >
                        <div className="max-w-4xl mx-auto p-6 min-h-screen">
                            <div className="flex justify-end mb-4">
                                <button
                                    onClick={() => setShowSearch(false)}
                                    className="p-2 hover:bg-white/10 rounded-full transition-colors"
                                >
                                    <X size={24} />
                                </button>
                            </div>
                            <RecipeSearch />
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
