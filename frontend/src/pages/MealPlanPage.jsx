import React, { useState } from 'react';
import { useMealPlan } from '../contexts/MealPlanContext';
import { useUser } from '../contexts/UserContext';
import MealCard from '../components/meals/MealCard';
import RecipeDetailModal from '../components/meals/RecipeDetailModal';
import { RefreshCw, Calendar, ChevronDown, ChevronUp } from 'lucide-react';
import toast from 'react-hot-toast';
import { motion, AnimatePresence } from 'framer-motion';

export default function MealPlanPage() {
    const { currentPlan, regenerateDayPlan, swapMealSlot, loading } = useMealPlan();
    const { profile } = useUser();
    const [selectedRecipe, setSelectedRecipe] = useState(null);
    const [expandedDays, setExpandedDays] = useState([0]); // Day 1 expanded by default

    const toggleDay = (index) => {
        setExpandedDays(prev =>
            prev.includes(index)
                ? prev.filter(i => i !== index)
                : [...prev, index]
        );
    };

    const handleRegeneratePlan = async () => {
        toast.loading('Regenerating entire plan...');
        // TODO: Implement full plan regeneration
        toast.success('Plan regenerated!');
    };

    const handleRegenerateDay = async (dayIndex) => {
        if (!profile?.id) {
            toast.error('User profile not found');
            return;
        }

        try {
            await regenerateDayPlan(profile.id, dayIndex);
            toast.success(`Day ${dayIndex + 1} regenerated!`);
        } catch (error) {
            toast.error('Failed to regenerate day');
        }
    };

    const handleSwapMeal = async (dayIndex, mealSlot) => {
        if (!profile?.id) {
            toast.error('User profile not found');
            return;
        }

        try {
            await swapMealSlot(profile.id, dayIndex, mealSlot);
            toast.success(`${mealSlot} swapped!`);
        } catch (error) {
            toast.error('Failed to swap meal');
        }
    };

    if (!currentPlan) {
        return (
            <div className="flex flex-col items-center justify-center h-full">
                <p className="text-gray-400 text-lg">No meal plan available.</p>
                <p className="text-sm text-gray-500 mt-2">Complete onboarding to generate your plan!</p>
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
                <button
                    onClick={handleRegeneratePlan}
                    disabled={loading}
                    className="btn-primary flex items-center gap-2"
                >
                    <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                    Regenerate Plan
                </button>
            </div>

            {/* Weekly Summary */}
            <div className="card p-6">
                <h2 className="text-xl font-semibold mb-4">Weekly Summary</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                        <p className="text-3xl font-bold text-emerald-500">
                            {currentPlan.days.reduce((sum, day) => sum + day.total_stats.calories, 0)}
                        </p>
                        <p className="text-sm text-gray-400">Total Calories</p>
                    </div>
                    <div className="text-center">
                        <p className="text-3xl font-bold text-violet-500">
                            {(currentPlan.days.reduce((sum, day) => sum + day.scores.taste_match, 0) / 7 * 100).toFixed(0)}%
                        </p>
                        <p className="text-sm text-gray-400">Avg Taste Match</p>
                    </div>
                    <div className="text-center">
                        <p className="text-3xl font-bold text-amber-500">
                            {(currentPlan.days.reduce((sum, day) => sum + day.scores.health_match, 0) / 7 * 100).toFixed(0)}%
                        </p>
                        <p className="text-sm text-gray-400">Avg Health Match</p>
                    </div>
                    <div className="text-center">
                        <p className="text-3xl font-bold text-blue-500">
                            {(currentPlan.days.reduce((sum, day) => sum + day.scores.variety, 0) / 7 * 100).toFixed(0)}%
                        </p>
                        <p className="text-sm text-gray-400">Avg Variety</p>
                    </div>
                </div>
            </div>

            {/* Days */}
            <div className="space-y-4">
                {currentPlan.days.map((day, index) => (
                    <motion.div
                        key={index}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className="card overflow-hidden"
                    >
                        {/* Day Header */}
                        <button
                            onClick={() => toggleDay(index)}
                            className="w-full p-6 flex justify-between items-center hover:bg-white/5 transition-colors"
                        >
                            <div className="flex items-center gap-4">
                                <Calendar className="text-primary" size={24} />
                                <div className="text-left">
                                    <h2 className="text-2xl font-semibold">Day {index + 1}</h2>
                                    <p className="text-sm text-gray-400">
                                        {day.total_stats.calories} kcal / {day.total_stats.target_calories} target
                                    </p>
                                </div>
                            </div>

                            <div className="flex items-center gap-6">
                                {/* Scores */}
                                <div className="hidden md:flex gap-4 text-sm">
                                    <div>
                                        <span className="text-gray-400">Health:</span>
                                        <span className="ml-2 font-semibold text-emerald-500">
                                            {(day.scores.health_match * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                    <div>
                                        <span className="text-gray-400">Taste:</span>
                                        <span className="ml-2 font-semibold text-violet-500">
                                            {(day.scores.taste_match * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                    <div>
                                        <span className="text-gray-400">Variety:</span>
                                        <span className="ml-2 font-semibold text-amber-500">
                                            {(day.scores.variety * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                </div>

                                {/* Regenerate Button */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRegenerateDay(index);
                                    }}
                                    disabled={loading}
                                    className="btn-secondary flex items-center gap-2"
                                >
                                    <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                                    Regenerate
                                </button>

                                {/* Expand Icon */}
                                {expandedDays.includes(index) ? (
                                    <ChevronUp size={24} className="text-gray-400" />
                                ) : (
                                    <ChevronDown size={24} className="text-gray-400" />
                                )}
                            </div>
                        </button>

                        {/* Day Content */}
                        <AnimatePresence>
                            {expandedDays.includes(index) && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: 'auto', opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.3 }}
                                    className="border-t border-white/10"
                                >
                                    <div className="p-6">
                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                            {Object.entries(day.meals).map(([slot, recipe]) => (
                                                <div key={slot} className="flex flex-col gap-2">
                                                    <h3 className="uppercase tracking-wider text-sm font-semibold text-gray-500">
                                                        {slot}
                                                    </h3>
                                                    <MealCard
                                                        recipe={recipe}
                                                        mealSlot={slot}
                                                        dayIndex={index}
                                                        onSwap={handleSwapMeal}
                                                        onRegenerate={handleRegenerateDay}
                                                        onClick={() => setSelectedRecipe(recipe)}
                                                    />
                                                </div>
                                            ))}
                                        </div>

                                        {/* Nutrition Summary */}
                                        <div className="mt-6 p-4 bg-white/5 rounded-lg">
                                            <h4 className="font-semibold mb-3">Daily Nutrition</h4>
                                            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                                                <div>
                                                    <span className="text-gray-400">Calories:</span>
                                                    <span className="ml-2 font-semibold">{day.total_stats.calories}</span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-400">Protein:</span>
                                                    <span className="ml-2 font-semibold text-emerald-500">
                                                        {day.total_stats.protein_g}g
                                                    </span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-400">Carbs:</span>
                                                    <span className="ml-2 font-semibold text-amber-500">
                                                        {day.total_stats.carbs_g}g
                                                    </span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-400">Fat:</span>
                                                    <span className="ml-2 font-semibold text-violet-500">
                                                        {day.total_stats.fat_g}g
                                                    </span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-400">Fiber:</span>
                                                    <span className="ml-2 font-semibold text-blue-500">
                                                        {day.total_stats.fiber_g}g
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </motion.div>
                ))}
            </div>

            {/* Recipe Detail Modal */}
            {selectedRecipe && (
                <RecipeDetailModal
                    recipe={selectedRecipe}
                    onClose={() => setSelectedRecipe(null)}
                    onSwap={() => {
                        // TODO: Implement swap from modal
                        setSelectedRecipe(null);
                    }}
                />
            )}
        </div>
    );
}
