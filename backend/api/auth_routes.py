from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.utils.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from backend.utils.user_profiles import missing_profile_fields, profile_is_complete


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class UserSignup(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    name: Optional[str] = Field(default=None, max_length=120)


class AuthUser(BaseModel):
    id: str
    email: str
    name: str
    profile_complete: bool
    missing_profile_fields: list[str]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(Token):
    user: AuthUser


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if (
        "@" not in normalized
        or normalized.startswith("@")
        or normalized.endswith("@")
    ):
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


def _public_user(user: DBUser) -> AuthUser:
    return AuthUser(
        id=user.id,
        email=user.id,
        name=user.name or "User",
        profile_complete=profile_is_complete(user),
        missing_profile_fields=missing_profile_fields(user),
    )


def _auth_response(user: DBUser) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(data={"sub": user.id}),
        user=_public_user(user),
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
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        ) from exc
    return _auth_response(new_user)


@router.get("/me", response_model=AuthUser)
def me(current_user: DBUser = Depends(get_current_user)) -> AuthUser:
    return _public_user(current_user)
