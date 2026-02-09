import React, { useState } from 'react';
import { useUser } from '../contexts/UserContext';
import { User, Settings, Heart, Shield, Edit2, LogOut } from 'lucide-react';
import ProfileEditModal from '../components/profile/ProfileEditModal';
import HealthConditionsManager from '../components/profile/HealthConditionsManager';
import SettingsPanel from '../components/profile/SettingsPanel';
import { useNavigate } from 'react-router-dom';

export default function ProfilePage() {
    const { profile, updateProfile, logout } = useUser();
    const [isEditing, setIsEditing] = useState(false);
    const navigate = useNavigate();

    if (!profile) return null;

    const handleLogout = () => {
        logout();
        navigate('/');
    };

    const handleUpdateConditions = async (newConditions) => {
        // In a real app, we'd update this via API
        // For now, we'll update the local profile object structure
        const updatedProfile = {
            ...profile,
            health_conditions: newConditions
        };
        await updateProfile(updatedProfile);
    };

    return (
        <div className="space-y-8 animate-enter max-w-4xl mx-auto">
            {/* Header / Profile Card */}
            <div className="card p-8 bg-gradient-to-br from-gray-900 to-gray-800 border-white/10">
                <div className="flex flex-col md:flex-row items-center gap-6">
                    <div className="w-24 h-24 rounded-full bg-primary/20 flex items-center justify-center text-primary border-2 border-primary/30 shadow-lg shadow-primary/20">
                        <User size={40} />
                    </div>

                    <div className="flex-1 text-center md:text-left">
                        <h1 className="text-3xl font-bold mb-1">{profile.name}</h1>
                        <p className="text-gray-400 mb-4">{profile.email}</p>

                        <div className="flex flex-wrap justify-center md:justify-start gap-4 text-sm mt-2">
                            <span className="bg-white/5 px-3 py-1 rounded-full border border-white/10">
                                {profile.age} years
                            </span>
                            <span className="bg-white/5 px-3 py-1 rounded-full border border-white/10 capitalize">
                                {profile.gender}
                            </span>
                            <span className="bg-white/5 px-3 py-1 rounded-full border border-white/10">
                                {profile.height} cm
                            </span>
                            <span className="bg-white/5 px-3 py-1 rounded-full border border-white/10">
                                {profile.weight} kg
                            </span>
                        </div>
                    </div>

                    <button
                        onClick={() => setIsEditing(true)}
                        className="btn-secondary flex items-center gap-2"
                    >
                        <Edit2 size={16} /> Edit Profile
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Left Column */}
                <div className="space-y-8">
                    {/* Health Conditions */}
                    <HealthConditionsManager
                        conditions={profile.health_conditions || []}
                        onUpdate={handleUpdateConditions}
                    />

                    {/* Preferences & Goals */}
                    <div className="card p-6">
                        <div className="flex items-center gap-3 mb-6">
                            <Heart className="text-pink-500" size={24} />
                            <h2 className="text-xl font-semibold">Preferences & Goals</h2>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="text-sm text-gray-500 block mb-2">Activity Level</label>
                                <p className="font-medium capitalize">{profile.activity_level?.replace('_', ' ')}</p>
                            </div>

                            <div>
                                <label className="text-sm text-gray-500 block mb-2">Dietary Preferences</label>
                                <div className="flex flex-wrap gap-2">
                                    {(profile.dietary_preferences || []).map(pref => (
                                        <span key={pref} className="px-2 py-1 bg-pink-500/10 text-pink-500 rounded text-sm border border-pink-500/20">
                                            {pref}
                                        </span>
                                    ))}
                                    {(!profile.dietary_preferences || profile.dietary_preferences.length === 0) && (
                                        <span className="text-gray-500 italic text-sm">None selected</span>
                                    )}
                                </div>
                            </div>

                            <div>
                                <label className="text-sm text-gray-500 block mb-2">Goal</label>
                                <div className="p-3 bg-white/5 rounded-lg border border-white/10 border-l-4 border-l-primary">
                                    <p className="font-medium">Maintain Healthy Lifestyle</p>
                                    <p className="text-xs text-gray-400 mt-1">Based on your BMI of {(profile.weight / ((profile.height / 100) ** 2)).toFixed(1)}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Column */}
                <div className="space-y-8">
                    <div className="card p-6">
                        <div className="flex items-center gap-3 mb-6">
                            <Settings className="text-gray-400" size={24} />
                            <h2 className="text-xl font-semibold">Settings</h2>
                        </div>
                        <SettingsPanel onLogout={handleLogout} />
                    </div>
                </div>
            </div>

            {/* Modal */}
            {isEditing && (
                <ProfileEditModal
                    profile={profile}
                    onClose={() => setIsEditing(false)}
                    onSave={async (data) => {
                        await updateProfile({ ...profile, ...data });
                        setIsEditing(false);
                    }}
                />
            )}
        </div>
    );
}
