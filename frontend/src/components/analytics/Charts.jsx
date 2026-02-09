import React from 'react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = ['#10b981', '#8b5cf6', '#f59e0b', '#3b82f6', '#ec4899', '#14b8a6'];

export function HealthTrendChart({ data }) {
    // Sample data structure: [{ date: 'Mon', weight: 70, calories: 2000 }, ...]
    return (
        <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="date" stroke="rgba(255,255,255,0.5)" />
                <YAxis stroke="rgba(255,255,255,0.5)" />
                <Tooltip
                    contentStyle={{
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '8px',
                    }}
                />
                <Legend />
                <Line type="monotone" dataKey="weight" stroke="#10b981" strokeWidth={2} name="Weight (kg)" />
                <Line type="monotone" dataKey="calories" stroke="#f59e0b" strokeWidth={2} name="Calories" />
            </LineChart>
        </ResponsiveContainer>
    );
}

export function MacroDistributionChart({ protein, carbs, fat }) {
    const data = [
        { name: 'Protein', value: protein, color: '#10b981' },
        { name: 'Carbs', value: carbs, color: '#f59e0b' },
        { name: 'Fat', value: fat, color: '#8b5cf6' },
    ];

    return (
        <ResponsiveContainer width="100%" height={300}>
            <PieChart>
                <Pie
                    data={data}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                >
                    {data.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                </Pie>
                <Tooltip
                    contentStyle={{
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '8px',
                    }}
                />
            </PieChart>
        </ResponsiveContainer>
    );
}

export function TastePreferenceRadar({ data }) {
    // Sample data: [{ cuisine: 'Italian', score: 85 }, ...]
    return (
        <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={data}>
                <PolarGrid stroke="rgba(255,255,255,0.1)" />
                <PolarAngleAxis dataKey="cuisine" stroke="rgba(255,255,255,0.5)" />
                <PolarRadiusAxis stroke="rgba(255,255,255,0.3)" />
                <Radar name="Preference" dataKey="score" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.6} />
                <Tooltip
                    contentStyle={{
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '8px',
                    }}
                />
            </RadarChart>
        </ResponsiveContainer>
    );
}

export function VarietyChart({ data }) {
    // Sample data: [{ week: 'Week 1', ingredients: 45, cuisines: 8 }, ...]
    return (
        <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="week" stroke="rgba(255,255,255,0.5)" />
                <YAxis stroke="rgba(255,255,255,0.5)" />
                <Tooltip
                    contentStyle={{
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '8px',
                    }}
                />
                <Legend />
                <Bar dataKey="ingredients" fill="#f59e0b" name="Unique Ingredients" />
                <Bar dataKey="cuisines" fill="#3b82f6" name="Cuisines Tried" />
            </BarChart>
        </ResponsiveContainer>
    );
}

export function CarbonFootprintChart({ data }) {
    // Sample data: [{ month: 'Jan', saved: 12, baseline: 20 }, ...]
    return (
        <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="month" stroke="rgba(255,255,255,0.5)" />
                <YAxis stroke="rgba(255,255,255,0.5)" />
                <Tooltip
                    contentStyle={{
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '8px',
                    }}
                />
                <Legend />
                <Bar dataKey="baseline" fill="rgba(239,68,68,0.5)" name="Baseline CO₂" />
                <Bar dataKey="saved" fill="#22c55e" name="CO₂ Saved" />
            </BarChart>
        </ResponsiveContainer>
    );
}

export function CalorieProgressChart({ data }) {
    // Sample data: [{ day: 'Mon', consumed: 1800, target: 2000 }, ...]
    return (
        <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="day" stroke="rgba(255,255,255,0.5)" />
                <YAxis stroke="rgba(255,255,255,0.5)" />
                <Tooltip
                    contentStyle={{
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '8px',
                    }}
                />
                <Legend />
                <Bar dataKey="target" fill="rgba(255,255,255,0.2)" name="Target" />
                <Bar dataKey="consumed" fill="#10b981" name="Consumed" />
            </BarChart>
        </ResponsiveContainer>
    );
}
