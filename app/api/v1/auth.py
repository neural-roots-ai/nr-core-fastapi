from fastapi import APIRouter, Request, status

from app.api.deps import ClientIp, CurrentUser, DbSession, UserAgent
from app.middleware.rate_limit import limiter
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def signup(request: Request, payload: SignupRequest, db: DbSession) -> SignupResponse:
    user = await auth_service.signup(db, payload)
    return SignupResponse(id=user.id, username=user.username, email=user.email)


@router.post("/verify-email", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def verify_email(request: Request, payload: VerifyEmailRequest, db: DbSession) -> dict:
    await auth_service.verify_email(db, payload.email, payload.otp)
    return {"message": "Email verified. You can now log in."}


@router.post("/resend-otp", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def resend_otp(request: Request, payload: ResendOtpRequest, db: DbSession) -> dict:
    await auth_service.resend_otp(db, payload.email, payload.purpose)
    return {"message": "If that email is registered, a new code has been sent."}


@router.post("/login", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    db: DbSession,
    ip_address: ClientIp,
    user_agent: UserAgent,
) -> TokenResponse:
    access_token, refresh_token, expires_in = await auth_service.login(
        db, payload.identifier, payload.password, ip_address=ip_address, user_agent=user_agent
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/refresh", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    payload: RefreshRequest,
    db: DbSession,
    ip_address: ClientIp,
    user_agent: UserAgent,
) -> TokenResponse:
    access_token, refresh_token, expires_in = await auth_service.refresh_tokens(
        db, payload.refresh_token, ip_address=ip_address, user_agent=user_agent
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(payload: LogoutRequest, db: DbSession) -> dict:
    await auth_service.logout(db, payload.refresh_token)
    return {"message": "Logged out."}


@router.post("/logout-all", status_code=status.HTTP_200_OK)
async def logout_all(db: DbSession, current_user: CurrentUser) -> dict:
    await auth_service.logout_all(db, current_user.id)
    return {"message": "Logged out of all sessions."}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def forgot_password(request: Request, payload: ForgotPasswordRequest, db: DbSession) -> dict:
    await auth_service.forgot_password(db, payload.email)
    return {"message": "If that email is registered, a reset code has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def reset_password(request: Request, payload: ResetPasswordRequest, db: DbSession) -> dict:
    await auth_service.reset_password(db, payload.email, payload.otp, payload.new_password)
    return {"message": "Password has been reset. Please log in again."}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(payload: ChangePasswordRequest, db: DbSession, current_user: CurrentUser) -> dict:
    await auth_service.change_password(db, current_user, payload.current_password, payload.new_password)
    return {"message": "Password changed. Please log in again."}


@router.get("/me")
async def me(current_user: CurrentUser) -> UserOut:
    profile = current_user.profile
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        is_email_verified=bool(profile and profile.is_email_verified),
        date_joined=current_user.date_joined,
    )
