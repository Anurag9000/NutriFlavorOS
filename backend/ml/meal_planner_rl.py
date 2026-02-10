"""
Reinforcement Learning Meal Planner using PPO (Proximal Policy Optimization)
Learns optimal meal sequencing to maximize long-term user adherence
"""
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Categorical
import numpy as np
from typing import List, Dict, Tuple
from collections import deque
from .device_config import get_device, to_device

class PolicyNetwork(nn.Module):
    """Actor network for meal selection"""
    
    def __init__(self, state_dim=256, action_dim=100, hidden_dim=512):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, action_dim),
            nn.Softmax(dim=-1)
        )
    
    def forward(self, state):
        return self.network(state)

class ValueNetwork(nn.Module):
    """Critic network for state value estimation"""
    
    def __init__(self, state_dim=256, hidden_dim=512):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)
        )
    
    def forward(self, state):
        return self.network(state)

class RLMealPlanner:
    """
    Reinforcement Learning agent for optimal meal planning
    
    State: User profile + meal history + pantry inventory + time context
    Action: Select recipe for next meal slot
    Reward: User rating + adherence score + variety bonus
    
    Uses PPO (Proximal Policy Optimization) for stable training
    """
    
    def __init__(self, state_dim=256, action_dim=100, lr=3e-4, device=None):
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Set device
        self.device = device if device is not None else get_device()
        
        # Networks
        self.policy = PolicyNetwork(state_dim, action_dim).to(self.device)
        self.value = ValueNetwork(state_dim).to(self.device)
        
        # Optimizers
        self.policy_optimizer = optim.Adam(self.policy.parameters(), lr=lr)
        self.value_optimizer = optim.Adam(self.value.parameters(), lr=lr)
        
        # PPO hyperparameters
        self.gamma = 0.99  # Discount factor
        self.epsilon = 0.2  # Clipping parameter
        self.epochs = 10  # Training epochs per update
        
        # Experience buffer
        self.states = []
        self.actions = []
        self.rewards = []
        self.log_probs = []
        self.values = []
        self.dones = []
    
    def encode_state(self, user_profile: Dict, meal_history: List, 
                    pantry: List[str], time_context: Dict) -> torch.Tensor:
        """
        Encode current state into fixed-size vector
        
        Args:
            user_profile: User biometrics and preferences
            meal_history: Recent meals (last 7 days)
            pantry: Available ingredients
            time_context: {day_of_week, meal_slot, season}
        
        Returns:
            state_tensor: (state_dim,) tensor
        """
        state_vector = np.zeros(self.state_dim)
        
        # User profile features (0-50)
        state_vector[0] = user_profile.get('age', 30) / 100
        state_vector[1] = user_profile.get('weight_kg', 70) / 150
        state_vector[2] = user_profile.get('height_cm', 170) / 200
        state_vector[3] = user_profile.get('activity_level', 1.5) / 2.0
        state_vector[4] = {'weight_loss': 0, 'maintenance': 0.5, 'muscle_gain': 1.0}.get(
            user_profile.get('goal', 'maintenance'), 0.5
        )
        
        # Meal history features (50-150)
        # Encode recent ingredient usage
        recent_ingredients = set()
        for meal in meal_history[-21:]:  # Last week (3 meals/day * 7 days)
            if isinstance(meal, dict):
                recent_ingredients.update(meal.get('ingredients', []))
        
        for i, ing in enumerate(list(recent_ingredients)[:50]):
            idx = 50 + (hash(ing) % 50)
            state_vector[idx] = 1.0
        
        # Pantry features (150-200)
        for i, ing in enumerate(pantry[:50]):
            idx = 150 + (hash(ing) % 50)
            state_vector[idx] = 1.0
        
        # Time context (200-210)
        state_vector[200] = time_context.get('day_of_week', 0) / 7.0
        state_vector[201] = {'breakfast': 0, 'lunch': 0.5, 'dinner': 1.0}.get(
            time_context.get('meal_slot', 'lunch'), 0.5
        )
        state_vector[202] = time_context.get('season', 0) / 4.0
        
        return torch.FloatTensor(state_vector)
    
    def select_recipe(self, state: torch.Tensor, available_recipes: List[int]) -> Tuple[int, float]:
        """
        Select recipe using current policy
        
        Args:
            state: Current state tensor
            available_recipes: List of available recipe indices
        
        Returns:
            (selected_recipe_idx, log_prob)
        """
        # Move state to device
        state = state.to(self.device)
        
        with torch.no_grad():
            action_probs = self.policy(state)
        
        # Mask unavailable recipes
        mask = torch.zeros(self.action_dim, device=self.device)
        mask[available_recipes] = 1.0
        masked_probs = action_probs * mask
        masked_probs = masked_probs / masked_probs.sum()
        
        # Sample action
        dist = Categorical(masked_probs)
        action = dist.sample()
        log_prob = dist.log_prob(action)
        
        return action.item(), log_prob.item()
    
    def store_transition(self, state, action, reward, log_prob, value, done):
        """Store experience for training"""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.log_probs.append(log_prob)
        self.values.append(value)
        self.dones.append(done)
    
    def calculate_reward(self, user_rating: float, adherence_score: float, 
                        variety_score: float, health_score: float) -> float:
        """
        Calculate reward signal
        
        Args:
            user_rating: User's rating of the meal (0-1)
            adherence_score: Whether user ate the meal (0 or 1)
            variety_score: Variety score (0-1)
            health_score: Health match score (0-1)
        
        Returns:
            total_reward: Weighted sum of components
        """
        # Weighted reward
        reward = (
            user_rating * 0.4 +
            adherence_score * 0.3 +
            variety_score * 0.2 +
            health_score * 0.1
        )
        
        return reward
    
    def train(self):
        """Train policy and value networks using PPO"""
        if len(self.states) < 32:  # Minimum batch size
            return
        
        # Convert lists to tensors and move to device
        states = torch.stack(self.states).to(self.device)
        actions = torch.LongTensor(self.actions).to(self.device)
        old_log_probs = torch.FloatTensor(self.log_probs).to(self.device)
        rewards = torch.FloatTensor(self.rewards).to(self.device)
        dones = torch.FloatTensor(self.dones).to(self.device)
        
        # Stack values and move to device
        values = torch.stack(self.values).to(self.device)
        
        # Calculate returns and advantages
        returns = self._calculate_returns(rewards, dones).to(self.device)
        advantages = returns - values.squeeze()
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO update
        for _ in range(self.epochs):
            # Get current policy predictions
            action_probs = self.policy(states)
            dist = Categorical(action_probs)
            new_log_probs = dist.log_prob(actions)
            entropy = dist.entropy().mean()
            
            # Calculate ratio
            ratio = torch.exp(new_log_probs - old_log_probs)
            
            # Clipped surrogate objective
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.epsilon, 1 + self.epsilon) * advantages
            policy_loss = -torch.min(surr1, surr2).mean() - 0.01 * entropy
            
            # Update policy
            self.policy_optimizer.zero_grad()
            policy_loss.backward()
            self.policy_optimizer.step()
            
            # Value loss
            values = self.value(states).squeeze()
            value_loss = nn.MSELoss()(values, returns)
            
            # Update value
            self.value_optimizer.zero_grad()
            value_loss.backward()
            self.value_optimizer.step()
        
        # Clear buffer
        self.states = []
        self.actions = []
        self.rewards = []
        self.log_probs = []
        self.values = []
        self.dones = []
    
    def _calculate_returns(self, rewards, dones):
        """Calculate discounted returns"""
        returns = []
        R = 0
        
        for reward, done in zip(reversed(rewards), reversed(dones)):
            if done:
                R = 0
            R = reward + self.gamma * R
            returns.insert(0, R)
        
        return torch.FloatTensor(returns)
    
    def save_model(self, path: str):
        """Save model weights"""
        torch.save({
            'policy': self.policy.state_dict(),
            'value': self.value.state_dict()
        }, path)
    
    def load_model(self, path: str):
        """Load model weights"""
        checkpoint = torch.load(path, map_location=self.device)
        self.policy.load_state_dict(checkpoint['policy'])
        self.value.load_state_dict(checkpoint['value'])
        self.policy.to(self.device)
        self.value.to(self.device)
