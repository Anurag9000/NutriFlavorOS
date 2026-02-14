import React, { useEffect, useState } from 'react';
import { useGamification } from '../contexts/GamificationContext';
import { useUser } from '../contexts/UserContext';
import { Trophy, Award, Flame, TrendingUp, Medal, Star, Users } from 'lucide-react';
import StreakFlame from '../components/StreakFlame';
import { motion, AnimatePresence } from 'framer-motion';
import SocialHub from '../components/social/SocialHub';
import toast from 'react-hot-toast';

const ACHIEVEMENTS = [
    { id: 1, icon: '🥦', name: 'Veggie Master', description: 'Eat 30 different vegetables', target: 30, category: 'nutrition' },
    { id: 2, icon: '💧', name: 'Hydration Hero', description: 'Drink 2L water for 7 days', target: 7, category: 'health' },
    { id: 3, icon: '🔥', name: 'Streak Keeper', description: 'Maintain a 7-day streak', target: 7, category: 'consistency' },
    { id: 4, icon: '🍳', name: 'Home Chef', description: 'Cook 10 meals from scratch', target: 10, category: 'skill' },
    { id: 5, icon: '🌍', name: 'Eco Warrior', description: 'Save 5kg of CO2', target: 5, category: 'sustainability' },
    { id: 6, icon: '🥡', name: 'Zero Waste', description: 'Log 0 food waste for a week', target: 7, category: 'sustainability' },
    { id: 7, icon: '🌶️', name: 'Spice Explorer', description: 'Try 5 new spices', target: 5, category: 'flavor' },
    { id: 8, icon: '🥗', name: 'Balanced Plate', description: 'Hit macro targets for 5 days', target: 5, category: 'nutrition' },
    { id: 9, icon: '🤝', name: 'Team Player', description: 'Complete 5 team challenges', target: 5, category: 'social' },
];

// Helper components
const AchievementsView = ({ achievements }) => {
    const [selectedCategory, setSelectedCategory] = useState('all');

    const categories = [
        { id: 'all', label: 'All', icon: Star },
        { id: 'nutrition', label: 'Nutrition', icon: Trophy },
        { id: 'sustainability', label: 'Eco', icon: Award },
    ];

    const filteredAchievements = selectedCategory === 'all'
        ? ACHIEVEMENTS
        : ACHIEVEMENTS.filter(a => a.category === selectedCategory);

    return (
        <div>
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-semibold flex items-center gap-3">
                    <Trophy className="text-primary" size={28} />
                    Achievements
                </h2>

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
                    // Mock progress for demo
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
    );
};

