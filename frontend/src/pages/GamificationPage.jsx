import React, { useEffect, useState } from 'react';
import { useGamification } from '../contexts/GamificationContext';
import { useUser } from '../contexts/UserContext';
import { Trophy, Award, Flame, TrendingUp, Medal, Star } from 'lucide-react';
import StreakFlame from '../components/StreakFlame';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';

const ACHIEVEMENTS = [
    { id: 1, icon: '🌍', name: 'Eco Warrior', description: 'Save 100kg CO2', target: 100, category: 'sustainability' },
    { id: 2, icon: '🌳', name: 'Tree Planter', description: 'Save equivalent of 10 trees', target: 10, category: 'sustainability' },
    { id: 3, icon: '💧', name: 'Water Saver', description: 'Save 1000L water', target: 1000, category: 'sustainability' },
    { id: 4, icon: '🗺️', name: 'Flavor Explorer', description: 'Try 50 unique ingredients', target: 50, category: 'variety' },
    { id: 5, icon: '👨‍🍳', name: 'Cuisine Master', description: 'Try 10 cuisines', target: 10, category: 'variety' },
    { id: 6, icon: '🎯', name: 'Macro Master', description: '30-day macro streak', target: 30, category: 'health' },
    { id: 7, icon: '💪', name: 'Health Champion', description: '30-day health streak', target: 30, category: 'health' },
    { id: 8, icon: '⭐', name: 'Taste Adventurer', description: 'Rate 100 meals', target: 100, category: 'engagement' },
    { id: 9, icon: '🤝', name: 'Team Player', description: 'Complete 5 team challenges', target: 5, category: 'social' },
];

