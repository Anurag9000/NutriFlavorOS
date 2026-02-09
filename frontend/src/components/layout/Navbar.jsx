import React from 'react';
import { useUser } from '../../contexts/UserContext';
import { Bell, Settings } from 'lucide-react';

export default function Navbar() {
    const { profile } = useUser();

    return (
        <header className="h-16 border-b border-white/10 bg-gray-900/30 backdrop-blur-sm flex items-center justify-between px-8">
            {/* Page Title - will be dynamic based on route */}
            <div>
                <h2 className="text-xl font-semibold">Welcome back{profile?.name ? `, ${profile.name}` : ''}!</h2>
                <p className="text-sm text-gray-400">Let's optimize your nutrition today</p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-4">
                {/* Notifications */}
                <button className="relative p-2 hover:bg-white/5 rounded-lg transition-colors">
                    <Bell size={20} />
                    <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                </button>

                {/* Settings */}
                <button className="p-2 hover:bg-white/5 rounded-lg transition-colors">
                    <Settings size={20} />
                </button>

                {/* User Avatar */}
                <div className="flex items-center gap-3 pl-4 border-l border-white/10">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-emerald-700 flex items-center justify-center font-bold">
                        {profile?.name ? profile.name[0].toUpperCase() : 'U'}
                    </div>
                </div>
            </div>
        </header>
    );
}
