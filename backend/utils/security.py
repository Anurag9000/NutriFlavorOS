"""Password hashing, JWT creation, and authenticated-user dependencies."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db


ALGORITHM = "HS256"
TOKEN_ISSUER = os.getenv("JWT_ISSUER", "nutriflavos-api")
TOKEN_AUDIENCE = os.getenv("JWT_AUDIENCE", "nutriflavos-web")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
password_hasher = PasswordHasher()


def _get_secret_key() -> str:
    """Return the configured signing key, refusing insecure public fallbacks."""

    secret = os.getenv("SECRET_KEY")
    if not secret or len(secret) < 32:
        raise RuntimeError(
            "SECRET_KEY must be configured with at least 32 unpredictable characters"
        )
    return secret


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    if not hashed_password:
        return False
    try:
        return password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    return password_hasher.hash(password)


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    now = datetime.now(timezone.utc)
    expires = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        **data,
        "iat": now,
        "nbf": now,
        "exp": expires,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[ALGORITHM],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
        )
    except InvalidTokenError:
        return None


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> DBUser:
    payload = decode_access_token(token)
    subject = payload.get("sub") if payload else None
    if not isinstance(subject, str) or not subject:
        raise _credentials_exception()

    user = db.query(DBUser).filter(DBUser.id == subject).first()
    if user is None:
        raise _credentials_exception()
    return user


def require_self(user_id: str, current_user: DBUser) -> None:
    """Prevent broken object-level authorization on user-owned resources."""

    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
