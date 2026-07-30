"""Security primitives.

Password hashing intentionally reproduces Django's own
``pbkdf2_sha256`` encoded format (``pbkdf2_sha256$<iterations>$<salt>$<hash>``)
so that user rows in ``auth_user`` remain fully interoperable with the
Django application that owns that table: a user created via this API
can log into Django admin (if ever given staff access) and a user
created via Django can log in through this API, without needing a
second copy of passlib/Django on this side.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings

settings = get_settings()

_DJANGO_ALGORITHM = "pbkdf2_sha256"


# ---------------------------------------------------------------------------
# Django-compatible password hashing
# ---------------------------------------------------------------------------

def hash_password(raw_password: str, *, iterations: int | None = None) -> str:
    iterations = iterations or settings.PBKDF2_ITERATIONS
    salt = secrets.token_hex(6)  # 12 hex chars, matches Django's salt length/charset needs
    derived = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), iterations)
    b64_hash = base64.b64encode(derived).decode("ascii").strip()
    return f"{_DJANGO_ALGORITHM}${iterations}${salt}${b64_hash}"


def verify_password(raw_password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_str, salt, b64_hash = encoded.split("$", 3)
    except ValueError:
        return False

    if algorithm != _DJANGO_ALGORITHM:
        # Any account with a hash from a different Django hasher (rare,
        # legacy) cannot be verified here. Fail closed.
        return False

    try:
        iterations = int(iterations_str)
    except ValueError:
        return False

    derived = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), iterations)
    computed = base64.b64encode(derived).decode("ascii").strip()
    return hmac.compare_digest(computed, b64_hash)


PASSWORD_MIN_LENGTH = 8


def validate_password_strength(password: str) -> str | None:
    """Return an error message if the password is too weak, else None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
    if not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter."
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one digit."
    if not any(c in string.punctuation for c in password):
        return "Password must contain at least one special character."
    return None


# ---------------------------------------------------------------------------
# JWT access tokens
# ---------------------------------------------------------------------------

def create_access_token(*, user_id: int, username: str, is_staff: bool = False) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "is_staff": is_staff,
        "type": "access",
        "iat": now,
        "exp": expires_at,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError subclasses on invalid/expired tokens."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


# ---------------------------------------------------------------------------
# Opaque refresh tokens (stored server-side only as a hash)
# ---------------------------------------------------------------------------

def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# OTP codes (email verification / password reset)
# ---------------------------------------------------------------------------

def generate_otp() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(settings.OTP_LENGTH))


def hash_otp(otp: str) -> str:
    # HMAC-keyed (not plain SHA-256): a 6-digit OTP only has 1M possible
    # values, so an unkeyed hash would let anyone who reads the email_otp
    # table brute-force the code in well under a second. Keying with
    # SECRET_KEY means that's no longer a pure offline dictionary attack.
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), otp.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_otp(otp: str, otp_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(otp), otp_hash)
