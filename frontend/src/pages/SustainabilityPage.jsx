import React, { useEffect, useState } from 'react';
import { useGamification } from '../contexts/GamificationContext';
import { useUser } from '../contexts/UserContext';
import { Leaf, TreePine, Droplets, Zap, TrendingDown } from 'lucide-react';
import { CarbonFootprintChart } from '../components/analytics/Charts';
import { motion } from 'framer-motion';

export default function SustainabilityPage() {
    const { impactMetrics, fetchImpactMetrics } = useGamification();
    const { profile } = useUser();
    const [timeRange, setTimeRange] = useState('monthly');

    useEffect(() => {
        if (profile?.id) {
            fetchImpactMetrics(profile.id);
        }
    }, [profile]);

    // Sample data for carbon chart
    const carbonData = [
        { month: 'Jan', saved: 12.5, baseline: 25 },
        { month: 'Feb', saved: 15.2, baseline: 25 },
        { month: 'Mar', saved: 18.7, baseline: 25 },
        { month: 'Apr', saved: 22.1, baseline: 25 },
        { month: 'May', saved: 19.8, baseline: 25 },
        { month: 'Jun', saved: 24.3, baseline: 25 },
    ];

    const metrics = impactMetrics || {
        carbon_saved: 0,
        water_saved: 0,
        trees_equivalent: 0,
        energy_saved: 0,
    };

    const impactCards = [
        {
            icon: Leaf,
            value: `${metrics.carbon_saved?.toFixed(1) || 0} kg`,
            label: 'CO₂ Saved',
            color: '#22c55e',
            description: 'Equivalent to driving 0 km less',
        },
        {
            icon: TreePine,
            value: metrics.trees_equivalent || 0,
            label: 'Trees Planted Equivalent',
            color: '#10b981',
            description: 'Based on carbon absorption',
        },
        {
            icon: Droplets,
            value: `${metrics.water_saved || 0} L`,
            label: 'Water Saved',
            color: '#3b82f6',
            description: 'Through sustainable food choices',
        },
        {
            icon: Zap,
            value: `${metrics.energy_saved || 0} kWh`,
            label: 'Energy Saved',
            color: '#f59e0b',
            description: 'From reduced food production',
        },
    ];

    const recommendations = [
        {
            icon: '🌱',
            title: 'Choose plant-based proteins',
            description: 'Reduce carbon footprint by up to 50%',
            impact: 'High Impact',
            color: 'green',
        },
        {
            icon: '🥬',
            title: 'Buy seasonal produce',
            description: 'Lower transportation emissions',
            impact: 'Medium Impact',
            color: 'yellow',
        },
        {
            icon: '♻️',
            title: 'Reduce food waste',
            description: 'Plan meals to minimize waste',
            impact: 'High Impact',
            color: 'green',
        },
        {
            icon: '🌍',
            title: 'Choose local ingredients',
            description: 'Support local farmers and reduce transport',
            impact: 'Medium Impact',
            color: 'yellow',
        },
        {
            icon: '🐟',
            title: 'Select sustainable seafood',
            description: 'Protect ocean ecosystems',
            impact: 'Medium Impact',
            color: 'yellow',
        },
        {
            icon: '🥫',
            title: 'Minimize packaging',
            description: 'Choose bulk or minimal packaging options',
            impact: 'Low Impact',
            color: 'blue',
        },
    ];

    return (
        <div className="space-y-8 animate-enter">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold mb-2">Sustainability Impact</h1>
                    <p className="text-gray-400">Track your environmental footprint</p>
                </div>

                {/* Time Range Selector */}
                <div className="flex gap-2">
                    {['weekly', 'monthly', 'yearly'].map((range) => (
                        <button
                            key={range}
                            onClick={() => setTimeRange(range)}
                            className={`px-4 py-2 rounded-lg capitalize transition-colors ${timeRange === range
                                    ? 'bg-primary text-white'
                                    : 'bg-white/5 text-gray-400 hover:bg-white/10'
                                }`}
                        >
                            {range}
                        </button>
                    ))}
                </div>
            </div>

            {/* Impact Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {impactCards.map((card, index) => (
                    <motion.div
                        key={index}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className="card p-6 text-center hover:scale-105 transition-transform"
                    >
                        <card.icon
                            className="mx-auto mb-3"
                            size={40}
                            style={{ color: card.color }}
                        />
                        <p className="text-3xl font-bold mb-2">{card.value}</p>
                        <p className="text-sm text-gray-400 mb-2">{card.label}</p>
                        <p className="text-xs text-gray-500">{card.description}</p>
                    </motion.div>
                ))}
            </div>

            {/* Carbon Tracker */}
            <div className="card p-6">
                <div className="flex items-center gap-3 mb-6">
                    <TrendingDown className="text-green-500" size={24} />
                    <h2 className="text-2xl font-semibold">Carbon Footprint Trend</h2>
                </div>
                <p className="text-gray-400 mb-4 text-sm">
                    Track your carbon savings over time compared to baseline
                </p>
                <CarbonFootprintChart data={carbonData} />
            </div>

            {/* Comparison Stats */}
            <div className="card p-6">
                <h2 className="text-2xl font-semibold mb-6">Your Impact Compared To</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                        <p className="text-4xl font-bold text-green-500 mb-2">-35%</p>
                        <p className="text-sm text-gray-400">vs Average Diet</p>
                        <p className="text-xs text-gray-500 mt-2">
                            You're doing better than 65% of users!
                        </p>
                    </div>
                    <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                        <p className="text-4xl font-bold text-blue-500 mb-2">-52%</p>
                        <p className="text-sm text-gray-400">vs Meat-Heavy Diet</p>
                        <p className="text-xs text-gray-500 mt-2">
                            Equivalent to 120 km less driving
                        </p>
                    </div>
                    <div className="p-4 bg-violet-500/10 border border-violet-500/30 rounded-lg">
                        <p className="text-4xl font-bold text-violet-500 mb-2">+18%</p>
                        <p className="text-sm text-gray-400">vs Last Month</p>
                        <p className="text-xs text-gray-500 mt-2">
                            Great improvement! Keep it up!
                        </p>
                    </div>
                </div>
            </div>

            {/* Recommendations */}
            <div className="card p-6">
                <h2 className="text-2xl font-semibold mb-6">Sustainable Recommendations</h2>
                <p className="text-gray-400 mb-6">
                    Personalized tips to reduce your environmental impact
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {recommendations.map((rec, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.1 }}
                            className={`p-4 rounded-lg border ${rec.color === 'green'
                                    ? 'bg-green-500/10 border-green-500/30'
                                    : rec.color === 'yellow'
                                        ? 'bg-yellow-500/10 border-yellow-500/30'
                                        : 'bg-blue-500/10 border-blue-500/30'
                                }`}
                        >
                            <div className="flex items-start gap-3">
                                <span className="text-3xl">{rec.icon}</span>
                                <div className="flex-1">
                                    <div className="flex justify-between items-start mb-2">
                                        <p className={`font-medium ${rec.color === 'green'
                                                ? 'text-green-400'
                                                : rec.color === 'yellow'
                                                    ? 'text-yellow-400'
                                                    : 'text-blue-400'
                                            }`}>
                                            {rec.title}
                                        </p>
                                        <span className={`text-xs px-2 py-1 rounded-full ${rec.color === 'green'
                                                ? 'bg-green-500/20 text-green-400'
                                                : rec.color === 'yellow'
                                                    ? 'bg-yellow-500/20 text-yellow-400'
                                                    : 'bg-blue-500/20 text-blue-400'
                                            }`}>
                                            {rec.impact}
                                        </span>
                                    </div>
                                    <p className="text-sm text-gray-400">{rec.description}</p>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>

            {/* Achievements */}
            <div className="card p-6">
                <h2 className="text-2xl font-semibold mb-6">Sustainability Milestones</h2>
                <div className="space-y-4">
                    <div className="flex items-center gap-4 p-4 bg-white/5 rounded-lg">
                        <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center text-2xl">
                            🌍
                        </div>
                        <div className="flex-1">
                            <p className="font-semibold">Eco Warrior</p>
                            <p className="text-sm text-gray-400">Save 100kg CO₂</p>
                            <div className="mt-2 w-full bg-white/10 rounded-full h-2">
                                <div
                                    className="bg-green-500 h-2 rounded-full"
                                    style={{ width: `${(metrics.carbon_saved / 100) * 100}%` }}
                                ></div>
                            </div>
                        </div>
                        <p className="text-sm text-gray-400">
                            {metrics.carbon_saved?.toFixed(1) || 0} / 100 kg
                        </p>
                    </div>

                    <div className="flex items-center gap-4 p-4 bg-white/5 rounded-lg">
                        <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center text-2xl">
                            💧
                        </div>
                        <div className="flex-1">
                            <p className="font-semibold">Water Saver</p>
                            <p className="text-sm text-gray-400">Save 1000L water</p>
                            <div className="mt-2 w-full bg-white/10 rounded-full h-2">
                                <div
                                    className="bg-blue-500 h-2 rounded-full"
                                    style={{ width: `${(metrics.water_saved / 1000) * 100}%` }}
                                ></div>
                            </div>
                        </div>
                        <p className="text-sm text-gray-400">
                            {metrics.water_saved || 0} / 1000 L
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
