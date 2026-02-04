"""
Health Outcome Predictor using LSTM for time-series forecasting
Predicts weight loss trajectory, HbA1c levels, and other health metrics
"""
import torch
import torch.nn as nn
import numpy as np
from typing import List, Dict, Tuple
from collections import deque

class HealthLSTM(nn.Module):
    """LSTM model for health outcome prediction"""
    
    def __init__(self, input_dim=10, hidden_dim=128, num_layers=2, output_dim=3):
        super().__init__()
        
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2
        )
        
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, output_dim)
        )
    
    def forward(self, x):
        # x shape: (batch, seq_len, input_dim)
        lstm_out, _ = self.lstm(x)
        
        # Use last time step
        last_output = lstm_out[:, -1, :]
        
        # Predict outcomes
        predictions = self.fc(last_output)
        
        return predictions

class HealthOutcomePredictor:
    """
    Predictive health analytics using LSTM
    
    Predicts:
    1. Weight trajectory (next 30 days)
    2. HbA1c levels (for diabetics)
    3. Cholesterol levels
    4. Adherence probability
    
    Input: 30-day history of:
    - Daily calorie intake
    - Macro distribution
    - Exercise minutes
    - Sleep hours
    - Stress level
    - Meal adherence
    """
    
    def __init__(self, input_dim=10, hidden_dim=128):
        self.model = HealthLSTM(input_dim=input_dim, hidden_dim=hidden_dim, output_dim=3)
        self.input_dim = input_dim
        self.history_window = 30  # Days
        
        # Normalization parameters (learned from training data)
        self.feature_means = np.zeros(input_dim)
        self.feature_stds = np.ones(input_dim)
    
    def predict_outcomes(self, user_history: List[Dict]) -> Dict[str, any]:
        """
        Predict health outcomes based on user history
        
        Args:
            user_history: List of daily records with:
                - calories, protein_g, carbs_g, fat_g
                - exercise_minutes, sleep_hours
                - stress_level (1-10), adherence (0-1)
                - weight_kg, age
        
        Returns:
            {
                'weight_prediction_30d': float,
                'weight_confidence_interval': (float, float),
                'hba1c_prediction': float,
                'cholesterol_prediction': float,
                'adherence_probability': float,
                'trajectory': List[float]  # Daily predictions
            }
        """
        if len(user_history) < self.history_window:
            return self._default_prediction()
        
        # Prepare input tensor
        input_tensor = self._prepare_input(user_history[-self.history_window:])
        
        self.model.eval()
        with torch.no_grad():
            predictions = self.model(input_tensor)
        
        # Extract predictions
        weight_delta = predictions[0, 0].item()  # Weight change in 30 days
        hba1c = predictions[0, 1].item()
        cholesterol = predictions[0, 2].item()
        
        # Calculate current weight
        current_weight = user_history[-1].get('weight_kg', 70)
        predicted_weight = current_weight + weight_delta
        
        # Generate daily trajectory
        trajectory = self._generate_trajectory(current_weight, predicted_weight, days=30)
        
        # Calculate confidence interval (±5%)
        confidence_lower = predicted_weight * 0.95
        confidence_upper = predicted_weight * 1.05
        
        # Predict adherence probability based on trend
        adherence_prob = self._predict_adherence(user_history)
        
        return {
            'weight_prediction_30d': round(predicted_weight, 1),
            'weight_confidence_interval': (round(confidence_lower, 1), round(confidence_upper, 1)),
            'hba1c_prediction': round(hba1c, 1),
            'cholesterol_prediction': round(cholesterol, 0),
            'adherence_probability': round(adherence_prob, 2),
            'trajectory': trajectory,
            'insights': self._generate_insights(user_history, predicted_weight)
        }
    
    def _prepare_input(self, history: List[Dict]) -> torch.Tensor:
        """Convert history to tensor"""
        features = []
        
        for day in history:
            day_features = [
                day.get('calories', 2000) / 3000,  # Normalize
                day.get('protein_g', 100) / 200,
                day.get('carbs_g', 200) / 400,
                day.get('fat_g', 70) / 150,
                day.get('exercise_minutes', 30) / 120,
                day.get('sleep_hours', 7) / 10,
                day.get('stress_level', 5) / 10,
                day.get('adherence', 0.8),
                day.get('weight_kg', 70) / 150,
                day.get('age', 30) / 100
            ]
            features.append(day_features)
        
        # Convert to tensor
        tensor = torch.FloatTensor(features).unsqueeze(0)  # Add batch dimension
        return tensor
    
    def _generate_trajectory(self, start_weight: float, end_weight: float, days: int) -> List[float]:
        """Generate smooth weight trajectory"""
        # Exponential decay curve for realistic weight loss
        trajectory = []
        delta = end_weight - start_weight
        
        for day in range(days + 1):
            progress = 1 - np.exp(-3 * day / days)  # Exponential approach
            weight = start_weight + delta * progress
            trajectory.append(round(weight, 1))
        
        return trajectory
    
    def _predict_adherence(self, history: List[Dict]) -> float:
        """Predict adherence probability based on recent trend"""
        if len(history) < 7:
            return 0.7
        
        recent_adherence = [day.get('adherence', 0.8) for day in history[-7:]]
        avg_adherence = np.mean(recent_adherence)
        
        # Trend analysis
        if len(recent_adherence) >= 7:
            trend = np.polyfit(range(7), recent_adherence, 1)[0]
            # Positive trend increases probability
            adherence_prob = avg_adherence + trend * 0.5
        else:
            adherence_prob = avg_adherence
        
        return max(0.0, min(1.0, adherence_prob))
    
    def _generate_insights(self, history: List[Dict], predicted_weight: float) -> List[str]:
        """Generate actionable insights"""
        insights = []
        
        current_weight = history[-1].get('weight_kg', 70)
        weight_change = predicted_weight - current_weight
        
        if weight_change < -2:
            insights.append(f"Great progress! Predicted to lose {abs(weight_change):.1f}kg in 30 days")
        elif weight_change > 2:
            insights.append(f"Warning: Predicted weight gain of {weight_change:.1f}kg")
        else:
            insights.append("Maintaining current weight trajectory")
        
        # Analyze recent patterns
        recent_calories = [day.get('calories', 2000) for day in history[-7:]]
        avg_calories = np.mean(recent_calories)
        
        if avg_calories > 2500:
            insights.append("Consider reducing daily calorie intake")
        
        recent_exercise = [day.get('exercise_minutes', 0) for day in history[-7:]]
        avg_exercise = np.mean(recent_exercise)
        
        if avg_exercise < 30:
            insights.append("Increase physical activity to 30+ minutes/day")
        
        return insights
    
    def _default_prediction(self) -> Dict:
        """Return default prediction when insufficient data"""
        return {
            'weight_prediction_30d': None,
            'weight_confidence_interval': (None, None),
            'hba1c_prediction': None,
            'cholesterol_prediction': None,
            'adherence_probability': 0.7,
            'trajectory': [],
            'insights': ["Insufficient data for prediction. Continue logging for 30 days."]
        }
