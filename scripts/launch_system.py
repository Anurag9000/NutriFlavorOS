"""
Master Launch Script for NutriFlavorOS
Orchestrates: DB checks, Model training verification, Backend startup, Frontend launch
"""
import os
import sys
import subprocess
import time
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print_success(f"{description}: Found")
        return True
    else:
        print_warning(f"{description}: Missing (will use fallback)")
        return False

def verify_databases():
    """Verify all data files exist"""
    print_header("DATABASE VERIFICATION")
    
    data_dir = Path("backend/data")
    required_files = {
        "recipes.json": "Recipe Database",
        "flavor_db.json": "Flavor Database",
        "mock_data.sql": "SQL Mock Data"
    }
    
    all_exist = True
    for filename, description in required_files.items():
        filepath = data_dir / filename
        exists = check_file_exists(filepath, description)
        all_exist = all_exist and exists
    
    return all_exist

def verify_ml_models():
    """Verify ML model weights exist"""
    print_header("ML MODEL VERIFICATION")
    
    weights_dir = Path("backend/ml/weights")
    models = {
        "taste_predictor.pth": "Taste Predictor (Transformer)",
        "rl_planner.pth": "RL Meal Planner (PPO)",
        "grocery_predictor.pth": "Grocery Predictor (LSTM)",
        "health_predictor.pth": "Health Predictor (LSTM)"
    }
    
    trained_count = 0
    for filename, description in models.items():
        filepath = weights_dir / filename
        if check_file_exists(filepath, description):
            trained_count += 1
    
    print(f"\n{Colors.BLUE}Trained Models: {trained_count}/{len(models)}{Colors.END}")
    
    if trained_count < len(models):
        print_warning("Some models missing. Run: python scripts/train_all_models.py")
        return False
    return True

def start_backend():
    """Start FastAPI backend server"""
    print_header("STARTING BACKEND SERVER")
    
    print("Starting FastAPI on http://127.0.0.1:8000...")
    print("Press Ctrl+C to stop\n")
    
    try:
        # Start backend in foreground (user can Ctrl+C to stop)
        subprocess.run(
            ["python", "-m", "backend.main"],
            cwd=os.getcwd(),
            check=True
        )
    except KeyboardInterrupt:
        print("\n\nBackend stopped by user.")
    except Exception as e:
        print_error(f"Backend failed to start: {e}")
        return False
    
    return True

def open_frontend():
    """Open frontend in browser"""
    print_header("FRONTEND LAUNCH")
    
    frontend_dir = Path("frontend")
    
    if not frontend_dir.exists():
        print_warning("Frontend directory not found. Skipping.")
        return False
    
    print("To start frontend:")
    print(f"  1. cd {frontend_dir}")
    print("  2. npm install (if first time)")
    print("  3. npm run dev")
    print("\nBackend is running. Open another terminal for frontend.")
    
    return True

def main():
    print_header("NUTRIFLAVOR OS - SYSTEM LAUNCHER")
    
    # Step 1: Verify Databases
    db_ok = verify_databases()
    
    # Step 2: Verify ML Models
    models_ok = verify_ml_models()
    
    # Step 3: System Status
    print_header("SYSTEM STATUS")
    if db_ok and models_ok:
        print_success("All systems ready!")
    elif db_ok:
        print_warning("Databases OK, but models need training")
    else:
        print_warning("Some components missing")
    
    # Step 4: Launch Backend
    print("\n" + "="*60)
    user_input = input("Start backend server? (y/n): ")
    
    if user_input.lower() == 'y':
        open_frontend()
        start_backend()
    else:
        print("\nLaunch cancelled. To start manually:")
        print("  Backend: python -m backend.main")
        print("  Frontend: cd frontend && npm run dev")

if __name__ == "__main__":
    main()
