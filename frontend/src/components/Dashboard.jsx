import React from 'react';
import RecipeCard from './RecipeCard';
import { Activity, BarChart3, UtensilsCrossed, RefreshCw } from 'lucide-react';

export default function Dashboard({ planResponse, userProfile }) {
    if (!planResponse || !planResponse.days) return null;

    // Just show Day 1 for prototype simplicity, or list days
    const day1 = planResponse.days[0];

    return (
        <div className="animate-enter space-y-8">
            {/* Header Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="card flex items-center gap-4">
                    <div className="p-3 bg-emerald-500/20 text-emerald-500 rounded-full">
                        <Activity size={24} />
                    </div>
                    <div>
                        <p className="text-sm text-gray-400">Health Match</p>
                        <p className="text-2xl font-bold">{(day1.scores.health_match * 100).toFixed(0)}%</p>
                    </div>
                </div>

                <div className="card flex items-center gap-4">
                    <div className="p-3 bg-violet-500/20 text-violet-500 rounded-full">
                        <UtensilsCrossed size={24} />
                    </div>
                    <div>
                        <p className="text-sm text-gray-400">Taste Profile</p>
                        <p className="text-2xl font-bold">{(day1.scores.taste_match * 100).toFixed(0)}%</p>
                    </div>
                </div>

                <div className="card flex items-center gap-4">
                    <div className="p-3 bg-amber-500/20 text-amber-500 rounded-full">
                        <BarChart3 size={24} />
                    </div>
                    <div>
                        <p className="text-sm text-gray-400">Dietary Entropy</p>
                        <p className="text-2xl font-bold">{(day1.scores.variety * 100).toFixed(0)}%</p>
                    </div>
                </div>
            </div>

            {/* Plan Section */}
            <div>
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-2xl">Daily Plan <span className="text-gray-500 text-lg font-normal ml-2">({day1.total_stats.calories} kcal / {day1.total_stats.target_calories} target)</span></h2>
                    <button className="btn-secondary flex items-center gap-2">
                        <RefreshCw size={18} /> Regenerate
                    </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {Object.entries(day1.meals).map(([slot, recipe]) => (
                        <div key={slot} className="flex flex-col gap-2">
                            <h3 className="uppercase tracking-wider text-sm font-semibold text-gray-500">{slot}</h3>
                            <RecipeCard recipe={recipe} />
                        </div>
                    ))}
                </div>
            </div>

            {/* Shopping List Mock */}
            <div className="card p-6">
                <h3 className="text-xl mb-4">Quick Shopping List</h3>
                <div className="flex flex-wrap gap-2 text-sm text-gray-300">
                    {Object.values(day1.meals).flatMap(r => r.ingredients).map((ing, i) => (
                        <span key={i} className="bg-white/5 px-2 py-1 rounded border border-white/10">
                            {ing}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
}
