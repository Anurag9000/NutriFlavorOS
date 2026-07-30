from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.models import Gender, Goal, UserProfile
from backend.utils.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from backend.utils.user_profiles import apply_profile


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class UserSignup(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    name: Optional[str] = Field(default=None, max_length=120)
    age: int = Field(default=30, ge=18, le=120)
    weight_kg: float = Field(default=70.0, gt=0, le=500)
    height_cm: float = Field(default=170.0, gt=0, le=300)
    gender: Gender = Gender.OTHER
    activity_level: float = Field(default=1.4, ge=1.0, le=3.0)
    goal: Goal = Goal.MAINTENANCE


class AuthUser(BaseModel):
    id: str
    email: str
    name: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(Token):
    user: AuthUser


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise HTTPException(status_code=422, detail="A valid email address is required")
    return normalized


def _authenticate(db: Session, email: str, password: str) -> DBUser:
    normalized = _normalize_email(email)
    user = db.query(DBUser).filter(DBUser.id == normalized).first()
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _auth_response(user: DBUser) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(data={"sub": user.id}),
        user=AuthUser(id=user.id, email=user.id, name=user.name or "User"),
    )


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    user = _authenticate(db, form_data.username, form_data.password)
    return Token(access_token=create_access_token(data={"sub": user.id}))


@router.post("/login", response_model=AuthResponse)
def login(user_data: UserLogin, db: Session = Depends(get_db)) -> AuthResponse:
    return _auth_response(_authenticate(db, user_data.email, user_data.password))


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserSignup, db: Session = Depends(get_db)) -> AuthResponse:
    email = _normalize_email(user_data.email)
    if db.query(DBUser).filter(DBUser.id == email).first() is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    new_user = DBUser(
        id=email,
        name=(user_data.name or "New User").strip() or "New User",
        hashed_password=get_password_hash(user_data.password),
    )
    apply_profile(
        new_user,
        UserProfile(
            name=new_user.name,
            age=user_data.age,
            weight_kg=user_data.weight_kg,
            height_cm=user_data.height_cm,
            gender=user_data.gender,
            activity_level=user_data.activity_level,
            goal=user_data.goal,
        ),
    )

    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc

    return _auth_response(new_user)


@router.get("/me", response_model=AuthUser)
def me(current_user: DBUser = Depends(get_current_user)) -> AuthUser:
    return AuthUser(
        id=current_user.id,
        email=current_user.id,
        name=current_user.name or "User",
    )
