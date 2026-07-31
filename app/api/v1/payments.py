import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ValidationAppError
from app.middleware.rate_limit import limiter
from app.schemas.payment import (
    CreateOrderRequest,
    CreateOrderResponse,
    CurrencyOut,
    DetectedRegionOut,
    EnrollmentOut,
    OrderStatusResponse,
    ProgramFeeOut,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from app.services import currency_service, payment_service, promo_service
from app.services.razorpay_service import verify_webhook_signature

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/payments", tags=["payments"])


async def _resolve_currency(
    request: Request,
    response: Response,
    db: DbSession,
    *,
    country_id: int | None,
    currency: str | None,
):
    resolved = await currency_service.resolve(
        db,
        request,
        currency_override=currency,
        country_id_override=country_id,
        cookie_currency=request.cookies.get(currency_service.PREFERRED_CURRENCY_COOKIE),
    )
    if resolved.source == "override":
        # Remember an explicit choice so the next visit (and the eventual
        # /orders call) stays consistent without re-detecting.
        response.set_cookie(
            currency_service.PREFERRED_CURRENCY_COOKIE,
            resolved.currency_code,
            max_age=settings.PREFERRED_CURRENCY_COOKIE_MAX_AGE_SECONDS,
            samesite="lax",
            httponly=False,  # frontend reads this to pre-select the currency switcher
        )
    return resolved


@router.get("/currency")
async def detect_currency(
    request: Request,
    response: Response,
    db: DbSession,
    currency: str | None = None,
) -> DetectedRegionOut:
    """Region/currency detection for the frontend's initial page load and
    its currency switcher - independent of any specific program."""
    resolved = await _resolve_currency(request, response, db, country_id=None, currency=currency)
    currency_row = await currency_service.get_currency(db, resolved.currency_code)
    supported = await currency_service.get_active_currencies(db)
    return DetectedRegionOut(
        currency=resolved.currency_code,
        currency_symbol=currency_row.symbol if currency_row else resolved.currency_code,
        country_id=resolved.country_id,
        currency_source=resolved.source,
        is_estimated=resolved.is_estimated,
        supported_currencies=[
            CurrencyOut(
                currency_code=c.currency_code,
                currency_name=c.currency_name,
                symbol=c.symbol,
                decimal_digits=c.decimal_digits,
            )
            for c in supported
        ],
    )


@router.get("/programs/{program_id}/fee")
async def get_program_fee(
    program_id: int,
    db: DbSession,
    request: Request,
    response: Response,
    country_id: int | None = None,
    currency: str | None = None,
    promo_code: str | None = None,
) -> ProgramFeeOut:
    resolved = await _resolve_currency(request, response, db, country_id=country_id, currency=currency)
    price = await payment_service.get_program_fee_details(db, program_id, resolved)
    currency_row = await currency_service.get_currency(db, price.currency_code)

    promo_valid: bool | None = None
    promo_message: str | None = None
    promo_discount_amount = None
    payable_amount = price.final_amount
    if promo_code:
        try:
            # Read-only preview: does not lock the promo row or reserve a
            # usage slot, so a mistyped/expired code just reports itself as
            # invalid instead of failing this (public, unauthenticated) lookup.
            promo_quote = await promo_service.quote(
                db, code=promo_code, program_id=program_id, currency_code=price.currency_code, amount=price.final_amount
            )
            promo_valid = True
            promo_discount_amount = promo_quote.discount_amount
            payable_amount = promo_quote.payable_amount
        except ValidationAppError as exc:
            promo_valid = False
            promo_message = exc.message

    return ProgramFeeOut(
        program_id=price.program.program_id,
        program_name=price.program.program_name,
        country_id=price.country_id,
        base_amount=price.base_amount,
        amount=price.final_amount,
        discount_amount=price.discount_amount,
        currency=price.currency_code,
        currency_symbol=currency_row.symbol if currency_row else price.currency_code,
        currency_source=resolved.source,
        is_estimated=resolved.is_estimated,
        promo_code=promo_code,
        promo_valid=promo_valid,
        promo_message=promo_message,
        promo_discount_amount=promo_discount_amount,
        payable_amount=payable_amount,
    )


@router.post("/orders", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_order(
    request: Request,
    response: Response,
    payload: CreateOrderRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> CreateOrderResponse:
    resolved = await _resolve_currency(
        request, response, db, country_id=payload.country_id, currency=payload.currency
    )
    order, program_name = await payment_service.create_order(
        db, current_user, payload.program_id, resolved, promo_code=payload.promo_code
    )
    return CreateOrderResponse(
        order_id=order.id,
        razorpay_order_id=order.razorpay_order_id,
        razorpay_key_id=settings.RAZORPAY_KEY_ID,
        amount=order.amount,
        amount_subunits=order.amount_subunits,
        currency=order.currency,
        display_amount=order.display_amount,
        display_currency=order.display_currency,
        promo_code=payload.promo_code if order.promo_code_id is not None else None,
        promo_discount_amount=order.promo_discount_amount,
        program_name=program_name,
        receipt=order.receipt,
    )


@router.post("/orders/verify")
@limiter.limit("20/minute")
async def verify_payment(
    request: Request,
    payload: VerifyPaymentRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> VerifyPaymentResponse:
    order_status, enrollment_status = await payment_service.verify_payment(db, current_user, payload)
    if order_status == "paid":
        message = "Payment successful. You're enrolled!"
    elif order_status == "failed":
        message = "Payment failed. Please try again."
    else:
        message = "Payment is being processed."
    return VerifyPaymentResponse(status=order_status, enrollment_status=enrollment_status, message=message)


@router.get("/orders/{order_id}")
async def get_order_status(order_id: int, db: DbSession, current_user: CurrentUser) -> OrderStatusResponse:
    order, program_name = await payment_service.get_order_status(db, current_user, order_id)
    return OrderStatusResponse(status=order.status, amount=order.amount, currency=order.currency, program_name=program_name)


@router.get("/enrollments/me")
async def list_my_enrollments(db: DbSession, current_user: CurrentUser) -> list[EnrollmentOut]:
    rows = await payment_service.list_enrollments(db, current_user)
    return [
        EnrollmentOut(
            program_id=enrollment.program_id,
            program_name=program_name,
            status=enrollment.status,
            enrolled_on=enrollment.enrolled_on,
        )
        for enrollment, program_name in rows
    ]


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    responses={400: {"description": "Missing/invalid signature header or malformed JSON body."}},
)
async def razorpay_webhook(
    request: Request,
    db: DbSession,
    x_razorpay_signature: str | None = Header(default=None),
) -> dict:
    raw_body = await request.body()

    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing signature header.")

    if not verify_webhook_signature(raw_body=raw_body, signature=x_razorpay_signature):
        raise AuthenticationError("Invalid webhook signature.")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    try:
        await payment_service.handle_webhook(db, payload)
    except Exception:
        logger.exception("Error handling Razorpay webhook event=%s", payload.get("event"))
        # Still return 200: we've logged it, and returning a non-2xx here
        # would make Razorpay retry a payload we may have already
        # partially processed (records are idempotent on payment_id).
    return {"status": "ok"}
