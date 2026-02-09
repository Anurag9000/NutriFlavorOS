import React, { useState } from 'react';
import { Activity, TrendingUp, BarChart3, PieChart as PieChartIcon } from 'lucide-react';
import {
    HealthTrendChart,
    MacroDistributionChart,
    VarietyChart,
    CalorieProgressChart,
} from '../components/analytics/Charts';
import TasteProfileVisualizer from '../components/learning/TasteProfileVisualizer';

export default function AnalyticsPage() {
    const [timeRange, setTimeRange] = useState('7d');

    // Mock data
    const healthData = [
        { date: 'Mon', score: 82 },
        { date: 'Tue', score: 85 },
        { date: 'Wed', score: 78 },
        { date: 'Thu', score: 90 },
        { date: 'Fri', score: 88 },
        { date: 'Sat', score: 92 },
        { date: 'Sun', score: 95 },
    ];

    const varietyData = [
        { name: 'Vegetables', value: 35 },
        { name: 'Fruits', value: 25 },
        { name: 'Grains', value: 20 },
        { name: 'Proteins', value: 15 },
        { name: 'Dairy', value: 5 },
    ];

    const calorieData = [
        { date: 'Mon', calories: 2100, target: 2000 },
        { date: 'Tue', calories: 1950, target: 2000 },
        { date: 'Wed', calories: 2200, target: 2000 },
        { date: 'Thu', calories: 2000, target: 2000 },
        { date: 'Fri', calories: 1800, target: 2000 },
        { date: 'Sat', calories: 2300, target: 2000 },
        { date: 'Sun', calories: 2050, target: 2000 },
    ];

    const macroData = [
        { name: 'Carbs', value: 45, color: '#10B981' },
        { name: 'Protein', value: 30, color: '#3B82F6' },
        { name: 'Fat', value: 25, color: '#F59E0B' },
    ];

    return (
        <div className="space-y-8 animate-enter">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold mb-2">Analytics</h1>
                    <p className="text-gray-400">Deep dive into your nutrition data</p>
                </div>

                <div className="flex bg-white/5 rounded-lg p-1 border border-white/10">
                    {['7d', '30d', '3m', '1y'].map(range => (
                        <button
                            key={range}
                            onClick={() => setTimeRange(range)}
                            className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${timeRange === range
                                    ? 'bg-primary text-white shadow-lg'
                                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                                }`}
                        >
                            {range}
                        </button>
                    ))}
                </div>
            </div>

            {/* Main Visualizations Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Health Trend */}
                <div className="card p-6 lg:col-span-2">
                    <div className="flex items-center gap-3 mb-6">
                        <Activity className="text-emerald-500" size={24} />
                        <h2 className="text-xl font-semibold">Health Score Trend</h2>
                    </div>
                    <HealthTrendChart data={healthData} />
                </div>

                {/* Macro Distribution */}
                <div className="card p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <PieChartIcon className="text-blue-500" size={24} />
                        <h2 className="text-xl font-semibold">Macro Distribution</h2>
                    </div>
                    <p className="text-gray-400 mb-4 text-sm">Average daily ratio over selected period</p>
                    <MacroDistributionChart data={macroData} />
                </div>

                {/* Calorie Progress */}
                <div className="card p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <Activity className="text-orange-500" size={24} />
                        <h2 className="text-xl font-semibold">Calorie Adherence</h2>
                    </div>
                    <p className="text-gray-400 mb-4 text-sm">Daily intake vs target</p>
                    <CalorieProgressChart data={calorieData} />
                </div>
            </div>

            {/* Row 2: Taste & Variety */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="card p-6">
                    <h3 className="text-xl font-semibold mb-4">Taste Profile</h3>
                    <TasteProfileVisualizer />
                </div>

                <div className="card p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <BarChart3 className="text-amber-500" size={24} />
                        <h2 className="text-xl font-semibold">Dietary Variety</h2>
                    </div>
                    <p className="text-gray-400 mb-4 text-sm">Unique ingredients and food groups</p>
                    <VarietyChart data={varietyData} />
                </div>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="card p-6 text-center">
                    <p className="text-gray-400 text-sm mb-1">Avg. Health Score</p>
                    <p className="text-2xl font-bold text-emerald-400">87</p>
                </div>
                <div className="card p-6 text-center">
                    <p className="text-gray-400 text-sm mb-1">Most Eaten</p>
                    <p className="text-2xl font-bold text-blue-400">Avocado</p>
                </div>
                <div className="card p-6 text-center">
                    <p className="text-gray-400 text-sm mb-1">Cravings count</p>
                    <p className="text-2xl font-bold text-pink-400">12</p>
                </div>
                <div className="card p-6 text-center">
                    <p className="text-gray-400 text-sm mb-1">Data Points</p>
                    <p className="text-2xl font-bold text-gray-200">1,450</p>
                </div>
            </div>
        </div>
    );
}
