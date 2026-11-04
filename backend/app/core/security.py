"""
ProductMind AI — Security & Cryptography Utilities
Provides bcrypt password hashing, SHA-256 session token hashing,
and PyJWT-based access and refresh token lifecycle operations.
"""

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Dict, Any, Optional, Tuple
import uuid
import bcrypt
import jwt

from app.core.config import settings


class SecurityException(Exception):
    """Base exception for security and authentication failures."""
    pass


class InvalidTokenException(SecurityException):
    """Raised when token validation or signature fails."""
    pass


class ExpiredTokenException(SecurityException):
    """Raised when a token has expired."""
    pass


def hash_password(password: str) -> str:
    """Hashes a plain-text password securely using bcrypt."""
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain-text password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def hash_token(raw_token: str) -> str:
    """Computes a SHA-256 digest of a session refresh token for secure database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: str,
    session_id: str,
    session_family: str,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, int]:
    """
    Generates a cryptographically-signed short-lived JWT access token.
    Returns (token_string, expires_in_seconds).
    """
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire_dt = datetime.now(timezone.utc) + delta

    payload: Dict[str, Any] = {
        "jti": str(uuid.uuid4()),
        "sub": user_id,
        "session_id": session_id,
        "session_family": session_family,
        "type": "access",
        "exp": expire_dt,
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, int(delta.total_seconds())


def create_refresh_token(
    user_id: str,
    session_family: str,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, datetime]:
    """
    Generates a cryptographically-signed rotating JWT refresh token with unique jti.
    Returns (token_string, expire_datetime).
    """
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expire_dt = datetime.now(timezone.utc) + delta

    payload: Dict[str, Any] = {
        "jti": str(uuid.uuid4()),
        "sub": user_id,
        "session_family": session_family,
        "type": "refresh",
        "exp": expire_dt,
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expire_dt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT token's signature, format, and expiry.
    Raises ExpiredTokenException or InvalidTokenException on failure.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredTokenException("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenException("Invalid token signature or payload") from exc
