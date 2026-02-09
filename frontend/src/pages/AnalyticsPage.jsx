import React, { useState } from 'react';
import { Activity, TrendingUp, BarChart3, PieChart as PieChartIcon } from 'lucide-react';
import {
    HealthTrendChart,
    MacroDistributionChart,
    TastePreferenceRadar,
    VarietyChart,
    CalorieProgressChart,
} from '../components/analytics/Charts';

export default function AnalyticsPage() {
    const [timeRange, setTimeRange] = useState('7d');

    // Sample data - would come from API in production
    const healthData = [
        { date: 'Mon', weight: 70, calories: 1950 },
        { date: 'Tue', weight: 69.8, calories: 2100 },
        { date: 'Wed', weight: 69.7, calories: 1850 },
        { date: 'Thu', weight: 69.5, calories: 2000 },
        { date: 'Fri', weight: 69.4, calories: 1900 },
        { date: 'Sat', weight: 69.3, calories: 2200 },
        { date: 'Sun', weight: 69.2, calories: 1950 },
    ];

    const tasteData = [
        { cuisine: 'Italian', score: 85 },
        { cuisine: 'Mexican', score: 72 },
        { cuisine: 'Indian', score: 90 },
        { cuisine: 'Chinese', score: 68 },
        { cuisine: 'Japanese', score: 75 },
        { cuisine: 'Mediterranean', score: 88 },
    ];

    const varietyData = [
        { week: 'Week 1', ingredients: 45, cuisines: 8 },
        { week: 'Week 2', ingredients: 52, cuisines: 9 },
        { week: 'Week 3', ingredients: 48, cuisines: 7 },
        { week: 'Week 4', ingredients: 55, cuisines: 10 },
    ];

    const calorieData = [
        { day: 'Mon', consumed: 1950, target: 2000 },
        { day: 'Tue', consumed: 2100, target: 2000 },
        { day: 'Wed', consumed: 1850, target: 2000 },
        { day: 'Thu', consumed: 2000, target: 2000 },
        { day: 'Fri', consumed: 1900, target: 2000 },
        { day: 'Sat', consumed: 2200, target: 2000 },
        { day: 'Sun', consumed: 1950, target: 2000 },
    ];

    return (
        <div className="space-y-8 animate-enter">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold mb-2">Analytics & Insights</h1>
                    <p className="text-gray-400">Track your nutrition trends and progress</p>
                </div>

                {/* Time Range Selector */}
                <div className="flex gap-2">
                    {['7d', '30d', '90d', '1y'].map((range) => (
                        <button
                            key={range}
                            onClick={() => setTimeRange(range)}
                            className={`px-4 py-2 rounded-lg transition-colors ${timeRange === range
                                    ? 'bg-primary text-white'
                                    : 'bg-white/5 text-gray-400 hover:bg-white/10'
                                }`}
                        >
                            {range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : range === '90d' ? '90 Days' : '1 Year'}
                        </button>
                    ))}
                </div>
            </div>

            {/* Charts Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Health Insights */}
                <div className="card p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <Activity className="text-emerald-500" size={24} />
                        <h2 className="text-xl font-semibold">Health Trends</h2>
                    </div>
                    <p className="text-gray-400 mb-4 text-sm">Weight and calorie tracking over time</p>
                    <HealthTrendChart data={healthData} />
                </div>

                {/* Taste Insights */}
                <div className="card p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <TrendingUp className="text-violet-500" size={24} />
                        <h2 className="text-xl font-semibold">Taste Preferences</h2>
                    </div>
                    <p className="text-gray-400 mb-4 text-sm">Your favorite cuisines based on ratings</p>
                    <TastePreferenceRadar data={tasteData} />
                </div>

                {/* Variety Metrics */}
                <div className="card p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <BarChart3 className="text-amber-500" size={24} />
                        <h2 className="text-xl font-semibold">Variety Metrics</h2>
                    </div>
                    <p className="text-gray-400 mb-4 text-sm">Unique ingredients and cuisine diversity</p>
                    <VarietyChart data={varietyData} />
                </div>

                {/* Macro Distribution */}
                <div className="card p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <PieChartIcon className="text-blue-500" size={24} />
                        <h2 className="text-xl font-semibold">Macro Distribution</h2>
                    </div>
                    <p className="text-gray-400 mb-4 text-sm">Average protein, carbs, and fat breakdown</p>
                    <MacroDistributionChart protein={120} carbs={250} fat={65} />
                </div>
            </div>

            {/* Weekly Calorie Progress */}
            <div className="card p-6">
                <div className="flex items-center gap-3 mb-4">
                    <Activity className="text-primary" size={24} />
                    <h2 className="text-xl font-semibold">Weekly Calorie Progress</h2>
                </div>
                <p className="text-gray-400 mb-4 text-sm">Daily calorie consumption vs target</p>
                <CalorieProgressChart data={calorieData} />
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="card p-6 text-center">
                    <p className="text-3xl font-bold text-emerald-500 mb-2">94%</p>
                    <p className="text-sm text-gray-400">Avg Health Match</p>
                </div>
                <div className="card p-6 text-center">
                    <p className="text-3xl font-bold text-violet-500 mb-2">87%</p>
                    <p className="text-sm text-gray-400">Avg Taste Match</p>
                </div>
                <div className="card p-6 text-center">
                    <p className="text-3xl font-bold text-amber-500 mb-2">156</p>
                    <p className="text-sm text-gray-400">Unique Ingredients</p>
                </div>
                <div className="card p-6 text-center">
                    <p className="text-3xl font-bold text-blue-500 mb-2">23</p>
                    <p className="text-sm text-gray-400">Cuisines Tried</p>
                </div>
            </div>
        </div>
    );
}
