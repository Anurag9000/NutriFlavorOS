import React, { useEffect, useState } from 'react';
import { useMealPlan } from '../contexts/MealPlanContext';
import { useGamification } from '../contexts/GamificationContext';
import { useUser } from '../contexts/UserContext';
import ProgressRings from '../components/ProgressRings';
import QuickStats from '../components/dashboard/QuickStats';
import RecipeCard from '../components/RecipeCard';
import RecipeDetailModal from '../components/meals/RecipeDetailModal';
import RecipeSearch from '../components/meals/RecipeSearch';
import { Calendar } from 'lucide-react';

export default function DashboardPage() {
    const { currentPlan, swapMealSlot } = useMealPlan();
    const { streak, impactMetrics, achievements, fetchStreak, fetchImpactMetrics, fetchAchievements } = useGamification();
    const { profile } = useUser();
    const [selectedRecipe, setSelectedRecipe] = useState(null);

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

    useEffect(() => {
        if (profile?.id) {
            fetchStreak(profile.id);
            fetchImpactMetrics(profile.id);
            fetchAchievements(profile.id);
        }
    }, [profile]);

    if (!currentPlan) {
        return (
            <div className="flex flex-col items-center justify-center h-full">
                <p className="text-gray-400 text-lg">No meal plan generated yet.</p>
                <p className="text-sm text-gray-500 mt-2">Complete onboarding to get started!</p>
            </div>
        );
    }

    const day1 = currentPlan.days[0];

    // Calculate total macros for the day
    const totalProtein = Object.values(day1.meals).reduce((sum, meal) => sum + (meal.nutrition?.protein_g || 0), 0);
    const totalCarbs = Object.values(day1.meals).reduce((sum, meal) => sum + (meal.nutrition?.carbs_g || 0), 0);
    const totalFat = Object.values(day1.meals).reduce((sum, meal) => sum + (meal.nutrition?.fat_g || 0), 0);

    return (
        <div className="space-y-8 animate-enter">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold mb-2">Dashboard</h1>
                    <p className="text-gray-400">Your personalized nutrition overview</p>
                </div>
                <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Calendar size={16} />
                    <span>{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</span>
                </div>
            </div>

            {/* Progress Rings */}
            <div className="card p-8">
                <h2 className="text-xl font-semibold mb-6">Today's Progress</h2>
                <ProgressRings
                    health={day1.scores.health_match}
                    taste={day1.scores.taste_match}
                    variety={day1.scores.variety}
                    sustainability={0.85}
                />
            </div>

            {/* Recipe Search */}
            <div className="card p-8">
                <RecipeSearch />
            </div>

            {/* Quick Stats */}
            <QuickStats
                calories={day1.total_stats.calories}
                targetCalories={day1.total_stats.target_calories}
                streak={streak || 0}
                achievements={achievements}
                carbonSaved={impactMetrics?.carbon_saved || 0}
                protein={totalProtein}
                carbs={totalCarbs}
                fat={totalFat}
            />

            {/* Today's Meals */}
            <div>
                <h2 className="text-2xl font-semibold mb-6">Today's Meals</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {Object.entries(day1.meals).map(([slot, recipe]) => (
                        <div key={slot} className="flex flex-col gap-2">
                            <h3 className="uppercase tracking-wider text-sm font-semibold text-gray-500">{slot}</h3>
                            <div onClick={() => setSelectedRecipe({ ...recipe, slot, dayIndex: 0 })} className="cursor-pointer transition-transform hover:scale-[1.02]">
                                <RecipeCard recipe={recipe} />
                            </div>
                        </div>
                    ))}
                </div>
            </div>

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
        </div>
    );
}
