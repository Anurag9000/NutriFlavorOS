import React, { useState } from 'react';
import { Users, Trophy, Target, ArrowRight, Share2, MessageCircle } from 'lucide-react';
import { motion } from 'framer-motion';

const ChallengeCard = ({ challenge }) => (
    <div className="bg-gradient-to-br from-gray-800 to-gray-900 border border-white/10 rounded-xl p-5 relative overflow-hidden group hover:border-primary/50 transition-colors">
        <div className={`absolute top-0 right-0 p-2 rounded-bl-xl text-xs font-bold ${challenge.difficulty === 'Hard' ? 'bg-red-500/20 text-red-500' :
                challenge.difficulty === 'Medium' ? 'bg-amber-500/20 text-amber-500' :
                    'bg-emerald-500/20 text-emerald-500'
            }`}>
            {challenge.difficulty}
        </div>

        <div className="flex items-start gap-4 mb-4">
            <div className="text-4xl">{challenge.icon}</div>
            <div>
                <h3 className="font-bold text-lg">{challenge.title}</h3>
                <p className="text-sm text-gray-400">{challenge.description}</p>
            </div>
        </div>

        <div className="space-y-3">
            <div className="flex justify-between text-sm">
                <span className="text-gray-400">{challenge.participants} participants</span>
                <span className="text-primary font-medium">{challenge.reward} XP</span>
            </div>

            <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
                <div
                    className="bg-primary h-full rounded-full"
                    style={{ width: `${challenge.progress}%` }}
                />
            </div>

            <button className="w-full py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm font-medium transition-colors border border-white/10">
                Join Challenge
            </button>
        </div>
    </div>
);

const FriendRow = ({ friend }) => (
    <div className="flex items-center justify-between p-3 hover:bg-white/5 rounded-lg transition-colors">
        <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center text-lg">
                {friend.avatar}
            </div>
            <div>
                <p className="font-medium">{friend.name}</p>
                <p className="text-xs text-gray-400">{friend.status}</p>
            </div>
        </div>
        <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-amber-500 flex items-center gap-1">
                <Target size={12} /> {friend.streak}
            </span>
            <button className="p-2 hover:bg-white/10 rounded-full text-gray-400 hover:text-white transition-colors">
                <MessageCircle size={16} />
            </button>
        </div>
    </div>
);

export default function SocialHub() {
    const [activeTab, setActiveTab] = useState('challenges');

    const challenges = [
        {
            id: 1,
            title: "Plant Power Week",
            description: "Eat 100% plant-based meals for 7 days",
            icon: "🌱",
            participants: 1240,
            reward: 500,
            difficulty: "Medium",
            progress: 45
        },
        {
            id: 2,
            title: "Hydration Hero",
            description: "Drink 3L of water daily for a month",
            icon: "💧",
            participants: 3500,
            reward: 1000,
            difficulty: "Easy",
            progress: 80
        },
        {
            id: 3,
            title: "Sugar Detox",
            description: "No added sugar for 14 days",
            icon: "🚫",
            participants: 890,
            reward: 2000,
            difficulty: "Hard",
            progress: 10
        }
    ];

    const friends = [
        { id: 1, name: "Alex Chen", avatar: "👨‍💻", status: "Cooking Dinner", streak: 12 },
        { id: 2, name: "Sarah Jones", avatar: "👩‍🎨", status: "Completed Goal", streak: 45 },
        { id: 3, name: "Mike Ross", avatar: "🚴", status: "Last active 2h ago", streak: 5 },
        { id: 4, name: "Emma Wilson", avatar: "🧘‍♀️", status: "Shopping", streak: 28 },
    ];

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Main Content (Challenges) */}
            <div className="lg:col-span-2 space-y-6">
                <div className="flex items-center justify-between">
                    <h2 className="text-2xl font-semibold flex items-center gap-2">
                        <Trophy className="text-amber-500" /> Active Challenges
                    </h2>
                    <button className="text-sm text-primary hover:text-primary/80">View All</button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {challenges.map(c => <ChallengeCard key={c.id} challenge={c} />)}
                </div>

                <div className="card p-6 bg-gradient-to-br from-indigo-900/50 to-purple-900/50 border-indigo-500/20">
                    <h3 className="text-xl font-bold mb-2">Invite Friends & Earn</h3>
                    <p className="text-gray-300 mb-4">Get 500 XP for every friend who completes their first week.</p>
                    <button className="bg-white text-indigo-900 py-2 px-6 rounded-lg font-bold hover:bg-gray-100 transition-colors flex items-center gap-2 w-fit">
                        <Share2 size={18} /> Invite Friends
                    </button>
                </div>
            </div>

            {/* Sidebar (Friends) */}
            <div className="card p-6 h-fit">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-semibold flex items-center gap-2">
                        <Users className="text-blue-500" /> Friends
                    </h2>
                    <span className="bg-blue-500/20 text-blue-500 text-xs px-2 py-1 rounded-full font-bold">
                        {friends.length} Online
                    </span>
                </div>

                <div className="space-y-1">
                    {friends.map(f => <FriendRow key={f.id} friend={f} />)}
                </div>

                <button className="w-full mt-6 py-2 border border-dashed border-white/20 rounded-lg text-gray-400 hover:text-white hover:border-white/40 transition-all text-sm">
                    + Add Friend
                </button>
            </div>
        </div>
    );
}
