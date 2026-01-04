import subprocess
import time
import os
import sys

def run_app():
    print("Starting NutriFlavorOS Prototype...")
    
    # 1. Start Backend in background
    print("[1/2] Launching Backend (FastAPI)...")
    backend = subprocess.Popen(
        ["uvicorn", "backend.main:app", "--port", "8000", "--reload"],
        cwd=os.path.join(os.getcwd()),
        shell=True
    )
    
    # 2. Start Frontend in background
    print("[2/2] Launching Frontend (Vite)...")
    frontend_dir = os.path.join(os.getcwd(), "frontend")
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True
    )
    
    print("\n--- System Running ---")
    print("Backend: http://localhost:8000")
    print("Frontend: http://localhost:5173")
    print("Press Ctrl+C to stop both servers.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping servers...")
        backend.terminate()
        frontend.terminate()
        print("Stopped.")

if __name__ == "__main__":
    run_app()
