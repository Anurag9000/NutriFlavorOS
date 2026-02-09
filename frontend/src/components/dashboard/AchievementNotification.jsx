import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Confetti from 'react-confetti';
import { Trophy, X } from 'lucide-react';
import toast from 'react-hot-toast';

export default function AchievementNotification({ achievement, onClose }) {
    const [showConfetti, setShowConfetti] = useState(true);

    useEffect(() => {
        // Auto-close after 5 seconds
        const timer = setTimeout(() => {
            onClose();
        }, 5000);

        // Stop confetti after 3 seconds
        const confettiTimer = setTimeout(() => {
            setShowConfetti(false);
        }, 3000);

        return () => {
            clearTimeout(timer);
            clearTimeout(confettiTimer);
        };
    }, [onClose]);

    if (!achievement) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0, scale: 0.8, y: -50 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.8, y: -50 }}
                transition={{ type: 'spring', damping: 15 }}
                className="fixed top-20 right-8 z-50 max-w-md"
            >
                {/* Confetti */}
                {showConfetti && (
                    <div className="fixed inset-0 pointer-events-none">
                        <Confetti
                            width={window.innerWidth}
                            height={window.innerHeight}
                            recycle={false}
                            numberOfPieces={200}
                            gravity={0.3}
                        />
                    </div>
                )}

                {/* Notification Card */}
                <div className="bg-gradient-to-br from-yellow-500/20 to-orange-500/20 backdrop-blur-lg border-2 border-yellow-500/50 rounded-2xl p-6 shadow-2xl">
                    {/* Close Button */}
                    <button
                        onClick={onClose}
                        className="absolute top-3 right-3 p-1 hover:bg-white/10 rounded-full transition-colors"
                    >
                        <X size={20} className="text-white/70" />
                    </button>

                    {/* Header */}
                    <div className="flex items-center gap-3 mb-4">
                        <motion.div
                            animate={{
                                rotate: [0, -10, 10, -10, 10, 0],
                                scale: [1, 1.1, 1],
                            }}
                            transition={{ duration: 0.5, repeat: 2 }}
                            className="text-5xl"
                        >
                            {achievement.icon || '🏆'}
                        </motion.div>
                        <div>
                            <h3 className="text-xl font-bold text-white">Achievement Unlocked!</h3>
                            <p className="text-sm text-yellow-200">{achievement.name}</p>
                        </div>
                    </div>

                    {/* Description */}
                    <p className="text-white/90 mb-4">{achievement.description}</p>

                    {/* Progress */}
                    {achievement.progress && (
                        <div className="space-y-2">
                            <div className="flex justify-between text-sm text-white/70">
                                <span>Progress</span>
                                <span>{achievement.progress.current} / {achievement.progress.target}</span>
                            </div>
                            <div className="w-full bg-white/20 rounded-full h-2">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${(achievement.progress.current / achievement.progress.target) * 100}%` }}
                                    transition={{ duration: 1, delay: 0.5 }}
                                    className="bg-gradient-to-r from-yellow-400 to-orange-500 h-2 rounded-full"
                                />
                            </div>
                        </div>
                    )}

                    {/* Reward */}
                    {achievement.reward && (
                        <div className="mt-4 p-3 bg-white/10 rounded-lg">
                            <p className="text-sm text-white/70">Reward</p>
                            <p className="font-semibold text-yellow-300">{achievement.reward}</p>
                        </div>
                    )}
                </div>
            </motion.div>
        </AnimatePresence>
    );
}

// Toast-style notification (simpler version)
export function showAchievementToast(achievement) {
    toast.custom((t) => (
        <motion.div
            initial={{ opacity: 0, x: 300 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 300 }}
            className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white px-6 py-4 rounded-lg shadow-lg flex items-center gap-3 max-w-md"
        >
            <span className="text-3xl">{achievement.icon || '🏆'}</span>
            <div className="flex-1">
                <p className="font-bold">{achievement.name}</p>
                <p className="text-sm text-white/90">{achievement.description}</p>
            </div>
            <button
                onClick={() => toast.dismiss(t.id)}
                className="p-1 hover:bg-white/20 rounded-full transition-colors"
            >
                <X size={18} />
            </button>
        </motion.div>
    ), {
        duration: 5000,
        position: 'top-right',
    });
}
