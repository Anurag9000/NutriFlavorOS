@echo off
echo Starting FoodScope Backend...
cd backend
title FoodScope Backend
call venv\Scripts\activate
uvicorn main:app --reload --port 8000
pause
