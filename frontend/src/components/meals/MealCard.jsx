import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, Shuffle, Star, Clock, ChefHat } from 'lucide-react';
import toast from 'react-hot-toast';

export default function MealCard({
    recipe,
    mealSlot,
    dayIndex,
    onSwap,
    onRegenerate,
    onClick
}) {
    const [isSwapping, setIsSwapping] = useState(false);

    const handleSwap = async (e) => {
        e.stopPropagation();
        setIsSwapping(true);
        try {
            await onSwap(dayIndex, mealSlot);
            toast.success(`${mealSlot} swapped successfully!`);
        } catch (error) {
            toast.error('Failed to swap meal');
        } finally {
            setIsSwapping(false);
        }
    };

    const handleRegenerate = async (e) => {
        e.stopPropagation();
        try {
            await onRegenerate(dayIndex);
            toast.success(`Day ${dayIndex + 1} regenerated!`);
        } catch (error) {
            toast.error('Failed to regenerate day');
        }
    };

    return (
        <motion.div
            whileHover={{ scale: 1.02, y: -4 }}
            whileTap={{ scale: 0.98 }}
            onClick={onClick}
            className="card cursor-pointer overflow-hidden group relative"
        >
            {/* Meal Slot Label */}
            <div className="absolute top-3 left-3 z-10">
                <span className="px-3 py-1 bg-primary/20 text-primary text-xs font-semibold rounded-full border border-primary/30 backdrop-blur-sm">
                    {mealSlot}
                </span>
            </div>

            {/* Recipe Image Placeholder */}
            <div className="h-40 bg-gradient-to-br from-primary/20 to-emerald-700/20 flex items-center justify-center relative overflow-hidden">
                <div className="absolute inset-0 bg-black/20"></div>
                <ChefHat size={48} className="text-white/30 relative z-10" />

                {/* Hover Overlay */}
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                    <button
                        onClick={handleSwap}
                        disabled={isSwapping}
                        className="p-2 bg-white/20 hover:bg-white/30 rounded-full transition-colors"
                        title="Swap this meal"
                    >
                        {isSwapping ? (
                            <RefreshCw size={20} className="text-white animate-spin" />
                        ) : (
                            <Shuffle size={20} className="text-white" />
                        )}
                    </button>
                    <button
                        onClick={onClick}
                        className="p-2 bg-white/20 hover:bg-white/30 rounded-full transition-colors"
                        title="View details"
                    >
                        <Star size={20} className="text-white" />
                    </button>
                </div>
            </div>

            {/* Recipe Info */}
            <div className="p-4">
                <h3 className="font-semibold text-white mb-2 line-clamp-1">{recipe.name}</h3>

                {/* Nutrition Info */}
                <div className="flex gap-4 text-sm text-gray-400 mb-3">
                    <div>
                        <span className="font-medium text-primary">{recipe.nutrition?.calories || 0}</span> cal
                    </div>
                    <div>
                        <span className="font-medium text-emerald-500">{recipe.nutrition?.protein_g || 0}g</span> protein
                    </div>
                </div>

                {/* Tags */}
                {recipe.tags && recipe.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                        {recipe.tags.slice(0, 3).map((tag, i) => (
                            <span
                                key={i}
                                className="px-2 py-0.5 bg-white/5 text-xs text-gray-400 rounded-full"
                            >
                                {tag}
                            </span>
                        ))}
                    </div>
                )}

                {/* Cooking Time */}
                {recipe.cooking_time && (
                    <div className="flex items-center gap-1 mt-2 text-xs text-gray-500">
                        <Clock size={12} />
                        <span>{recipe.cooking_time} min</span>
                    </div>
                )}
            </div>

            {/* Score Indicator */}
            {recipe.taste_score && (
                <div className="absolute top-3 right-3 z-10">
                    <div className="px-2 py-1 bg-violet-500/20 text-violet-400 text-xs font-bold rounded-full border border-violet-500/30 backdrop-blur-sm">
                        {(recipe.taste_score * 100).toFixed(0)}% match
                    </div>
                </div>
            )}
        </motion.div>
    );
}
