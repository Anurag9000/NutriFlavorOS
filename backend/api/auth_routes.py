from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class UserLogin(BaseModel):
    email: str
    password: str

class UserSignup(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

@router.post("/login")
async def login(user_data: UserLogin):
    """
    Mock login - accepts any credentials
    """
    # In a real app, verify password hash
    return {
        "access_token": "mock_token_12345",
        "token_type": "bearer",
        "user": {
            "id": "usr_1",
            "email": user_data.email,
            "name": "Test User"
        }
    }

@router.post("/signup")
async def signup(user_data: UserSignup):
    """
    Mock signup - accepts any valid email/password
    """
    return {
        "access_token": "mock_token_new_user",
        "token_type": "bearer",
        "user": {
            "id": "usr_new",
            "email": user_data.email,
            "name": user_data.name or "New User"
        }
    }
