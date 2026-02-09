import React, { useState } from 'react';
import { Bell, Shield, Smartphone, Moon, Globe, LogOut } from 'lucide-react';

export default function SettingsPanel({ onLogout }) {
    const [settings, setSettings] = useState({
        notifications: true,
        darkMode: true,
        publicProfile: false,
        dataSharing: false,
        imperialUnits: false
    });

    const toggle = (key) => {
        setSettings(prev => ({ ...prev, [key]: !prev[key] }));
    };

    return (
        <div className="space-y-6">
            <h3 className="text-xl font-semibold mb-4">App Settings</h3>

            <div className="card p-0 overflow-hidden divide-y divide-white/10">
                <div className="p-4 flex justify-between items-center hover:bg-white/5 transition-colors">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-500/20 text-blue-500 rounded-lg">
                            <Bell size={20} />
                        </div>
                        <div>
                            <p className="font-medium">Notifications</p>
                            <p className="text-xs text-gray-400">Receive daily reminders and updates</p>
                        </div>
                    </div>
                    <Toggle checked={settings.notifications} onChange={() => toggle('notifications')} />
                </div>

                <div className="p-4 flex justify-between items-center hover:bg-white/5 transition-colors">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-violet-500/20 text-violet-500 rounded-lg">
                            <Moon size={20} />
                        </div>
                        <div>
                            <p className="font-medium">Dark Mode</p>
                            <p className="text-xs text-gray-400">Easy on the eyes</p>
                        </div>
                    </div>
                    <Toggle checked={settings.darkMode} onChange={() => toggle('darkMode')} />
                </div>

                <div className="p-4 flex justify-between items-center hover:bg-white/5 transition-colors">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-emerald-500/20 text-emerald-500 rounded-lg">
                            <Globe size={20} />
                        </div>
                        <div>
                            <p className="font-medium">Public Profile</p>
                            <p className="text-xs text-gray-400">Show progress on leaderboards</p>
                        </div>
                    </div>
                    <Toggle checked={settings.publicProfile} onChange={() => toggle('publicProfile')} />
                </div>

                <div className="p-4 flex justify-between items-center hover:bg-white/5 transition-colors">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-amber-500/20 text-amber-500 rounded-lg">
                            <Shield size={20} />
                        </div>
                        <div>
                            <p className="font-medium">Data Sharing</p>
                            <p className="text-xs text-gray-400">Share anonymous data for research</p>
                        </div>
                    </div>
                    <Toggle checked={settings.dataSharing} onChange={() => toggle('dataSharing')} />
                </div>
            </div>

            <button
                onClick={onLogout}
                className="w-full p-4 card flex items-center justify-center gap-2 text-red-500 hover:bg-red-500/10 transition-colors border border-red-500/20"
            >
                <LogOut size={20} />
                <span>Log Out</span>
            </button>
        </div>
    );
}

const Toggle = ({ checked, onChange }) => (
    <button
        onClick={onChange}
        className={`w-12 h-6 rounded-full relative transition-colors ${checked ? 'bg-primary' : 'bg-gray-700'}`}
    >
        <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${checked ? 'left-7' : 'left-1'}`} />
    </button>
);
