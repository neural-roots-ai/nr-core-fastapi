from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError, ValidationAppError
from app.db.models.catalog import Program, ProgramFee
from app.db.models.django_auth import AuthUser
from app.db.models.payment import CourseEnrollment, PaymentOrder, PaymentTransaction
from app.schemas.payment import VerifyPaymentRequest
from app.services import email_service, razorpay_service

logger = logging.getLogger(__name__)
settings = get_settings()


def _parse_fee_amount(raw: str) -> Decimal:
    cleaned = re.sub(r"[^0-9.]", "", raw or "")
    if not cleaned:
        raise ValidationAppError("Program fee is not configured correctly.")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValidationAppError("Program fee is not configured correctly.") from exc


def _apply_discount(amount: Decimal, discount_amount: int | None) -> Decimal:
    """program_fee.discount is a flat amount in the same currency as the
    fee (e.g. fee=7000, discount=6500 -> payable 500), NOT a percentage -
    confirmed against live NRDB data where discount values exceed 100.
    """
    if not discount_amount:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net = amount - Decimal(discount_amount)
    if net < 0:
        net = Decimal("0")
    return net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def _get_program_fee_row(db: AsyncSession, program_id: int, country_id: int) -> ProgramFee:
    stmt = (
        select(ProgramFee)
        .join(Program, ProgramFee.program_id == Program.program_id)
        .where(
            ProgramFee.program_id == program_id,
            ProgramFee.country_id == country_id,
            ProgramFee.is_active.is_(True),
            Program.is_active.is_(True),
        )
    )
    fee = (await db.execute(stmt)).scalar_one_or_none()
    if fee is None:
        raise NotFoundError("No active fee found for this program and country.")
    return fee


async def get_program_fee_details(
    db: AsyncSession, program_id: int, country_id: int
) -> tuple[Program, Decimal, Decimal, Decimal]:
    """Returns (program, base_amount, final_amount, discount_amount)."""
    fee = await _get_program_fee_row(db, program_id, country_id)
    program = await db.get(Program, program_id)
    if program is None:
        raise NotFoundError("Program not found.")
    base_amount = _parse_fee_amount(fee.program_fee)
    final_amount = _apply_discount(base_amount, fee.discount)
    return program, base_amount, final_amount, base_amount - final_amount


