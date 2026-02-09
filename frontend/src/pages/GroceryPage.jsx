import InventoryTracker from '../components/grocery/InventoryTracker';

export default function GroceryPage() {
    const { shoppingList, predictions, fetchShoppingList, fetchPredictions } = useGrocery();
    const { profile } = useUser();

    useEffect(() => {
        if (profile?.id) {
            fetchShoppingList(profile.id);
            fetchPredictions(profile.id);
        }
    }, [profile]);

    return (
        <div className="space-y-8 animate-enter">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold mb-2">Smart Grocery</h1>
                <p className="text-gray-400">ML-powered shopping lists and inventory management</p>
            </div>

            {/* Shopping List */}
            <div className="card p-6">
                <div className="flex items-center gap-3 mb-6">
                    <ShoppingCart className="text-primary" size={24} />
                    <h2 className="text-2xl font-semibold">This Week's Shopping List</h2>
                </div>

                {shoppingList.length > 0 ? (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {shoppingList.map((item, i) => (
                            <div key={i} className="p-3 bg-white/5 rounded-lg border border-white/10">
                                <p className="font-medium">{item.name || item}</p>
                                <p className="text-sm text-gray-400">{item.quantity} {item.unit}</p>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-gray-400">Generate a meal plan to see your shopping list</p>
                )}
            </div>

            {/* ML Predictions */}
            <div className="card p-6">
                <div className="flex items-center gap-3 mb-6">
                    <TrendingUp className="text-violet-500" size={24} />
                    <h2 className="text-2xl font-semibold">ML Predictions</h2>
                </div>

                {predictions.length > 0 ? (
                    <div className="space-y-3">
                        {predictions.map((pred, i) => (
                            <div key={i} className="flex justify-between items-center p-4 bg-white/5 rounded-lg border border-white/10">
                                <div>
                                    <p className="font-medium">{pred.item}</p>
                                    <p className="text-sm text-gray-400">Running low - {pred.days_until_empty} days left</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-sm text-gray-400">Suggested</p>
                                    <p className="font-semibold">{pred.recommended_quantity}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-gray-400">No predictions available yet. Log your purchases to enable ML predictions.</p>
                )}
            </div>

            {/* Inventory */}
            <InventoryTracker />
        </div>
    );
}
