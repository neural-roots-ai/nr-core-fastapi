import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.middleware.rate_limit import limiter
from app.schemas.payment import (
    CreateOrderRequest,
    CreateOrderResponse,
    EnrollmentOut,
    OrderStatusResponse,
    ProgramFeeOut,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from app.services import payment_service
from app.services.razorpay_service import verify_webhook_signature

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/programs/{program_id}/fee")
async def get_program_fee(program_id: int, country_id: int, db: DbSession) -> ProgramFeeOut:
    program, base_amount, final_amount, discount_amount = await payment_service.get_program_fee_details(
        db, program_id, country_id
    )
    return ProgramFeeOut(
        program_id=program.program_id,
        program_name=program.program_name,
        country_id=country_id,
        base_amount=base_amount,
        amount=final_amount,
        discount_amount=discount_amount,
        currency=settings.DEFAULT_CURRENCY,
    )


@router.post("/orders", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_order(
    request: Request,
    payload: CreateOrderRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> CreateOrderResponse:
    order, program_name = await payment_service.create_order(db, current_user, payload.program_id, payload.country_id)
    return CreateOrderResponse(
        order_id=order.id,
        razorpay_order_id=order.razorpay_order_id,
        razorpay_key_id=settings.RAZORPAY_KEY_ID,
        amount=order.amount,
        amount_subunits=order.amount_subunits,
        currency=order.currency,
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
