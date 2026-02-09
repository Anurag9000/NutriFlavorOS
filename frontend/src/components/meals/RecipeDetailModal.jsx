import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Clock, ChefHat, Flame, Users, BookOpen } from 'lucide-react';

export default function RecipeDetailModal({ recipe, onClose, onSwap }) {
    const [activeTab, setActiveTab] = useState('ingredients');

    if (!recipe) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                onClick={onClose}
            >
                <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.9, opacity: 0 }}
                    transition={{ type: 'spring', damping: 20 }}
                    className="bg-gray-900 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden shadow-2xl border border-white/10"
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="relative h-48 bg-gradient-to-br from-primary/30 to-emerald-700/30 p-6 flex items-end">
                        <button
                            onClick={onClose}
                            className="absolute top-4 right-4 p-2 bg-black/30 hover:bg-black/50 rounded-full transition-colors"
                        >
                            <X size={24} className="text-white" />
                        </button>

                        <div>
                            <h2 className="text-3xl font-bold text-white mb-2">{recipe.name}</h2>
                            <div className="flex gap-4 text-sm text-white/80">
                                <div className="flex items-center gap-1">
                                    <Clock size={16} />
                                    <span>{recipe.cooking_time || '30'} min</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <ChefHat size={16} />
                                    <span>{recipe.difficulty || 'Medium'}</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <Users size={16} />
                                    <span>{recipe.servings || '2'} servings</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="flex border-b border-white/10">
                        {['ingredients', 'instructions', 'nutrition'].map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`flex-1 py-3 px-4 capitalize font-medium transition-colors ${activeTab === tab
                                        ? 'text-primary border-b-2 border-primary'
                                        : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                {tab}
                            </button>
                        ))}
                    </div>

                    {/* Content */}
                    <div className="p-6 overflow-y-auto max-h-[calc(90vh-300px)]">
                        {/* Ingredients Tab */}
                        {activeTab === 'ingredients' && (
                            <motion.div
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="space-y-3"
                            >
                                <h3 className="text-xl font-semibold mb-4">Ingredients</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {recipe.ingredients?.map((ingredient, i) => (
                                        <div
                                            key={i}
                                            className="flex items-center gap-3 p-3 bg-white/5 rounded-lg border border-white/10"
                                        >
                                            <div className="w-2 h-2 rounded-full bg-primary"></div>
                                            <span className="text-white">{ingredient}</span>
                                        </div>
                                    ))}
                                </div>
                            </motion.div>
                        )}

                        {/* Instructions Tab */}
                        {activeTab === 'instructions' && (
                            <motion.div
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="space-y-4"
                            >
                                <h3 className="text-xl font-semibold mb-4">Instructions</h3>
                                {recipe.instructions ? (
                                    <div className="space-y-4">
                                        {recipe.instructions.split('\n').map((step, i) => (
                                            <div key={i} className="flex gap-4">
                                                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold">
                                                    {i + 1}
                                                </div>
                                                <p className="text-gray-300 pt-1">{step}</p>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        <div className="flex gap-4">
                                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold">1</div>
                                            <p className="text-gray-300 pt-1">Prepare all ingredients as listed above.</p>
                                        </div>
                                        <div className="flex gap-4">
                                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold">2</div>
                                            <p className="text-gray-300 pt-1">Follow standard cooking procedures for this dish type.</p>
                                        </div>
                                        <div className="flex gap-4">
                                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold">3</div>
                                            <p className="text-gray-300 pt-1">Cook until done and serve hot.</p>
                                        </div>
                                    </div>
                                )}
                            </motion.div>
                        )}

                        {/* Nutrition Tab */}
                        {activeTab === 'nutrition' && (
                            <motion.div
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                            >
                                <h3 className="text-xl font-semibold mb-4">Nutrition Facts</h3>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <div className="p-4 bg-white/5 rounded-lg border border-white/10 text-center">
                                        <p className="text-3xl font-bold text-primary">{recipe.nutrition?.calories || 0}</p>
                                        <p className="text-sm text-gray-400 mt-1">Calories</p>
                                    </div>
                                    <div className="p-4 bg-white/5 rounded-lg border border-white/10 text-center">
                                        <p className="text-3xl font-bold text-emerald-500">{recipe.nutrition?.protein_g || 0}g</p>
                                        <p className="text-sm text-gray-400 mt-1">Protein</p>
                                    </div>
                                    <div className="p-4 bg-white/5 rounded-lg border border-white/10 text-center">
                                        <p className="text-3xl font-bold text-amber-500">{recipe.nutrition?.carbs_g || 0}g</p>
                                        <p className="text-sm text-gray-400 mt-1">Carbs</p>
                                    </div>
                                    <div className="p-4 bg-white/5 rounded-lg border border-white/10 text-center">
                                        <p className="text-3xl font-bold text-violet-500">{recipe.nutrition?.fat_g || 0}g</p>
                                        <p className="text-sm text-gray-400 mt-1">Fat</p>
                                    </div>
                                </div>

                                {/* Additional Nutrition Info */}
                                <div className="mt-6 space-y-3">
                                    <h4 className="font-semibold text-white">Micronutrients</h4>
                                    <div className="grid grid-cols-2 gap-3">
                                        {['Fiber', 'Sugar', 'Sodium', 'Cholesterol'].map((nutrient) => (
                                            <div key={nutrient} className="flex justify-between p-3 bg-white/5 rounded-lg">
                                                <span className="text-gray-400">{nutrient}</span>
                                                <span className="font-medium text-white">-</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </div>

                    {/* Footer Actions */}
                    <div className="p-6 border-t border-white/10 flex gap-3">
                        <button
                            onClick={onSwap}
                            className="flex-1 btn-secondary flex items-center justify-center gap-2"
                        >
                            <Flame size={18} />
                            Swap Recipe
                        </button>
                        <button className="flex-1 btn-primary flex items-center justify-center gap-2">
                            <BookOpen size={18} />
                            Save to Favorites
                        </button>
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
}
