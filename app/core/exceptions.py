"""Application-level exceptions.

Services raise these instead of HTTPException directly, so business
logic stays framework-agnostic. A single exception handler in
app.main translates them into the JSON error envelope.
"""

from __future__ import annotations


class AppError(Exception):
    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_error"


class AccountLockedError(AppError):
    status_code = 423
    code = "account_locked"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


class PaymentGatewayError(AppError):
    status_code = 502
    code = "payment_gateway_error"
