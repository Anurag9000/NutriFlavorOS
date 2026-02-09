import React from 'react';
import { Activity, Flame, Trophy, Leaf, TrendingUp, Target } from 'lucide-react';
import { motion } from 'framer-motion';

const StatCard = ({ icon: Icon, label, value, subtext, color, delay = 0 }) => {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay, duration: 0.3 }}
            className="card flex items-center gap-4 hover:scale-105 transition-transform cursor-pointer"
        >
            <div className={`p-3 rounded-full`} style={{ backgroundColor: `${color}20`, color }}>
                <Icon size={24} />
            </div>
            <div className="flex-1">
                <p className="text-sm text-gray-400">{label}</p>
                <p className="text-2xl font-bold">{value}</p>
                {subtext && <p className="text-xs text-gray-500 mt-1">{subtext}</p>}
            </div>
        </motion.div>
    );
};

export default function QuickStats({
    calories,
    targetCalories,
    streak,
    achievements,
    carbonSaved,
    protein,
    carbs,
    fat
}) {
    const achievementCount = achievements?.filter(a => a.unlocked).length || 0;
    const totalAchievements = achievements?.length || 9;

    const macroTotal = protein + carbs + fat;
    const proteinPercent = macroTotal > 0 ? ((protein / macroTotal) * 100).toFixed(0) : 0;
    const carbsPercent = macroTotal > 0 ? ((carbs / macroTotal) * 100).toFixed(0) : 0;
    const fatPercent = macroTotal > 0 ? ((fat / macroTotal) * 100).toFixed(0) : 0;

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <StatCard
                icon={Activity}
                label="Calories Today"
                value={`${calories}/${targetCalories}`}
                subtext={`${((calories / targetCalories) * 100).toFixed(0)}% of goal`}
                color="#10b981"
                delay={0}
            />

            <StatCard
                icon={Flame}
                label="Current Streak"
                value={`${streak} days`}
                subtext={streak > 0 ? "Keep it going!" : "Start your streak today!"}
                color="#f59e0b"
                delay={0.1}
            />

            <StatCard
                icon={Trophy}
                label="Achievements"
                value={`${achievementCount}/${totalAchievements}`}
                subtext={`${((achievementCount / totalAchievements) * 100).toFixed(0)}% unlocked`}
                color="#8b5cf6"
                delay={0.2}
            />

            <StatCard
                icon={Leaf}
                label="CO₂ Saved"
                value={`${carbonSaved.toFixed(1)} kg`}
                subtext="This month"
                color="#22c55e"
                delay={0.3}
            />

            <StatCard
                icon={Target}
                label="Macros"
                value={`${proteinPercent}/${carbsPercent}/${fatPercent}`}
                subtext="Protein / Carbs / Fat (%)"
                color="#3b82f6"
                delay={0.4}
            />

            <StatCard
                icon={TrendingUp}
                label="Weekly Progress"
                value="On Track"
                subtext="5/7 days logged"
                color="#ec4899"
                delay={0.5}
            />
        </div>
    );
}
