"""
ML-Powered Grocery Prediction System
Predicts what user will buy, when, and how much using time-series forecasting
"""
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json

class GroceryLSTM(nn.Module):
    """
    LSTM model for time-series grocery consumption forecasting
    Predicts: What items, when to buy, and quantity needed
    """
    
    def __init__(self, num_items=500, embedding_dim=64, hidden_dim=128):
        super().__init__()
        
        self.num_items = num_items
        self.item_embedding = nn.Embedding(num_items, embedding_dim)
        
        # LSTM for consumption pattern learning
        self.lstm = nn.LSTM(
            input_size=embedding_dim + 5,  # embedding + temporal features
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
            dropout=0.2
        )
        
        # Prediction heads
        self.quantity_predictor = nn.Linear(hidden_dim, 1)  # How much
        self.days_until_predictor = nn.Linear(hidden_dim, 1)  # When
        self.purchase_probability = nn.Linear(hidden_dim, 1)  # Will buy?
        
        self.sigmoid = nn.Sigmoid()
        self.relu = nn.ReLU()
        
    def forward(self, item_ids, temporal_features):
        """
        Args:
            item_ids: (batch, seq_len) - Item IDs in purchase history
            temporal_features: (batch, seq_len, 5) - [day_of_week, week_of_month, quantity, days_since_last, price]
        
        Returns:
            quantity: Predicted quantity needed
            days_until: Days until next purchase
            probability: Probability of purchasing
        """
        # Embed items
        item_embeds = self.item_embedding(item_ids)  # (batch, seq_len, embedding_dim)
        
        # Concatenate with temporal features
        lstm_input = torch.cat([item_embeds, temporal_features], dim=-1)
        
        # LSTM forward
        lstm_out, _ = self.lstm(lstm_input)
        last_hidden = lstm_out[:, -1, :]  # Use last time step
        
        # Predictions
        quantity = self.relu(self.quantity_predictor(last_hidden))
        days_until = self.relu(self.days_until_predictor(last_hidden))
        probability = self.sigmoid(self.purchase_probability(last_hidden))
        
        return quantity, days_until, probability


