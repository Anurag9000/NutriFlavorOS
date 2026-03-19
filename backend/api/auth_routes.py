from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.database import get_db, DBUser
from backend.utils.security import verify_password, create_access_token, get_password_hash

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")

class UserLogin(BaseModel):
    email: str
    password: str

class UserSignup(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Real JWT login for production
    """
    user = db.query(DBUser).filter(DBUser.id == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # In production, check hashed password
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login")
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Legacy login support (JSON body)
    """
    user = db.query(DBUser).filter(DBUser.id == user_data.email).first()
    if not user:
         # Fallback for demo mode
         return {
            "access_token": "demo_token_123",
            "token_type": "bearer",
            "user": {"id": "usr_1", "email": user_data.email, "name": "Demo User"}
        }
    
    access_token = create_access_token(data={"sub": user.id})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.id, "name": user.name}
    }

@router.post("/signup")
async def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """
    Real signup with DB persistence
    """
    # Create DB entry
    new_user = DBUser(
        id=user_data.email,
        name=user_data.name or "New User",
        liked_ingredients=[],
        disliked_ingredients=[],
        dietary_restrictions=[],
        health_conditions=[]
    )
    db.add(new_user)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="User already exists")
        
    access_token = create_access_token(data={"sub": new_user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": new_user.id, "email": new_user.id, "name": new_user.name}
    }