const LeaderboardView = ({ leaderboards }) => {
    const { fetchLeaderboard } = useGamification();
    const [leaderboardType, setLeaderboardType] = useState('carbon_saved');

    const leaderboardTypes = [
        { id: 'carbon_saved', label: 'Carbon Saved', icon: '🌍' },
        { id: 'streak', label: 'Longest Streak', icon: '🔥' },
        { id: 'health_score', label: 'Health Score', icon: '💪' },
    ];

    useEffect(() => {
        fetchLeaderboard(leaderboardType);
    }, [leaderboardType]);

    const currentLeaderboard = leaderboards[leaderboardType] || [];

    return (
        <div className="card p-6">
            <div className="flex justify-between items-center mb-6">
                <div className="flex items-center gap-3">
                    <TrendingUp className="text-violet-500" size={24} />
                    <h2 className="text-2xl font-semibold">Leaderboard</h2>
                </div>

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
                {currentLeaderboard.length > 0 ? (
                    currentLeaderboard.map((user, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.05 }}
                            className={`flex items-center justify-between p-4 rounded-lg border transition-all ${user.user_id === 'usr_1' // Simple check for current user in demo
                                ? 'bg-primary/20 border-primary/50 scale-105'
                                : 'bg-white/5 border-white/10 hover:bg-white/10'
                                }`}
                        >
                            <div className="flex items-center gap-4">
                                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${user.rank === 1 ? 'bg-yellow-500/20 text-yellow-500' :
                                    user.rank === 2 ? 'bg-gray-400/20 text-gray-400' :
                                        user.rank === 3 ? 'bg-orange-500/20 text-orange-500' :
                                            'bg-white/10 text-gray-400'
                                    }`}>
                                    {user.rank}
                                </div>
                                <div className="text-3xl">{'👤'}</div>
                                <div>
                                    <p className={`font-medium ${user.user_id === 'usr_1' ? 'text-primary' : 'text-white'}`}>
                                        {user.username}
                                    </p>
                                    <p className="text-sm text-gray-400">Rank {user.rank}</p>
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="font-semibold text-lg">{user.score} {leaderboardType === 'carbon_saved' ? 'kg' : leaderboardType === 'streak' ? 'days' : 'pts'}</p>
                                {user.user_id === 'usr_1' && <p className="text-xs text-primary">You're here!</p>}
                            </div>
                        </motion.div>
                    ))
                ) : (
                    <div className="text-center py-8 text-gray-400">Loading leaderboard...</div>
                )}
            </div>
        </div>
    );
};

export default function GamificationPage() {
    const { streak, impactMetrics, achievements, leaderboards, fetchAchievements, fetchStreak, fetchImpactMetrics, fetchLeaderboard } = useGamification();
    const { profile } = useUser();
    const [activeTab, setActiveTab] = useState('achievements');

    useEffect(() => {
        if (profile?.id) {
            fetchAchievements(profile.id);
            fetchStreak(profile.id);
            fetchImpactMetrics(profile.id);
            fetchLeaderboard('carbon_saved');
        }
    }, [profile]);

    return (
        <div className="space-y-8 animate-enter">
            <div>
                <h1 className="text-3xl font-bold mb-2">My Progress</h1>
                <p className="text-gray-400">Track your healthy habits and rewards</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="card p-6 flex flex-col items-center justify-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-orange-500/10 radial-gradient"></div>
                    <StreakFlame days={streak || 0} />
                    <h2 className="text-2xl font-bold mt-4">Day Streak</h2>
                    <p className="text-gray-400">Keep it up!</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div className="card p-4 flex flex-col items-center justify-center bg-white/5">
                        <Award className="text-yellow-500 mb-2" size={32} />
                        <span className="text-2xl font-bold">{achievements?.length || 0}</span>
                        <span className="text-xs text-gray-400 uppercase tracking-widest">Badges</span>
                    </div>
                    <div className="card p-4 flex flex-col items-center justify-center bg-white/5">
                        <Star className="text-purple-500 mb-2" size={32} />
                        <span className="text-2xl font-bold">{impactMetrics?.total_points || 0}</span>
                        <span className="text-xs text-gray-400 uppercase tracking-widest">XP Points</span>
                    </div>
                </div>
            </div>

            <div className="w-full">
                <div className="flex border-b border-white/10 mb-6">
                    <button
                        onClick={() => setActiveTab('achievements')}
                        className={`flex-1 py-3 font-medium border-b-2 transition-colors flex justify-center items-center gap-2 ${activeTab === 'achievements'
                            ? 'border-primary text-primary'
                            : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        <Trophy size={18} /> Achievements
                    </button>
                    <button
                        onClick={() => setActiveTab('leaderboard')}
                        className={`flex-1 py-3 font-medium border-b-2 transition-colors flex justify-center items-center gap-2 ${activeTab === 'leaderboard'
                            ? 'border-primary text-primary'
                            : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        <Medal size={18} /> Leaderboards
                    </button>
                    <button
                        onClick={() => setActiveTab('social')}
                        className={`flex-1 py-3 font-medium border-b-2 transition-colors flex justify-center items-center gap-2 ${activeTab === 'social'
                            ? 'border-primary text-primary'
                            : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        <Users size={18} /> Social
                    </button>
                </div>

                <AnimatePresence mode='wait'>
                    {activeTab === 'achievements' && (
                        <motion.div
                            key="achievements"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                        >
                            <AchievementsView achievements={achievements} />
                        </motion.div>
                    )}
                    {activeTab === 'leaderboard' && (
                        <motion.div
                            key="leaderboard"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                        >
                            <LeaderboardView leaderboards={leaderboards} currentUserId={profile?.id} />
                        </motion.div>
                    )}
                    {activeTab === 'social' && (
                        <motion.div
                            key="social"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                        >
                            <SocialHub />
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}