class GroceryPredictor:
    """
    Intelligent grocery prediction system with online learning
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.model = GroceryLSTM()
        self.item_to_id = {}
        self.id_to_item = {}
        self.next_id = 0
        
        # User's purchase history
        self.purchase_history = []  # List of {item, quantity, date, price}
        self.current_inventory = {}  # {item: quantity}
        self.consumption_rates = {}  # {item: units_per_day}
        
        # Load model if exists
        self._load_model()
        
    def update_inventory(self, item: str, quantity: float, action: str = "add"):
        """
        Update current inventory
        
        Args:
            item: Item name
            quantity: Quantity to add/remove
            action: 'add' (purchased) or 'consume' (used)
        """
        if item not in self.current_inventory:
            self.current_inventory[item] = 0.0
        
        if action == "add":
            self.current_inventory[item] += quantity
        elif action == "consume":
            self.current_inventory[item] = max(0, self.current_inventory[item] - quantity)
        
        # Update consumption rate
        self._update_consumption_rate(item, quantity, action)
        
    def log_purchase(self, items: List[Dict[str, any]]):
        """
        Log a grocery purchase
        
        Args:
            items: List of {item: str, quantity: float, price: float}
        """
        purchase_date = datetime.now()
        
        for item_data in items:
            item = item_data["item"]
            quantity = item_data["quantity"]
            price = item_data.get("price", 0.0)
            
            # Add to history
            self.purchase_history.append({
                "item": item,
                "quantity": quantity,
                "date": purchase_date,
                "price": price
            })
            
            # Update inventory
            self.update_inventory(item, quantity, action="add")
            
            # Assign ID if new item
            if item not in self.item_to_id:
                self.item_to_id[item] = self.next_id
                self.id_to_item[self.next_id] = item
                self.next_id += 1
        
        # Trigger online learning update
        self._online_update()
        
    def predict_next_purchase(self, item: str) -> Dict[str, float]:
        """
        Predict when and how much of an item user will need
        
        Args:
            item: Item name
        
        Returns:
            {
                "days_until_purchase": float,
                "quantity_needed": float,
                "probability": float,
                "current_stock": float,
                "consumption_rate": float
            }
        """
        if item not in self.item_to_id:
            return {
                "days_until_purchase": 7.0,  # Default weekly
                "quantity_needed": 1.0,
                "probability": 0.5,
                "current_stock": 0.0,
                "consumption_rate": 0.0
            }
        
        # Prepare input sequence
        item_history = self._get_item_history(item)
        
        if len(item_history) < 2:
            # Not enough data, use heuristics
            return self._heuristic_prediction(item)
        
        # Convert to model input
        item_ids, temporal_features = self._prepare_model_input(item_history)
        
        # Model prediction
        self.model.eval()
        with torch.no_grad():
            quantity, days_until, probability = self.model(item_ids, temporal_features)
        
        return {
            "days_until_purchase": float(days_until.item()),
            "quantity_needed": float(quantity.item()),
            "probability": float(probability.item()),
            "current_stock": self.current_inventory.get(item, 0.0),
            "consumption_rate": self.consumption_rates.get(item, 0.0)
        }
    
    def generate_shopping_list(self, days_ahead: int = 7) -> List[Dict]:
        """
        Generate optimized shopping list for next N days
        
        Args:
            days_ahead: How many days to plan for
        
        Returns:
            List of {item, quantity, urgency, estimated_cost}
        """
        shopping_list = []
        
        for item in self.item_to_id.keys():
            prediction = self.predict_next_purchase(item)
            
            current_stock = prediction["current_stock"]
            consumption_rate = prediction["consumption_rate"]
            
            # Calculate if we'll run out in next N days
            days_until_empty = current_stock / consumption_rate if consumption_rate > 0 else 999
            
            if days_until_empty <= days_ahead:
                # Need to buy this item
                quantity_needed = consumption_rate * days_ahead - current_stock
                quantity_needed = max(0, quantity_needed)
                
                if quantity_needed > 0:
                    # Calculate urgency (0-1, higher = more urgent)
                    urgency = 1.0 - (days_until_empty / days_ahead)
                    urgency = max(0, min(1, urgency))
                    
                    # Estimate cost based on historical prices
                    avg_price = self._get_average_price(item)
                    
                    shopping_list.append({
                        "item": item,
                        "quantity": round(quantity_needed, 2),
                        "urgency": round(urgency, 2),
                        "estimated_cost": round(avg_price * quantity_needed, 2),
                        "days_until_empty": round(days_until_empty, 1),
                        "current_stock": round(current_stock, 2)
                    })
        
        # Sort by urgency (most urgent first)
        shopping_list.sort(key=lambda x: x["urgency"], reverse=True)
        
        return shopping_list
    
    def forecast_consumption(self, item: str, days: int = 30) -> List[float]:
        """
        Forecast consumption over next N days
        
        Args:
            item: Item name
            days: Number of days to forecast
        
        Returns:
            List of predicted daily consumption
        """
        consumption_rate = self.consumption_rates.get(item, 0.0)
        
        # Simple linear forecast (can be enhanced with seasonality)
        forecast = [consumption_rate] * days
        
        return forecast
    
    def _update_consumption_rate(self, item: str, quantity: float, action: str):
        """Update estimated consumption rate for item"""
        if action != "consume":
            return
        
        if item not in self.consumption_rates:
            self.consumption_rates[item] = quantity
        else:
            # Exponential moving average
            alpha = 0.3
            self.consumption_rates[item] = (
                alpha * quantity + (1 - alpha) * self.consumption_rates[item]
            )
    
    def _get_item_history(self, item: str) -> List[Dict]:
        """Get purchase history for specific item"""
        return [p for p in self.purchase_history if p["item"] == item]
    
    def _prepare_model_input(self, item_history: List[Dict]) -> Tuple[torch.Tensor, torch.Tensor]:
        """Convert item history to model input tensors"""
        item_id = self.item_to_id[item_history[0]["item"]]
        
        # Use last 10 purchases
        history = item_history[-10:]
        
        item_ids = []
        temporal_features = []
        
        for i, purchase in enumerate(history):
            item_ids.append(item_id)
            
            # Temporal features: [day_of_week, week_of_month, quantity, days_since_last, price]
            date = purchase["date"]
            day_of_week = date.weekday() / 7.0  # Normalize
            week_of_month = (date.day - 1) // 7 / 4.0
            quantity = purchase["quantity"]
            
            if i > 0:
                days_since_last = (date - history[i-1]["date"]).days
            else:
                days_since_last = 7.0  # Default
            
            price = purchase.get("price", 0.0)
            
            temporal_features.append([
                day_of_week,
                week_of_month,
                quantity,
                days_since_last / 30.0,  # Normalize
                price / 100.0  # Normalize
            ])
        
        # Pad if needed
        while len(item_ids) < 10:
            item_ids.insert(0, item_id)
            temporal_features.insert(0, [0, 0, 0, 0, 0])
        
        item_ids_tensor = torch.LongTensor([item_ids])
        temporal_tensor = torch.FloatTensor([temporal_features])
        
        return item_ids_tensor, temporal_tensor
    
    def _heuristic_prediction(self, item: str) -> Dict[str, float]:
        """Fallback heuristic when not enough data"""
        consumption_rate = self.consumption_rates.get(item, 0.1)
        current_stock = self.current_inventory.get(item, 0.0)
        
        days_until = current_stock / consumption_rate if consumption_rate > 0 else 7.0
        
        return {
            "days_until_purchase": min(days_until, 14.0),
            "quantity_needed": consumption_rate * 7,  # Weekly supply
            "probability": 0.7,
            "current_stock": current_stock,
            "consumption_rate": consumption_rate
        }
    
    def _get_average_price(self, item: str) -> float:
        """Get average historical price for item"""
        item_purchases = self._get_item_history(item)
        if not item_purchases:
            return 5.0  # Default price
        
        prices = [p.get("price", 0) for p in item_purchases if p.get("price", 0) > 0]
        return np.mean(prices) if prices else 5.0
    
    def _online_update(self):
        """Trigger online learning update"""
        # This would be called by OnlineLearningManager
        # For now, just save the state
        self._save_model()
    
    def _save_model(self):
        """Save model and user data"""
        save_path = f"backend/ml/models/grocery_predictor_{self.user_id}.pth"
        torch.save({
            "model_state": self.model.state_dict(),
            "item_to_id": self.item_to_id,
            "id_to_item": self.id_to_item,
            "next_id": self.next_id,
            "purchase_history": self.purchase_history,
            "current_inventory": self.current_inventory,
            "consumption_rates": self.consumption_rates
        }, save_path)
    
    def _load_model(self):
        """Load model and user data"""
        import os
        save_path = f"backend/ml/models/grocery_predictor_{self.user_id}.pth"
        
        if os.path.exists(save_path):
            checkpoint = torch.load(save_path)
            self.model.load_state_dict(checkpoint["model_state"])
            self.item_to_id = checkpoint["item_to_id"]
            self.id_to_item = checkpoint["id_to_item"]
            self.next_id = checkpoint["next_id"]
            self.purchase_history = checkpoint["purchase_history"]
            self.current_inventory = checkpoint["current_inventory"]
            self.consumption_rates = checkpoint["consumption_rates"]
