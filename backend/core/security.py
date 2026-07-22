"""
Security and JWT utilities - password hashing and token management.
Supports JWT authentication, secure bcrypt hashing, and refresh token cycles.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Union, Dict, Optional
import threading
import time
from collections import defaultdict
import jwt
import bcrypt
from core.config import get_settings

settings = get_settings()

# JWT configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Brute-force login protection
LOGIN_ATTEMPT_WINDOW_SECONDS = 900   # 15 minutes
LOGIN_ATTEMPT_MAX = 5
LOGIN_LOCKOUT_SECONDS = 900          # 15 minutes


def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against its bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(
    subject: Union[str, Any],
    role: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Generate a short-lived access JWT token.
    
    Args:
        subject: The subject of the token (typically user UUID or email)
        role: The security role of the user (Admin, Staff, User)
        expires_delta: Optional custom expiration time delta
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "type": "access"
    }
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


import uuid as _uuid

def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Generate a long-lived refresh JWT token.
    
    Args:
        subject: The subject of the token (typically user UUID or email)
        expires_delta: Optional custom expiration time delta
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "jti": str(_uuid.uuid4())
    }
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    
    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token signature is invalid or parsing fails.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError as e:
        raise e
    except jwt.InvalidTokenError as e:
        raise e


class LoginAttemptLimiter:
    """
    In-memory brute-force guard for the login endpoint.

    Tracks failed login attempts per email; once an email accumulates
    ``LOGIN_ATTEMPT_MAX`` failures within ``LOGIN_ATTEMPT_WINDOW_SECONDS``,
    further attempts for that email are rejected for ``LOGIN_LOCKOUT_SECONDS``
    regardless of whether the password supplied is actually correct.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures: Dict[str, list] = defaultdict(list)
        self._locked_until: Dict[str, float] = {}

    def check_locked(self, email: str) -> Optional[int]:
        """Return remaining lockout seconds if *email* is locked out, else None."""
        with self._lock:
            locked_until = self._locked_until.get(email)
            if locked_until is None:
                return None
            remaining = int(locked_until - time.time())
            if remaining <= 0:
                self._locked_until.pop(email, None)
                self._failures.pop(email, None)
                return None
            return remaining

    def record_failure(self, email: str) -> None:
        """Record a failed login attempt, locking the account if over threshold."""
        with self._lock:
            now = time.time()
            window_start = now - LOGIN_ATTEMPT_WINDOW_SECONDS
            attempts = [t for t in self._failures[email] if t >= window_start]
            attempts.append(now)
            self._failures[email] = attempts
            if len(attempts) >= LOGIN_ATTEMPT_MAX:
                self._locked_until[email] = now + LOGIN_LOCKOUT_SECONDS

    def record_success(self, email: str) -> None:
        """Clear any failure history for *email* after a successful login."""
        with self._lock:
            self._failures.pop(email, None)
            self._locked_until.pop(email, None)


_login_limiter: Optional[LoginAttemptLimiter] = None
_login_limiter_lock = threading.Lock()


def get_login_attempt_limiter() -> LoginAttemptLimiter:
    """Return the process-wide singleton :class:`LoginAttemptLimiter`."""
    global _login_limiter
    if _login_limiter is None:
        with _login_limiter_lock:
            if _login_limiter is None:
                _login_limiter = LoginAttemptLimiter()
    return _login_limiter

