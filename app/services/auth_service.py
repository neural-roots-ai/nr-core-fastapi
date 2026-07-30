from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountLockedError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    RateLimitedError,
    ValidationAppError,
)
from app.core.security import (
    create_access_token,
    generate_otp,
    generate_refresh_token,
    hash_otp,
    hash_password,
    hash_token,
    verify_otp as verify_otp_hash,
    verify_password,
)
from app.db.models.auth_ext import AuthUserProfile, EmailOtp, LoginAudit, RefreshToken
from app.db.models.django_auth import AuthUser
from app.core.config import get_settings
from app.schemas.auth import SignupRequest
from app.services import email_service

logger = logging.getLogger(__name__)
settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_user_by_username_or_email(db: AsyncSession, identifier: str) -> AuthUser | None:
    stmt = select(AuthUser).where(
        (AuthUser.username == identifier) | (AuthUser.email == identifier)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_or_create_profile(db: AsyncSession, user_id: int) -> AuthUserProfile:
    profile = await db.get(AuthUserProfile, user_id)
    if profile is None:
        profile = AuthUserProfile(user_id=user_id)
        db.add(profile)
        await db.flush()
    return profile


# ---------------------------------------------------------------------------
# Signup / email verification
# ---------------------------------------------------------------------------

async def signup(db: AsyncSession, payload: SignupRequest) -> AuthUser:
    existing = await db.execute(
        select(AuthUser).where(
            (AuthUser.username == payload.username) | (AuthUser.email == payload.email)
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("A user with this username or email already exists.")

    user = AuthUser(
        username=payload.username,
        email=payload.email,
        password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        is_superuser=False,
        is_staff=False,
        is_active=True,
        date_joined=_now(),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("A user with this username or email already exists.") from exc

    profile = AuthUserProfile(user_id=user.id, phone_number=payload.phone_number, is_email_verified=False)
    db.add(profile)
    await db.flush()

    await _create_and_send_otp(db, user_id=user.id, email=user.email, purpose="signup_verify")
    await db.commit()
    await db.refresh(user)
    return user


async def _create_and_send_otp(db: AsyncSession, *, user_id: int | None, email: str, purpose: str) -> None:
    cooldown_cutoff = _now() - timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
    recent = await db.execute(
        select(EmailOtp)
        .where(EmailOtp.email == email, EmailOtp.purpose == purpose)
        .order_by(EmailOtp.created_on.desc())
        .limit(1)
    )
    latest = recent.scalar_one_or_none()
    if latest is not None and latest.created_on > cooldown_cutoff:
        wait_seconds = int((latest.created_on - cooldown_cutoff).total_seconds())
        raise RateLimitedError(f"Please wait {wait_seconds}s before requesting another code.")

    otp = generate_otp()
    otp_row = EmailOtp(
        user_id=user_id,
        email=email,
        otp_hash=hash_otp(otp),
        purpose=purpose,
        expires_at=_now() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    )
    db.add(otp_row)
    await db.flush()
    await email_service.send_otp_email(email, otp, purpose)


async def resend_otp(db: AsyncSession, email: str, purpose: str) -> None:
    user = (await db.execute(select(AuthUser).where(AuthUser.email == email))).scalar_one_or_none()
    if purpose == "signup_verify" and user is not None:
        profile = await _get_or_create_profile(db, user.id)
        if profile.is_email_verified:
            raise ConflictError("Email is already verified.")
    # Always behave the same whether or not the account exists, to avoid
    # leaking which emails are registered.
    await _create_and_send_otp(db, user_id=user.id if user else None, email=email, purpose=purpose)
    await db.commit()


async def _consume_otp(db: AsyncSession, email: str, otp: str, purpose: str) -> EmailOtp:
    stmt = (
        select(EmailOtp)
        .where(EmailOtp.email == email, EmailOtp.purpose == purpose, EmailOtp.is_used.is_(False))
        .order_by(EmailOtp.created_on.desc())
        .limit(1)
    )
    otp_row = (await db.execute(stmt)).scalar_one_or_none()
    if otp_row is None:
        raise AuthenticationError("Invalid or expired code.")

    if otp_row.expires_at < _now():
        raise AuthenticationError("Invalid or expired code.")

    if otp_row.attempts >= settings.OTP_MAX_ATTEMPTS:
        otp_row.is_used = True
        await db.commit()
        raise AuthenticationError("Too many incorrect attempts. Please request a new code.")

    if not verify_otp_hash(otp, otp_row.otp_hash):
        otp_row.attempts += 1
        await db.commit()
        raise AuthenticationError("Invalid or expired code.")

    otp_row.is_used = True
    await db.flush()
    return otp_row


async def verify_email(db: AsyncSession, email: str, otp: str) -> None:
    otp_row = await _consume_otp(db, email, otp, "signup_verify")
    user = (await db.execute(select(AuthUser).where(AuthUser.email == email))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found.")
    profile = await _get_or_create_profile(db, user.id)
    profile.is_email_verified = True
    otp_row.user_id = user.id
    await db.commit()


# ---------------------------------------------------------------------------
# Login / tokens
# ---------------------------------------------------------------------------

async def _issue_tokens(
    db: AsyncSession, user: AuthUser, *, ip_address: str | None, user_agent: str | None
) -> tuple[str, str, int]:
    access_token, expires_at = create_access_token(user_id=user.id, username=user.username, is_staff=user.is_staff)
    refresh_token = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            family_id=uuid.uuid4(),
            expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    await db.flush()
    expires_in = int((expires_at - _now()).total_seconds())
    return access_token, refresh_token, expires_in


async def login(
    db: AsyncSession, identifier: str, password: str, *, ip_address: str | None, user_agent: str | None
) -> tuple[str, str, int]:
    user = await _get_user_by_username_or_email(db, identifier)

    async def _audit(success: bool, reason: str | None, user_id: int | None = None) -> None:
        db.add(
            LoginAudit(
                user_id=user_id,
                username_attempted=identifier,
                success=success,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        await db.commit()

    if user is None:
        await _audit(False, "no_such_user")
        raise AuthenticationError("Incorrect username/email or password.")

    profile = await _get_or_create_profile(db, user.id)

    if profile.locked_until is not None and profile.locked_until > _now():
        await _audit(False, "locked", user.id)
        raise AccountLockedError("Account temporarily locked due to repeated failed attempts. Try again later.")

    if not verify_password(password, user.password):
        profile.failed_login_attempts += 1
        if profile.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            profile.locked_until = _now() + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
            profile.failed_login_attempts = 0
        await _audit(False, "bad_password", user.id)
        raise AuthenticationError("Incorrect username/email or password.")

    if not user.is_active:
        await _audit(False, "inactive", user.id)
        raise AuthenticationError("This account has been disabled.")

    if not profile.is_email_verified:
        await _audit(False, "email_not_verified", user.id)
        raise AuthenticationError("Please verify your email before logging in.", code="email_not_verified")

    profile.failed_login_attempts = 0
    profile.locked_until = None
    user.last_login = _now()

    access_token, refresh_token, expires_in = await _issue_tokens(db, user, ip_address=ip_address, user_agent=user_agent)
    await _audit(True, None, user.id)
    return access_token, refresh_token, expires_in


async def refresh_tokens(
    db: AsyncSession, refresh_token: str, *, ip_address: str | None, user_agent: str | None
) -> tuple[str, str, int]:
    token_hash = hash_token(refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    token_row = (await db.execute(stmt)).scalar_one_or_none()

    if token_row is None:
        raise AuthenticationError("Invalid refresh token.")

    if token_row.is_revoked:
        # Reuse of an already-rotated/revoked token: treat as a possible
        # theft and kill the whole session family defensively.
        await db.execute(
            RefreshToken.__table__.update()
            .where(RefreshToken.family_id == token_row.family_id)
            .values(is_revoked=True)
        )
        await db.commit()
        raise AuthenticationError("Refresh token has already been used. Please log in again.")

    if token_row.expires_at < _now():
        raise AuthenticationError("Refresh token expired. Please log in again.")

    user = await db.get(AuthUser, token_row.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Account is not available.")

    token_row.is_revoked = True

    access_token, expires_at = create_access_token(user_id=user.id, username=user.username, is_staff=user.is_staff)
    new_refresh_token = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(new_refresh_token),
            family_id=token_row.family_id,
            expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    await db.commit()
    expires_in = int((expires_at - _now()).total_seconds())
    return access_token, new_refresh_token, expires_in


async def logout(db: AsyncSession, refresh_token: str) -> None:
    token_hash = hash_token(refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    token_row = (await db.execute(stmt)).scalar_one_or_none()
    if token_row is not None:
        token_row.is_revoked = True
        await db.commit()


async def logout_all(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        RefreshToken.__table__.update().where(RefreshToken.user_id == user_id).values(is_revoked=True)
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Password reset / change
# ---------------------------------------------------------------------------

async def forgot_password(db: AsyncSession, email: str) -> None:
    user = (await db.execute(select(AuthUser).where(AuthUser.email == email))).scalar_one_or_none()
    # Always behave identically regardless of whether the email is
    # registered, to avoid leaking account existence.
    await _create_and_send_otp(db, user_id=user.id if user else None, email=email, purpose="password_reset")
    await db.commit()


async def reset_password(db: AsyncSession, email: str, otp: str, new_password: str) -> None:
    await _consume_otp(db, email, otp, "password_reset")
    user = (await db.execute(select(AuthUser).where(AuthUser.email == email))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found.")

    user.password = hash_password(new_password)
    profile = await _get_or_create_profile(db, user.id)
    profile.failed_login_attempts = 0
    profile.locked_until = None
    await db.flush()

    # Force re-login everywhere after a password reset.
    await db.execute(
        RefreshToken.__table__.update().where(RefreshToken.user_id == user.id).values(is_revoked=True)
    )
    await db.commit()


async def change_password(db: AsyncSession, user: AuthUser, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password):
        raise ValidationAppError("Current password is incorrect.")
    user.password = hash_password(new_password)
    await db.flush()
    await db.execute(
        RefreshToken.__table__.update().where(RefreshToken.user_id == user.id).values(is_revoked=True)
    )
    await db.commit()
