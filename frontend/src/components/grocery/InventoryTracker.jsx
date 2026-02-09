import React, { useState } from 'react';
import { Package, Plus, Minus, Search, Filter } from 'lucide-react';

export default function InventoryTracker() {
    const [inventory, setInventory] = useState([
        { id: 1, name: 'Rice', quantity: '2 kg', category: 'Pantry', status: 'good' },
        { id: 2, name: 'Olive Oil', quantity: '500 ml', category: 'Pantry', status: 'low' },
        { id: 3, name: 'Eggs', quantity: '4 pcs', category: 'Fridge', status: 'critical' },
        { id: 4, name: 'Milk', quantity: '1 L', category: 'Fridge', status: 'good' },
        { id: 5, name: 'Chicken Breast', quantity: '500g', category: 'Freezer', status: 'good' },
    ]);

    const [filter, setFilter] = useState('All');

    const getStatusColor = (status) => {
        switch (status) {
            case 'good': return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
            case 'low': return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20';
            case 'critical': return 'text-red-500 bg-red-500/10 border-red-500/20';
            default: return 'text-gray-500 bg-gray-500/10 border-gray-500/20';
        }
    };

    const filteredInventory = filter === 'All'
        ? inventory
        : inventory.filter(item => item.category === filter);

    return (
        <div className="card p-6">
            <div className="flex justify-between items-center mb-6">
                <div className="flex items-center gap-3">
                    <Package className="text-emerald-500" size={24} />
                    <h2 className="text-2xl font-semibold">Pantry Inventory</h2>
                </div>
                <button className="btn-primary flex items-center gap-2 text-sm px-3 py-1.5">
                    <Plus size={16} /> Add Item
                </button>
            </div>

            {/* Filters */}
            <div className="flex gap-2 mb-4 overflow-x-auto pb-2">
                {['All', 'Pantry', 'Fridge', 'Freezer'].map(cat => (
                    <button
                        key={cat}
                        onClick={() => setFilter(cat)}
                        className={`px-3 py-1 rounded-full text-sm whitespace-nowrap transition-colors ${filter === cat ? 'bg-primary text-white' : 'bg-white/5 text-gray-400 hover:bg-white/10'
                            }`}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Inventory List */}
            <div className="space-y-3">
                {filteredInventory.map(item => (
                    <div key={item.id} className="flex justify-between items-center p-3 bg-white/5 rounded-lg border border-white/10 hover:border-white/20 transition-colors">
                        <div className="flex items-center gap-3">
                            <div className={`w-2 h-2 rounded-full ${item.status === 'good' ? 'bg-emerald-500' :
                                    item.status === 'low' ? 'bg-yellow-500' : 'bg-red-500'
                                }`} />
                            <div>
                                <p className="font-medium">{item.name}</p>
                                <p className="text-xs text-gray-400">{item.category}</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-4">
                            <span className={`text-xs px-2 py-0.5 rounded border ${getStatusColor(item.status)}`}>
                                {item.status.toUpperCase()}
                            </span>
                            <div className="flex items-center gap-2 bg-black/20 rounded-lg p-1">
                                <button className="p-1 hover:text-white text-gray-400 transition-colors">
                                    <Minus size={14} />
                                </button>
                                <span className="text-sm min-w-[3ch] text-center font-mono">{item.quantity}</span>
                                <button className="p-1 hover:text-white text-gray-400 transition-colors">
                                    <Plus size={14} />
                                </button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
