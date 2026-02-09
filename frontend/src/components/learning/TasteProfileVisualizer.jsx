import React, { useState } from 'react';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts';

export default function TasteProfileVisualizer({ tasteProfile }) {
    // Default profile if none provided
    const data = tasteProfile || [
        { subject: 'Salty', A: 80, fullMark: 100 },
        { subject: 'Sweet', A: 45, fullMark: 100 },
        { subject: 'Sour', A: 30, fullMark: 100 },
        { subject: 'Spicy', A: 90, fullMark: 100 },
        { subject: 'Bitter', A: 20, fullMark: 100 },
        { subject: 'Umami', A: 85, fullMark: 100 },
    ];

    return (
        <div className="card p-6 flex flex-col items-center">
            <h3 className="text-xl font-semibold mb-2">Your Taste Profile</h3>
            <p className="text-gray-400 text-sm mb-4">Based on your ratings and history</p>

            <div className="w-full h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="80%" data={data}>
                        <PolarGrid stroke="#ffffff20" />
                        <PolarAngleAxis dataKey="subject" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                        <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                        <Radar
                            name="Taste Preference"
                            dataKey="A"
                            stroke="#8b5cf6"
                            strokeWidth={2}
                            fill="#8b5cf6"
                            fillOpacity={0.4}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#fff' }}
                            itemStyle={{ color: '#8b5cf6' }}
                        />
                    </RadarChart>
                </ResponsiveContainer>
            </div>

            <div className="grid grid-cols-2 gap-4 w-full mt-4">
                <div className="bg-white/5 p-3 rounded-lg border border-white/10 text-center">
                    <p className="text-xs text-gray-400">Top Flavor</p>
                    <p className="text-lg font-bold text-violet-400">Spicy 🔥</p>
                </div>
                <div className="bg-white/5 p-3 rounded-lg border border-white/10 text-center">
                    <p className="text-xs text-gray-400">Least Favorite</p>
                    <p className="text-lg font-bold text-gray-400">Bitter ☕</p>
                </div>
            </div>
        </div>
    );
}
