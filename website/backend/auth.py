from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import models
from database import get_db
import os
import time
from collections import defaultdict

SECRET_KEY = os.getenv("SECRET_KEY", "smartev-caccs-secret-key-change-in-production-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ── Simple in-memory rate limiter ─────────────────────────────────────────────
_WINDOW_SECONDS = 900   # 15-minute rolling window
_MAX_FAILURES = 10      # block after 10 failed attempts

_failed_attempts: dict = defaultdict(list)


def _check_rate_limit(identifier: str) -> bool:
    """Return True if the identifier should be blocked."""
    now = time.time()
    recent = [t for t in _failed_attempts[identifier] if now - t < _WINDOW_SECONDS]
    _failed_attempts[identifier] = recent
    return len(recent) >= _MAX_FAILURES


def _record_failure(identifier: str) -> None:
    _failed_attempts[identifier].append(time.time())


def _clear_failures(identifier: str) -> None:
    _failed_attempts[identifier] = []


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


def login_with_rate_limit(
    email: str,
    password: str,
    client_ip: str,
    db: Session,
) -> models.User:
    """Authenticate user with rate-limit protection per IP."""
    if _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again in 15 minutes.",
        )
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    _clear_failures(client_ip)
    return user
