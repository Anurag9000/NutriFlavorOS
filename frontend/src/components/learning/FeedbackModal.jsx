import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import MealRatingInterface from './MealRatingInterface';

export default function FeedbackModal({ recipe, onClose, onSubmit }) {
    if (!recipe) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                onClick={onClose}
            >
                <motion.div
                    initial={{ scale: 0.9, opacity: 0, y: 20 }}
                    animate={{ scale: 1, opacity: 1, y: 0 }}
                    exit={{ scale: 0.9, opacity: 0, y: 20 }}
                    className="bg-gray-900 border border-white/10 rounded-2xl w-full max-w-md overflow-hidden relative"
                    onClick={e => e.stopPropagation()}
                >
                    <button
                        onClick={onClose}
                        className="absolute right-4 top-4 p-2 hover:bg-white/10 rounded-full transition-colors z-10"
                    >
                        <X size={20} />
                    </button>

                    <div className="p-6">
                        <div className="flex items-center gap-4 mb-6">
                            <div className="w-16 h-16 rounded-xl bg-gray-800 flex items-center justify-center overflow-hidden">
                                {/* Placeholder for recipe image */}
                                <span className="text-2xl">🍲</span>
                            </div>
                            <div>
                                <h2 className="text-lg font-bold leading-tight">{recipe.name}</h2>
                                <p className="text-sm text-gray-400">{recipe.calories} kcal</p>
                            </div>
                        </div>

                        <MealRatingInterface
                            recipe={recipe}
                            onClose={onClose}
                            onSubmit={onSubmit}
                        />
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
}
