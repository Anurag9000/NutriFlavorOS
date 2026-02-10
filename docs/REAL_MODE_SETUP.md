# Real Mode Setup Guide

## Overview
FoodScope defaults to **Mock Mode** (offline) for development. This guide explains how to switch to **Real Mode** to connect with live external APIs (RecipeDB, FlavorDB, etc.).

## Prerequisites
You need valid API keys for the CosyLab services.
- **RecipeDB**: [Get Key](https://cosylab.iiitd.edu.in/recipedb/)
- **FlavorDB**: [Get Key](https://cosylab.iiitd.edu.in/flavordb/)
- **DietRx**: [Get Key](https://cosylab.iiitd.edu.in/dietrxdb/)
- **SustainableFoodDB**: [Get Key](https://cosylab.iiitd.edu.in/sustainablefooddb/)

## Configuration Steps

### 1. Create Environment File
Copy the example configuration file to a new `.env` file (which is git-ignored for security).

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux/Mac
cp .env.example .env
```

### 2. Configure API Keys
Open `.env` in your text editor and update the following lines:

1.  **Disable Mock Mode**:
    ```ini
    MOCK_MODE=false
    ```

2.  **Add Your Keys**:
    Replace the placeholder text with your actual API keys.
    ```ini
    RECIPEDB_API_KEY=your_actual_key_here
    FLAVORDB_API_KEY=your_actual_key_here
    SUSTAINABLEFOODDB_API_KEY=your_actual_key_here
    DIETRXDB_API_KEY=your_actual_key_here
    ```

### 3. Restart the Backend
The configuration is loaded at startup. You must restart the server for changes to take effect.

```bash
# If running via uvicorn directly
uvicorn backend.main:app --reload

# If using the start script
./start_backend.bat
```

## Verification

To verify you are in Real Mode:

1.  Check the server logs during startup. You should **NOT** see "Mock Data Loaded" messages.
2.  Make a search request (e.g., search for "Chicken").
    - If it returns results different from the fixed mock dataset (60 recipes), you are connected!
    - If you see a network error or "Invalid API Key", check your `.env` file.

## Troubleshooting

**Q: The app crashes on startup.**
A: Ensure strict network access rules aren't blocking the connection to `cosylab.iiitd.edu.in`.

**Q: I get "API Key Missing" errors.**
A: The backend will fallback to Mock Mode or raise an error if `MOCK_MODE=false` but keys are empty. Double-check variable names in `.env`.

**Q: Can I mix mock and real APIs?**
A: Currently, the global `MOCK_MODE` toggle applies to all services. To mix them, you would need to modify `backend/config.py` logic directly.