export default function GamificationPage() {
    const { achievements, leaderboards, streak, fetchAchievements, fetchLeaderboard, fetchStreak } = useGamification();
    const { profile } = useUser();
    const [selectedCategory, setSelectedCategory] = useState('all');
    const [leaderboardType, setLeaderboardType] = useState('carbon_saved');

    useEffect(() => {
        if (profile?.id) {
            fetchAchievements(profile.id);
            fetchLeaderboard(leaderboardType);
            fetchStreak(profile.id);
        }
    }, [profile, leaderboardType]);

    const categories = [
        { id: 'all', label: 'All', icon: Star },
        { id: 'sustainability', label: 'Sustainability', icon: Flame },
        { id: 'variety', label: 'Variety', icon: Award },
        { id: 'health', label: 'Health', icon: Trophy },
        { id: 'engagement', label: 'Engagement', icon: Medal },
    ];

    const filteredAchievements = selectedCategory === 'all'
        ? ACHIEVEMENTS
        : ACHIEVEMENTS.filter(a => a.category === selectedCategory);

    const leaderboardTypes = [
        { id: 'carbon_saved', label: 'Carbon Saved', icon: '🌍' },
        { id: 'streak', label: 'Longest Streak', icon: '🔥' },
        { id: 'variety', label: 'Most Variety', icon: '🗺️' },
        { id: 'health_score', label: 'Health Score', icon: '💪' },
    ];

    // Sample leaderboard data
    const leaderboardData = [
        { rank: 1, name: 'Alex Chen', value: 95.2, level: 12, avatar: '👨‍🍳' },
        { rank: 2, name: 'Sarah Kim', value: 88.7, level: 10, avatar: '👩‍🍳' },
        { rank: 3, name: 'Mike Johnson', value: 82.3, level: 9, avatar: '🧑‍🍳' },
        { rank: 4, name: 'Emma Davis', value: 76.8, level: 8, avatar: '👩‍🍳' },
        { rank: 5, name: 'You', value: 71.5, level: 7, avatar: '😊', isCurrentUser: true },
        { rank: 6, name: 'James Wilson', value: 68.2, level: 7, avatar: '🧑‍🍳' },
        { rank: 7, name: 'Lisa Brown', value: 64.9, level: 6, avatar: '👩‍🍳' },
    ];

    return (
        <div className="space-y-8 animate-enter">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold mb-2">Achievements & Leaderboards</h1>
                <p className="text-gray-400">Track your progress and compete with others</p>
            </div>

            {/* Streak Section */}
            <div className="card p-8">
                <div className="flex flex-col md:flex-row items-center gap-8">
                    <StreakFlame streakDays={streak || 0} />
                    <div className="flex-1">
                        <h2 className="text-2xl font-bold mb-3">Keep Your Streak Alive!</h2>
                        <p className="text-gray-400 mb-4">
                            You've logged meals for {streak || 0} consecutive days. Don't break the chain!
                        </p>
                        <div className="flex gap-4">
                            <button className="btn-primary">Log Today's Meal</button>
                            <button className="btn-secondary">View History</button>
                        </div>
                    </div>
                    {/* Streak Stats */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="text-center p-4 bg-white/5 rounded-lg">
                            <p className="text-2xl font-bold text-primary">{streak || 0}</p>
                            <p className="text-xs text-gray-400">Current</p>
                        </div>
                        <div className="text-center p-4 bg-white/5 rounded-lg">
                            <p className="text-2xl font-bold text-amber-500">15</p>
                            <p className="text-xs text-gray-400">Best</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Achievements Section */}
            <div>
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-2xl font-semibold flex items-center gap-3">
                        <Trophy className="text-primary" size={28} />
                        Achievements
                    </h2>

                    {/* Category Filter */}
                    <div className="flex gap-2">
                        {categories.map((cat) => (
                            <button
                                key={cat.id}
                                onClick={() => setSelectedCategory(cat.id)}
                                className={`px-4 py-2 rounded-lg transition-colors flex items-center gap-2 ${selectedCategory === cat.id
                                        ? 'bg-primary text-white'
                                        : 'bg-white/5 text-gray-400 hover:bg-white/10'
                                    }`}
                            >
                                <cat.icon size={16} />
                                <span className="hidden md:inline">{cat.label}</span>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredAchievements.map((ach, index) => {
                        const progress = Math.min((Math.random() * ach.target).toFixed(0), ach.target);
                        const percentage = (progress / ach.target) * 100;
                        const isUnlocked = percentage >= 100;

                        return (
                            <motion.div
                                key={ach.id}
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ delay: index * 0.05 }}
                                className={`card p-6 text-center relative overflow-hidden ${isUnlocked ? 'border-2 border-primary' : ''
                                    }`}
                            >
                                {isUnlocked && (
                                    <div className="absolute top-2 right-2">
                                        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                                            <Star size={16} className="text-white fill-white" />
                                        </div>
                                    </div>
                                )}

                                <motion.div
                                    animate={isUnlocked ? { scale: [1, 1.2, 1] } : {}}
                                    transition={{ duration: 0.5 }}
                                    className="text-5xl mb-3"
                                >
                                    {ach.icon}
                                </motion.div>
                                <h3 className="text-lg font-semibold mb-2">{ach.name}</h3>
                                <p className="text-sm text-gray-400 mb-4">{ach.description}</p>

                                <div className="w-full bg-white/10 rounded-full h-2 mb-2">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${percentage}%` }}
                                        transition={{ duration: 1, delay: index * 0.05 }}
                                        className={`h-2 rounded-full ${isUnlocked ? 'bg-primary' : 'bg-gray-500'
                                            }`}
                                    ></motion.div>
                                </div>
                                <p className="text-xs text-gray-500">
                                    {progress} / {ach.target} {isUnlocked && '✓ Unlocked!'}
                                </p>
                            </motion.div>
                        );
                    })}
                </div>
            </div>

            {/* Leaderboard Section */}
            <div className="card p-6">
                <div className="flex justify-between items-center mb-6">
                    <div className="flex items-center gap-3">
                        <TrendingUp className="text-violet-500" size={24} />
                        <h2 className="text-2xl font-semibold">Leaderboard</h2>
                    </div>

                    {/* Leaderboard Type Selector */}
                    <div className="flex gap-2">
                        {leaderboardTypes.map((type) => (
                            <button
                                key={type.id}
                                onClick={() => setLeaderboardType(type.id)}
                                className={`px-4 py-2 rounded-lg transition-colors flex items-center gap-2 ${leaderboardType === type.id
                                        ? 'bg-primary text-white'
                                        : 'bg-white/5 text-gray-400 hover:bg-white/10'
                                    }`}
                            >
                                <span>{type.icon}</span>
                                <span className="hidden md:inline">{type.label}</span>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="space-y-3">
                    {leaderboardData.map((user, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.05 }}
                            className={`flex items-center justify-between p-4 rounded-lg border transition-all ${user.isCurrentUser
                                    ? 'bg-primary/20 border-primary/50 scale-105'
                                    : 'bg-white/5 border-white/10 hover:bg-white/10'
                                }`}
                        >
                            <div className="flex items-center gap-4">
                                {/* Rank */}
                                <div
                                    className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${user.rank === 1
                                            ? 'bg-yellow-500/20 text-yellow-500'
                                            : user.rank === 2
                                                ? 'bg-gray-400/20 text-gray-400'
                                                : user.rank === 3
                                                    ? 'bg-orange-500/20 text-orange-500'
                                                    : 'bg-white/10 text-gray-400'
                                        }`}
                                >
                                    {user.rank}
                                </div>

                                {/* Avatar */}
                                <div className="text-3xl">{user.avatar}</div>

                                {/* User Info */}
                                <div>
                                    <p className={`font-medium ${user.isCurrentUser ? 'text-primary' : 'text-white'}`}>
                                        {user.name}
                                    </p>
                                    <p className="text-sm text-gray-400">Level {user.level}</p>
                                </div>
                            </div>

                            {/* Score */}
                            <div className="text-right">
                                <p className="font-semibold text-lg">{user.value} {leaderboardType === 'carbon_saved' ? 'kg' : leaderboardType === 'streak' ? 'days' : '%'}</p>
                                {user.isCurrentUser && (
                                    <p className="text-xs text-primary">You're here!</p>
                                )}
                            </div>
                        </motion.div>
                    ))}
                </div>

                <div className="mt-6 text-center">
                    <button className="btn-secondary">View Full Leaderboard</button>
                </div>
            </div>

            {/* Challenges Section */}
            <div className="card p-6">
                <h2 className="text-2xl font-semibold mb-6">Active Challenges</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 bg-gradient-to-br from-violet-500/20 to-purple-500/20 border border-violet-500/30 rounded-lg">
                        <div className="flex justify-between items-start mb-3">
                            <div>
                                <h3 className="font-semibold text-violet-400">Plant-Based Week</h3>
                                <p className="text-sm text-gray-400">Eat plant-based for 7 days</p>
                            </div>
                            <span className="text-xs px-2 py-1 bg-violet-500/30 rounded-full">3 days left</span>
                        </div>
                        <div className="w-full bg-white/10 rounded-full h-2 mb-2">
                            <div className="bg-violet-500 h-2 rounded-full" style={{ width: '57%' }}></div>
                        </div>
                        <p className="text-xs text-gray-400">4 / 7 days completed</p>
                    </div>

                    <div className="p-4 bg-gradient-to-br from-green-500/20 to-emerald-500/20 border border-green-500/30 rounded-lg">
                        <div className="flex justify-between items-start mb-3">
                            <div>
                                <h3 className="font-semibold text-green-400">Variety Champion</h3>
                                <p className="text-sm text-gray-400">Try 20 new ingredients</p>
                            </div>
                            <span className="text-xs px-2 py-1 bg-green-500/30 rounded-full">14 days left</span>
                        </div>
                        <div className="w-full bg-white/10 rounded-full h-2 mb-2">
                            <div className="bg-green-500 h-2 rounded-full" style={{ width: '35%' }}></div>
                        </div>
                        <p className="text-xs text-gray-400">7 / 20 ingredients</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
