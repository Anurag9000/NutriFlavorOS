import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, X, AlertCircle } from 'lucide-react';

export default function HealthConditionsManager({ conditions = [], onUpdate }) {
    const [newCondition, setNewCondition] = useState('');
    const [isAdding, setIsAdding] = useState(false);

    const handleAdd = () => {
        if (!newCondition.trim()) return;
        const updated = [...conditions, newCondition.trim()];
        onUpdate(updated);
        setNewCondition('');
        setIsAdding(false);
    };

    const handleRemove = (conditionToRemove) => {
        const updated = conditions.filter(c => c !== conditionToRemove);
        onUpdate(updated);
    };

    const commonConditions = [
        "Diabetes Type 1", "Diabetes Type 2", "Hypertension",
        "Celiac Disease", "Lactose Intolerance", "Nut Allergy",
        "Shellfish Allergy", "Vegan", "Vegetarian", "Pescatarian"
    ];

    return (
        <div className="card p-6 border border-white/10 bg-white/5 rounded-2xl">
            <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-2">
                    <AlertCircle className="text-primary" size={20} />
                    <h3 className="text-lg font-semibold">Health Conditions & Dietary Restrictions</h3>
                </div>
                {!isAdding && (
                    <button
                        onClick={() => setIsAdding(true)}
                        className="p-2 hover:bg-white/10 rounded-full transition-colors text-primary"
                    >
                        <Plus size={20} />
                    </button>
                )}
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
                <AnimatePresence>
                    {conditions.map(condition => (
                        <motion.div
                            key={condition}
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.8, opacity: 0 }}
                            className="bg-primary/20 text-primary px-3 py-1.5 rounded-full text-sm flex items-center gap-2 border border-primary/20"
                        >
                            <span>{condition}</span>
                            <button
                                onClick={() => handleRemove(condition)}
                                className="hover:text-white transition-colors"
                            >
                                <X size={14} />
                            </button>
                        </motion.div>
                    ))}
                </AnimatePresence>

                {conditions.length === 0 && !isAdding && (
                    <p className="text-gray-500 text-sm italic">No conditions listed</p>
                )}
            </div>

            <AnimatePresence>
                {isAdding && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                    >
                        <div className="flex gap-2 mb-3">
                            <input
                                value={newCondition}
                                onChange={e => setNewCondition(e.target.value)}
                                placeholder="Enter condition or restriction..."
                                className="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                                onKeyDown={e => e.key === 'Enter' && handleAdd()}
                                autoFocus
                            />
                            <button
                                onClick={handleAdd}
                                className="btn-primary py-1 px-4 text-sm"
                            >
                                Add
                            </button>
                            <button
                                onClick={() => setIsAdding(false)}
                                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            {commonConditions.filter(c => !conditions.includes(c)).map(c => (
                                <button
                                    key={c}
                                    onClick={() => {
                                        onUpdate([...conditions, c]);
                                        setIsAdding(false);
                                    }}
                                    className="text-xs bg-white/5 hover:bg-white/10 border border-white/5 rounded-full px-2 py-1 transition-colors"
                                >
                                    + {c}
                                </button>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
