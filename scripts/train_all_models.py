"""
Unified ML Model Training Script
Trains all 4 ML models using synthetic data generated from mock databases
"""
import os
import sys
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force Mock Mode
os.environ["MOCK_MODE"] = "true"

from backend.ml.taste_predictor import DeepTastePredictor
from backend.ml.health_predictor import HealthLSTM
from backend.ml.meal_planner_rl import RLMealPlanner
from backend.ml.grocery_predictor import GroceryLSTM
from backend.ml.device_config import get_device
from backend.config import APIConfig

print("🤖 ML MODEL TRAINING SUITE")
print("=" * 70)

# Setup
MODELS_DIR = Path("backend/ml/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
device = get_device()
print(f"✅ Using device: {device}\n")

# ============================================================
# 1. TASTE PREDICTOR TRAINING
# ============================================================
def train_taste_predictor():
    print("\n[1/4] Training Taste Predictor (Transformer-based)...")
    print("-" * 70)
    
    model = DeepTastePredictor(input_dim=512, hidden_dim=256, device=device)
    optimizer = optim.Adam(model.parameters(), lr=1e-4)
    criterion = nn.MSELoss()
    
    # Generate synthetic training data
    print("  📊 Generating synthetic training data...")
    num_samples = 5000
    
    # Simulate user genomes and recipe profiles
    user_genomes = torch.randn(num_samples, 1, 512).to(device)
    recipe_profiles = torch.randn(num_samples, 1, 512).to(device)
    
    # Synthetic labels (hedonic scores 0-1)
    # Simulate correlation: similar vectors = higher scores
    similarity = torch.cosine_similarity(
        user_genomes.squeeze(1), 
        recipe_profiles.squeeze(1), 
        dim=1
    )
    labels = ((similarity + 1) / 2).unsqueeze(1)  # Normalize to 0-1
    labels = labels + torch.randn_like(labels) * 0.1  # Add noise
    labels = torch.clamp(labels, 0, 1)
    
    # Training loop
    print("  🏋️  Training...")
    model.train()
    batch_size = 64
    epochs = 20
    
    for epoch in range(epochs):
        total_loss = 0
        for i in range(0, num_samples, batch_size):
            batch_user = user_genomes[i:i+batch_size]
            batch_recipe = recipe_profiles[i:i+batch_size]
            batch_labels = labels[i:i+batch_size]
            
            optimizer.zero_grad()
            predictions, _ = model(batch_user, batch_recipe)
            loss = criterion(predictions, batch_labels)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / (num_samples // batch_size)
        if (epoch + 1) % 5 == 0:
            print(f"    Epoch {epoch+1}/{epochs} - Loss: {avg_loss:.4f}")
    
    # Save model
    save_path = MODELS_DIR / "taste_predictor.pth"
    torch.save(model.state_dict(), save_path)
    print(f"  ✅ Model saved to {save_path}\n")

# ============================================================
# 2. HEALTH PREDICTOR TRAINING
# ============================================================
def train_health_predictor():
    print("\n[2/4] Training Health Predictor (LSTM)...")
    print("-" * 70)
    
    model = HealthLSTM(input_dim=10, hidden_dim=128, num_layers=2, output_dim=3)
    model = model.to(device)
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()
    
    # Generate synthetic training data
    print("  📊 Generating synthetic health sequences...")
    num_samples = 3000
    seq_length = 30  # 30 days of history
    
    # Simulate health sequences
    sequences = torch.randn(num_samples, seq_length, 10).to(device)
    
    # Synthetic targets: [weight_change, hba1c, cholesterol]
    # Simulate realistic ranges
    targets = torch.zeros(num_samples, 3).to(device)
    targets[:, 0] = torch.randn(num_samples) * 2  # Weight change ±2kg
    targets[:, 1] = torch.rand(num_samples) * 2 + 5  # HbA1c 5-7%
    targets[:, 2] = torch.rand(num_samples) * 50 + 150  # Cholesterol 150-200
    
    # Training loop
    print("  🏋️  Training...")
    batch_size = 32
    epochs = 30
    
    for epoch in range(epochs):
        total_loss = 0
        for i in range(0, num_samples, batch_size):
            batch_seq = sequences[i:i+batch_size]
            batch_targets = targets[i:i+batch_size]
            
            optimizer.zero_grad()
            predictions = model(batch_seq)
            loss = criterion(predictions, batch_targets)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / (num_samples // batch_size)
        if (epoch + 1) % 10 == 0:
            print(f"    Epoch {epoch+1}/{epochs} - Loss: {avg_loss:.4f}")
    
    # Save model
    save_path = MODELS_DIR / "health_predictor.pth"
    torch.save(model.state_dict(), save_path)
    print(f"  ✅ Model saved to {save_path}\n")

# ============================================================
# 3. RL MEAL PLANNER TRAINING
# ============================================================
def train_rl_planner():
    print("\n[3/4] Training RL Meal Planner (PPO)...")
    print("-" * 70)
    
    planner = RLMealPlanner(state_dim=256, action_dim=100, lr=3e-4, device=device)
    
    # Generate synthetic episodes
    print("  📊 Generating synthetic RL episodes...")
    num_episodes = 500
    
    for episode in range(num_episodes):
        # Simulate episode
        state = torch.randn(256).to(device)
        available_recipes = list(range(100))
        
        for step in range(10):  # 10 steps per episode
            # Select action
            action, log_prob = planner.select_recipe(state, available_recipes)
            
            # Get value estimate
            with torch.no_grad():
                value = planner.value(state.unsqueeze(0)).item()
            
            # Simulate reward (random for synthetic data)
            reward = planner.calculate_reward(
                user_rating=np.random.rand(),
                adherence_score=np.random.choice([0, 1]),
                variety_score=np.random.rand(),
                health_score=np.random.rand()
            )
            
            # Store transition
            done = (step == 9)
            planner.store_transition(state, action, reward, log_prob, value, done)
            
            # Next state
            state = torch.randn(256).to(device)
        
        # Train every 5 episodes
        if (episode + 1) % 5 == 0:
            planner.train()
        
        if (episode + 1) % 100 == 0:
            print(f"    Episode {episode+1}/{num_episodes} completed")
    
    # Save model
    save_path = MODELS_DIR / "meal_planner_rl.pth"
    planner.save_model(str(save_path))
    print(f"  ✅ Model saved to {save_path}\n")

# ============================================================
# 4. GROCERY PREDICTOR TRAINING
# ============================================================
def train_grocery_predictor():
    print("\n[4/4] Training Grocery Predictor (LSTM)...")
    print("-" * 70)
    
    model = GroceryLSTM(num_items=500, embedding_dim=64, hidden_dim=128)
    model = model.to(device)
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    criterion_quantity = nn.MSELoss()
    criterion_days = nn.MSELoss()
    criterion_prob = nn.BCELoss()
    
    # Generate synthetic training data
    print("  📊 Generating synthetic grocery sequences...")
    num_samples = 2000
    seq_length = 10  # 10 purchase history
    
    # Simulate purchase sequences
    item_ids = torch.randint(0, 500, (num_samples, seq_length)).to(device)
    temporal_features = torch.rand(num_samples, seq_length, 5).to(device)
    
    # Synthetic targets
    target_quantity = torch.rand(num_samples, 1).to(device) * 5  # 0-5 units
    target_days = torch.rand(num_samples, 1).to(device) * 14  # 0-14 days
    target_prob = (torch.rand(num_samples, 1) > 0.5).float().to(device)
    
    # Training loop
    print("  🏋️  Training...")
    batch_size = 32
    epochs = 25
    
    for epoch in range(epochs):
        total_loss = 0
        for i in range(0, num_samples, batch_size):
            batch_ids = item_ids[i:i+batch_size]
            batch_temporal = temporal_features[i:i+batch_size]
            batch_qty = target_quantity[i:i+batch_size]
            batch_days = target_days[i:i+batch_size]
            batch_prob = target_prob[i:i+batch_size]
            
            optimizer.zero_grad()
            pred_qty, pred_days, pred_prob = model(batch_ids, batch_temporal)
            
            loss = (criterion_quantity(pred_qty, batch_qty) + 
                   criterion_days(pred_days, batch_days) + 
                   criterion_prob(pred_prob, batch_prob))
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / (num_samples // batch_size)
        if (epoch + 1) % 10 == 0:
            print(f"    Epoch {epoch+1}/{epochs} - Loss: {avg_loss:.4f}")
    
    # Save model
    save_path = MODELS_DIR / "grocery_predictor.pth"
    torch.save(model.state_dict(), save_path)
    print(f"  ✅ Model saved to {save_path}\n")

# ============================================================
# MAIN EXECUTION
# ============================================================
if __name__ == "__main__":
    try:
        print("Starting ML model training pipeline...\n")
        
        train_taste_predictor()
        train_health_predictor()
        train_rl_planner()
        train_grocery_predictor()
        
        print("=" * 70)
        print("✨ ALL MODELS TRAINED SUCCESSFULLY! ✨")
        print("=" * 70)
        print("\nTrained models:")
        for model_file in MODELS_DIR.glob("*.pth"):
            size_mb = model_file.stat().st_size / (1024 * 1024)
            print(f"  ✅ {model_file.name} ({size_mb:.2f} MB)")
        
        print("\n📝 Next Steps:")
        print("  1. Models are ready for inference")
        print("  2. Start backend: uvicorn backend.main:app --reload")
        print("  3. Test API endpoints at http://localhost:8000/docs")
        
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