async def create_order(db: AsyncSession, user: AuthUser, program_id: int, country_id: int) -> tuple[PaymentOrder, str]:
    fee = await _get_program_fee_row(db, program_id, country_id)
    program = await db.get(Program, program_id)
    if program is None:
        raise NotFoundError("Program not found.")

    base_amount = _parse_fee_amount(fee.program_fee)
    amount = _apply_discount(base_amount, fee.discount)
    currency = settings.DEFAULT_CURRENCY
    amount_subunits = int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))

    receipt = f"nr-{user.id}-{program_id}-{uuid.uuid4().hex[:10]}"
    razorpay_order = await razorpay_service.create_order(
        amount_subunits=amount_subunits,
        currency=currency,
        receipt=receipt,
        notes={"user_id": str(user.id), "program_id": str(program_id), "username": user.username},
    )

    order = PaymentOrder(
        user_id=user.id,
        program_id=program_id,
        program_fee_id=fee.program_fee_id,
        country_id=country_id,
        razorpay_order_id=razorpay_order["id"],
        amount=amount,
        amount_subunits=amount_subunits,
        currency=currency,
        status="created",
        receipt=receipt,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order, program.program_name


async def _upsert_enrollment(db: AsyncSession, order: PaymentOrder) -> None:
    stmt = select(CourseEnrollment).where(
        CourseEnrollment.user_id == order.user_id, CourseEnrollment.program_id == order.program_id
    )
    enrollment = (await db.execute(stmt)).scalar_one_or_none()
    if enrollment is None:
        db.add(
            CourseEnrollment(
                user_id=order.user_id,
                program_id=order.program_id,
                payment_order_id=order.id,
                status="active",
                enrolled_on=datetime.now(timezone.utc),
            )
        )
    else:
        enrollment.status = "active"
        enrollment.payment_order_id = order.id
        enrollment.enrolled_on = enrollment.enrolled_on or datetime.now(timezone.utc)
    await db.flush()


async def _record_payment_and_enroll(db: AsyncSession, order: PaymentOrder, payment_data: dict[str, Any]) -> None:
    """Idempotent: a payment_id that's already recorded is a no-op.

    Both the client-side /verify call and the server-side webhook can
    race to record the same razorpay_payment_id; the unique constraint
    on payment_transaction.razorpay_payment_id is the source of truth
    that prevents double-processing.
    """
    razorpay_payment_id = payment_data["id"]
    existing = await db.execute(
        select(PaymentTransaction).where(PaymentTransaction.razorpay_payment_id == razorpay_payment_id)
    )
    if existing.scalar_one_or_none() is not None:
        return

    status = payment_data.get("status", "failed")
    card = payment_data.get("card") or {}
    db.add(
        PaymentTransaction(
            payment_order_id=order.id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=payment_data.get("signature"),
            method=payment_data.get("method"),
            status=status,
            amount_subunits=int(payment_data.get("amount") or order.amount_subunits),
            currency=payment_data.get("currency") or order.currency,
            bank=payment_data.get("bank"),
            wallet=payment_data.get("wallet"),
            vpa=payment_data.get("vpa"),
            card_last4=card.get("last4"),
            card_network=card.get("network"),
            error_code=payment_data.get("error_code"),
            error_description=payment_data.get("error_description"),
            raw_payload=payment_data,
        )
    )

    if status == "captured":
        order.status = "paid"
        await _upsert_enrollment(db, order)
    elif status == "failed" and order.status == "created":
        order.status = "failed"

    await db.flush()


async def verify_payment(db: AsyncSession, user: AuthUser, req: VerifyPaymentRequest) -> tuple[str, str]:
    stmt = select(PaymentOrder).where(PaymentOrder.razorpay_order_id == req.razorpay_order_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise NotFoundError("Order not found.")
    if order.user_id != user.id:
        raise PermissionDeniedError("This order does not belong to you.")

    if not razorpay_service.verify_payment_signature(
        razorpay_order_id=req.razorpay_order_id,
        razorpay_payment_id=req.razorpay_payment_id,
        razorpay_signature=req.razorpay_signature,
    ):
        raise AuthenticationError("Payment signature verification failed.")

    payment_data = await razorpay_service.fetch_payment(req.razorpay_payment_id)
    payment_data["signature"] = req.razorpay_signature

    try:
        await _record_payment_and_enroll(db, order, payment_data)
        await db.commit()
    except IntegrityError:
        await db.rollback()  # the webhook already recorded this payment concurrently

    await db.refresh(order)
    enrollment_stmt = select(CourseEnrollment).where(
        CourseEnrollment.user_id == user.id, CourseEnrollment.program_id == order.program_id
    )
    enrollment = (await db.execute(enrollment_stmt)).scalar_one_or_none()

    if order.status == "paid":
        program = await db.get(Program, order.program_id)
        if program is not None:
            await email_service.send_payment_confirmation_email(
                user.email, program.program_name, str(order.amount), order.currency
            )

    return order.status, (enrollment.status if enrollment else "pending")


async def handle_webhook(db: AsyncSession, payload: dict[str, Any]) -> None:
    event = payload.get("event")
    payment_entity = (payload.get("payload") or {}).get("payment", {}).get("entity")
    if not payment_entity:
        return

    razorpay_order_id = payment_entity.get("order_id")
    if not razorpay_order_id:
        return

    stmt = select(PaymentOrder).where(PaymentOrder.razorpay_order_id == razorpay_order_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        logger.warning("Webhook event %s for unknown razorpay_order_id=%s", event, razorpay_order_id)
        return

    try:
        await _record_payment_and_enroll(db, order, payment_entity)
        await db.commit()
    except IntegrityError:
        await db.rollback()  # already recorded via the client-side /verify call

    await db.refresh(order)
    if order.status == "paid" and event == "payment.captured":
        user = await db.get(AuthUser, order.user_id)
        program = await db.get(Program, order.program_id)
        if user is not None and program is not None:
            await email_service.send_payment_confirmation_email(
                user.email, program.program_name, str(order.amount), order.currency
            )


async def get_order_status(db: AsyncSession, user: AuthUser, order_id: int) -> tuple[PaymentOrder, str]:
    order = await db.get(PaymentOrder, order_id)
    if order is None or order.user_id != user.id:
        raise NotFoundError("Order not found.")
    program = await db.get(Program, order.program_id)
    return order, (program.program_name if program else "")


async def list_enrollments(db: AsyncSession, user: AuthUser) -> list[tuple[CourseEnrollment, str]]:
    stmt = (
        select(CourseEnrollment, Program.program_name)
        .join(Program, CourseEnrollment.program_id == Program.program_id)
        .where(CourseEnrollment.user_id == user.id)
        .order_by(CourseEnrollment.created_on.desc())
    )
    return list((await db.execute(stmt)).all())
