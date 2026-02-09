import React from 'react';
import { NavLink } from 'react-router-dom';
import {
    LayoutDashboard,
    UtensilsCrossed,
    ShoppingCart,
    BarChart3,
    Trophy,
    Leaf,
    User,
    ChefHat
} from 'lucide-react';

const navItems = [
    { to: '/app/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/app/meal-plan', icon: UtensilsCrossed, label: 'Meal Plan' },
    { to: '/app/grocery', icon: ShoppingCart, label: 'Grocery' },
    { to: '/app/analytics', icon: BarChart3, label: 'Analytics' },
    { to: '/app/gamification', icon: Trophy, label: 'Achievements' },
    { to: '/app/sustainability', icon: Leaf, label: 'Sustainability' },
    { to: '/app/profile', icon: User, label: 'Profile' },
];

export default function Sidebar() {
    return (
        <aside className="w-64 bg-gray-900/50 border-r border-white/10 flex flex-col">
            {/* Logo */}
            <div className="p-6 border-b border-white/10">
                <div className="flex items-center gap-3">
                    <div className="bg-gradient-to-br from-primary to-emerald-700 p-2 rounded-lg">
                        <ChefHat className="text-white" size={24} />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold">
                            NutriFlavor<span className="text-primary">OS</span>
                        </h1>
                        <p className="text-xs text-gray-400">v2.0</p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4">
                <ul className="space-y-2">
                    {navItems.map((item) => (
                        <li key={item.to}>
                            <NavLink
                                to={item.to}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${isActive
                                        ? 'bg-primary/20 text-primary border border-primary/30'
                                        : 'text-gray-400 hover:bg-white/5 hover:text-white'
                                    }`
                                }
                            >
                                <item.icon size={20} />
                                <span className="font-medium">{item.label}</span>
                            </NavLink>
                        </li>
                    ))}
                </ul>
            </nav>

            {/* Footer */}
            <div className="p-4 border-t border-white/10 text-xs text-gray-500">
                <p>© 2026 NutriFlavorOS</p>
                <p>Powered by ML & Science</p>
            </div>
        </aside>
    );
}
