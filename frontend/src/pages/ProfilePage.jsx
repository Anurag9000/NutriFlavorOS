import React from 'react';
import { useUser } from '../contexts/UserContext';
import { User, Settings, Heart, Pill } from 'lucide-react';

export default function ProfilePage() {
    const { profile } = useUser();

    return (
        <div className="space-y-8 animate-enter">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold mb-2">Profile & Settings</h1>
                <p className="text-gray-400">Manage your personal information and preferences</p>
            </div>

            {/* Profile Info */}
            <div className="card p-6">
                <div className="flex items-center gap-3 mb-6">
                    <User className="text-primary" size={24} />
                    <h2 className="text-2xl font-semibold">Personal Information</h2>
                </div>

                {profile ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="text-sm text-gray-400">Age</label>
                            <p className="text-lg font-medium">{profile.age} years</p>
                        </div>
                        <div>
                            <label className="text-sm text-gray-400">Weight</label>
                            <p className="text-lg font-medium">{profile.weight} kg</p>
                        </div>
                        <div>
                            <label className="text-sm text-gray-400">Height</label>
                            <p className="text-lg font-medium">{profile.height} cm</p>
                        </div>
                        <div>
                            <label className="text-sm text-gray-400">Activity Level</label>
                            <p className="text-lg font-medium capitalize">{profile.activity_level}</p>
                        </div>
                        <div>
                            <label className="text-sm text-gray-400">Health Goal</label>
                            <p className="text-lg font-medium capitalize">{profile.health_goal}</p>
                        </div>
                        <div>
                            <label className="text-sm text-gray-400">Dietary Preference</label>
                            <p className="text-lg font-medium capitalize">{profile.dietary_preference}</p>
                        </div>
                    </div>
                ) : (
                    <p className="text-gray-400">No profile information available</p>
                )}
            </div>

            {/* Preferences */}
            <div className="card p-6">
                <div className="flex items-center gap-3 mb-6">
                    <Heart className="text-red-500" size={24} />
                    <h2 className="text-2xl font-semibold">Food Preferences</h2>
                </div>

                {profile ? (
                    <div className="space-y-4">
                        <div>
                            <label className="text-sm text-gray-400 mb-2 block">Liked Ingredients</label>
                            <div className="flex flex-wrap gap-2">
                                {profile.liked_ingredients?.map((ing, i) => (
                                    <span key={i} className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-sm">
                                        {ing}
                                    </span>
                                ))}
                            </div>
                        </div>
                        <div>
                            <label className="text-sm text-gray-400 mb-2 block">Disliked Ingredients</label>
                            <div className="flex flex-wrap gap-2">
                                {profile.disliked_ingredients?.map((ing, i) => (
                                    <span key={i} className="px-3 py-1 bg-red-500/20 text-red-400 rounded-full text-sm">
                                        {ing}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>
                ) : (
                    <p className="text-gray-400">No preferences set</p>
                )}
            </div>

            {/* Health Conditions */}
            <div className="card p-6">
                <div className="flex items-center gap-3 mb-6">
                    <Pill className="text-blue-500" size={24} />
                    <h2 className="text-2xl font-semibold">Health & Medications</h2>
                </div>
                <p className="text-gray-400">Manage health conditions and medications for personalized recommendations</p>
                <button className="btn-secondary mt-4">Add Health Condition</button>
            </div>

            {/* Settings */}
            <div className="card p-6">
                <div className="flex items-center gap-3 mb-6">
                    <Settings className="text-gray-400" size={24} />
                    <h2 className="text-2xl font-semibold">Settings</h2>
                </div>
                <div className="space-y-4">
                    <div className="flex justify-between items-center p-4 bg-white/5 rounded-lg">
                        <div>
                            <p className="font-medium">Notifications</p>
                            <p className="text-sm text-gray-400">Meal reminders and achievements</p>
                        </div>
                        <button className="btn-secondary">Configure</button>
                    </div>
                    <div className="flex justify-between items-center p-4 bg-white/5 rounded-lg">
                        <div>
                            <p className="font-medium">Privacy</p>
                            <p className="text-sm text-gray-400">Data sharing and visibility</p>
                        </div>
                        <button className="btn-secondary">Manage</button>
                    </div>
                    <div className="flex justify-between items-center p-4 bg-white/5 rounded-lg">
                        <div>
                            <p className="font-medium">Export Data</p>
                            <p className="text-sm text-gray-400">Download your nutrition data</p>
                        </div>
                        <button className="btn-secondary">Export</button>
                    </div>
                </div>
            </div>
        </div>
    );
}
