import { useState } from "react";
import AppLayout from "@/components/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ShoppingCart, Check, Plus, Package, DollarSign, AlertTriangle } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useShoppingList, useLogPurchase, useLogConsumption } from "@/hooks/useApi";
import { useToast } from "@/hooks/use-toast";


export default function GroceryPredictions() {
  const { user } = useAuth();
  const userId = user?.id ?? "usr_1";
  const { toast } = useToast();

  const [week, setWeek] = useState<"this" | "next">("this");
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [showPurchaseForm, setShowPurchaseForm] = useState(false);
  const [purchaseItem, setPurchaseItem] = useState("");
  const [purchaseQty, setPurchaseQty] = useState("");
  const [purchasePrice, setPurchasePrice] = useState("");

  const daysAhead = week === "this" ? 7 : 14;
  const shoppingListQ = useShoppingList(userId, daysAhead);
  const purchaseMutation = useLogPurchase();
  const consumeMutation = useLogConsumption();

  const toggle = (id: string) => {
    setChecked((prev) => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  // Build display items — use API data if available, else mock
  const apiItems = shoppingListQ.data?.shopping_list;
  const summary = shoppingListQ.data?.summary;

  interface DisplayItem {
    id: string;
    name: string;
    category: string;
    quantity: string;
    frequency: string;
    confidence: number;
    urgency?: number;
    estimatedCost?: number;
  }

  let displayItems: DisplayItem[];
  if (apiItems && apiItems.length > 0) {
    displayItems = apiItems.map((item, i) => ({
      id: `api_${i}`,
      name: item.item,
      category: item.category ?? "General",
      quantity: `${item.predicted_quantity}`,
      frequency: item.urgency > 0.7 ? "Urgent" : "Regular",
      confidence: Math.round(Math.min(item.urgency * 100, 99)),
      urgency: item.urgency,
      estimatedCost: item.estimated_cost,
    }));
  } else {
    displayItems = []; // No API data available
  }

  const categories = [...new Set(displayItems.map((g) => g.category))];

  // Log purchase
  const handleLogPurchase = async () => {
    if (!purchaseItem || !purchaseQty) return;
    try {
      await purchaseMutation.mutateAsync({
        userId,
        items: [{
          item: purchaseItem,
          quantity: parseFloat(purchaseQty),
          price: parseFloat(purchasePrice) || 0,
        }],
      });
      toast({ title: "Purchase logged", description: `${purchaseItem} × ${purchaseQty} recorded` });
      setPurchaseItem("");
      setPurchaseQty("");
      setPurchasePrice("");
      setShowPurchaseForm(false);
    } catch {
      toast({ title: "Failed to log", description: "Backend unavailable", variant: "destructive" });
    }
  };

  // Log consumption
  const handleConsume = async (itemName: string) => {
    try {
      await consumeMutation.mutateAsync({ userId, item: itemName, quantity: 1 });
      toast({ title: "Consumption logged", description: `Used 1 unit of ${itemName}` });
    } catch {
      toast({ title: "Failed to log", description: "Backend unavailable", variant: "destructive" });
    }
  };

  return (
    <AppLayout>
      <div className="space-y-6 max-w-4xl mx-auto">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold">Grocery Predictions</h1>
            <p className="text-muted-foreground text-sm">AI-predicted items you'll need</p>
          </div>
          <div className="flex gap-2">
            {(["this", "next"] as const).map((w) => (
              <button
                key={w}
                onClick={() => setWeek(w)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${week === w ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground hover:bg-accent"
                  }`}
              >
                {w === "this" ? "This Week" : "Next Week"}
              </button>
            ))}
          </div>
        </div>

        {/* Summary Bar */}
        {summary && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <Package className="h-5 w-5 text-primary" />
                <div>
                  <p className="text-lg font-bold">{summary.total_items}</p>
                  <p className="text-xs text-muted-foreground">Total items</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <DollarSign className="h-5 w-5 text-taste" />
                <div>
                  <p className="text-lg font-bold">₹{summary.estimated_total_cost}</p>
                  <p className="text-xs text-muted-foreground">Est. cost</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <AlertTriangle className="h-5 w-5 text-destructive" />
                <div>
                  <p className="text-lg font-bold">{summary.urgent_items}</p>
                  <p className="text-xs text-muted-foreground">Urgent items</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <ShoppingCart className="h-5 w-5 text-sustainability" />
                <div>
                  <p className="text-lg font-bold">{summary.days_covered}d</p>
                  <p className="text-xs text-muted-foreground">Days covered</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Log Purchase */}
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowPurchaseForm(!showPurchaseForm)}>
            <Plus className="h-4 w-4 mr-1" />
            Log Purchase
          </Button>
        </div>

        {showPurchaseForm && (
          <Card>
            <CardContent className="p-4">
              <div className="flex gap-3 flex-wrap">
                <Input placeholder="Item name" value={purchaseItem} onChange={(e) => setPurchaseItem(e.target.value)} className="w-40" />
                <Input placeholder="Quantity" type="number" value={purchaseQty} onChange={(e) => setPurchaseQty(e.target.value)} className="w-24" />
                <Input placeholder="Price" type="number" value={purchasePrice} onChange={(e) => setPurchasePrice(e.target.value)} className="w-24" />
                <Button size="sm" onClick={handleLogPurchase} disabled={purchaseMutation.isPending}>
                  {purchaseMutation.isPending ? "Saving…" : "Save"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Grocery Items by Category */}
        {categories.map((cat) => (
          <div key={cat}>
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">{cat}</h2>
            <div className="space-y-2">
              {displayItems.filter((g) => g.category === cat).map((item) => (
                <Card key={item.id} className={`transition-colors ${checked.has(item.id) ? "opacity-50" : ""}`}>
                  <CardContent className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3 cursor-pointer" onClick={() => toggle(item.id)}>
                      <div className={`h-5 w-5 rounded border flex items-center justify-center transition-colors ${checked.has(item.id) ? "bg-primary border-primary" : "border-border"
                        }`}>
                        {checked.has(item.id) && <Check className="h-3 w-3 text-primary-foreground" />}
                      </div>
                      <div>
                        <p className={`font-medium text-sm ${checked.has(item.id) ? "line-through" : ""}`}>{item.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {item.quantity} · {item.frequency}
                          {item.estimatedCost != null && <span> · ₹{item.estimatedCost.toFixed(0)}</span>}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => handleConsume(item.name)}>
                        Used
                      </Button>
                      <span className={`text-xs ${(item.urgency ?? 0) > 0.7 ? "text-destructive font-medium" : "text-muted-foreground"}`}>
                        {item.confidence}% {(item.urgency ?? 0) > 0.7 ? "🚨" : ""}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ))}
      </div>
    </AppLayout>
  );
}
