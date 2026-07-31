from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
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
from app.db.models.pricing import ProgramPrice
from app.db.models.promo import PromoCodeRedemption
from app.schemas.payment import VerifyPaymentRequest
from app.services import email_service, promo_service, razorpay_service
from app.services.currency_service import ResolvedCurrency

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


def _apply_discount(amount: Decimal, discount_amount: Decimal | int | None) -> Decimal:
    """Both program_fee.discount and program_price.discount_amount are a flat
    amount in the same currency as the price (e.g. fee=7000, discount=6500 ->
    payable 500), NOT a percentage - confirmed against live NRDB data where
    discount values exceed 100.
    """
    if not discount_amount:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net = amount - Decimal(discount_amount)
    if net < 0:
        net = Decimal("0")
    return net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class _PriceResolution:
    program: Program
    base_amount: Decimal
    final_amount: Decimal
    discount_amount: Decimal
    currency_code: str
    country_id: int | None
    program_fee_id: int | None
    program_price_id: int | None


async def _get_program_price_row(db: AsyncSession, program_id: int, currency_code: str) -> ProgramPrice | None:
    stmt = select(ProgramPrice).where(
        ProgramPrice.program_id == program_id,
        ProgramPrice.currency_code == currency_code,
        ProgramPrice.is_active.is_(True),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_legacy_program_fee_row(db: AsyncSession, program_id: int, country_id: int) -> ProgramFee | None:
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
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_active_program(db: AsyncSession, program_id: int) -> Program:
    program = await db.get(Program, program_id)
    if program is None or not program.is_active:
        raise NotFoundError("Program not found.")
    return program


async def _resolve_price(db: AsyncSession, program_id: int, currency_code: str, country_id: int | None) -> _PriceResolution:
    """Prices a program in `currency_code`: the new program_price table
    (currency-keyed) is authoritative; the legacy country-keyed program_fee
    table is only consulted as a fallback while program_price is being
    backfilled, and only when a country_id is actually available.
    """
    program = await _get_active_program(db, program_id)

    price_row = await _get_program_price_row(db, program_id, currency_code)
    if price_row is not None:
        final_amount = _apply_discount(price_row.base_amount, price_row.discount_amount)
        return _PriceResolution(
            program=program,
            base_amount=price_row.base_amount,
            final_amount=final_amount,
            discount_amount=price_row.base_amount - final_amount,
            currency_code=currency_code,
            country_id=country_id,
            program_fee_id=None,
            program_price_id=price_row.program_price_id,
        )

    if country_id is not None:
        legacy_fee = await _get_legacy_program_fee_row(db, program_id, country_id)
        if legacy_fee is not None:
            # Quantize to 2dp like program_price.base_amount already is (a
            # NUMERIC(12,2) column) - program_fee.program_fee is a bare
            # varchar, so an unquantized "70000" would otherwise render as
            # base_amount="70000" instead of "70000.00" in API responses.
            base_amount = _parse_fee_amount(legacy_fee.program_fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            final_amount = _apply_discount(base_amount, legacy_fee.discount)
            return _PriceResolution(
                program=program,
                base_amount=base_amount,
                final_amount=final_amount,
                discount_amount=base_amount - final_amount,
                # Legacy program_fee predates multi-currency and was always
                # entered in the settlement currency (INR) - see README.
                currency_code=settings.SETTLEMENT_CURRENCY,
                country_id=country_id,
                program_fee_id=legacy_fee.program_fee_id,
                program_price_id=None,
            )

    raise NotFoundError(
        f"Program {program_id} has no active price configured for {currency_code}. "
        "Add a program_price row for this currency (or pass a country_id with an "
        "existing legacy program_fee row)."
    )


async def get_program_fee_details(db: AsyncSession, program_id: int, resolved: ResolvedCurrency) -> _PriceResolution:
    return await _resolve_price(db, program_id, resolved.currency_code, resolved.country_id)


async def create_order(
    db: AsyncSession,
    user: AuthUser,
    program_id: int,
    resolved: ResolvedCurrency,
    promo_code: str | None = None,
) -> tuple[PaymentOrder, str]:
    display_price = await _resolve_price(db, program_id, resolved.currency_code, resolved.country_id)
    natively_chargeable = display_price.currency_code in settings.razorpay_charge_currencies

    promo_quote = None
    display_payable = display_price.final_amount
    if promo_code:
        # Locks the promo_code row and reserves a usage slot - see
        # app/services/promo_service.py. Runs in this same uncommitted
        # transaction, so a failure anywhere below (including the Razorpay
        # API call) rolls the reservation back along with the order.
        promo_quote = await promo_service.redeem(
            db,
            code=promo_code,
            program_id=program_id,
            user_id=user.id,
            currency_code=display_price.currency_code,
            amount=display_price.final_amount,
            natively_chargeable=natively_chargeable,
        )
        display_payable = promo_quote.payable_amount

    if natively_chargeable:
        settlement_price = display_price
        settlement_payable = display_payable
    else:
        # Razorpay can't charge this currency for this merchant account -
        # fall back to the settlement currency (INR) so checkout can still
        # happen; display_price/display_payable above are kept for what the
        # buyer was shown. redeem() only allows a currency-scoped promo
        # (FIXED_AMOUNT, or a capped PERCENTAGE) when natively_chargeable,
        # so any promo reaching this branch is safe to reapply as-is.
        settlement_price = await _resolve_price(db, program_id, settings.SETTLEMENT_CURRENCY, resolved.country_id)
        settlement_payable = (
            promo_service.apply_to_amount(promo_quote, settlement_price.final_amount)
            if promo_quote is not None
            else settlement_price.final_amount
        )

    amount_subunits = int((settlement_payable * 100).to_integral_value(rounding=ROUND_HALF_UP))

    receipt = f"nr-{user.id}-{program_id}-{uuid.uuid4().hex[:10]}"
    razorpay_order = await razorpay_service.create_order(
        amount_subunits=amount_subunits,
        currency=settlement_price.currency_code,
        receipt=receipt,
        notes={"user_id": str(user.id), "program_id": str(program_id), "username": user.username},
    )

    order = PaymentOrder(
        user_id=user.id,
        program_id=program_id,
        program_fee_id=settlement_price.program_fee_id,
        program_price_id=settlement_price.program_price_id,
        country_id=resolved.country_id,
        razorpay_order_id=razorpay_order["id"],
        amount=settlement_payable,
        amount_subunits=amount_subunits,
        currency=settlement_price.currency_code,
        display_amount=display_payable,
        display_currency=display_price.currency_code,
        promo_code_id=promo_quote.promo_code_id if promo_quote is not None else None,
        promo_discount_amount=promo_quote.discount_amount if promo_quote is not None else None,
        status="created",
        receipt=receipt,
    )
    db.add(order)
    await db.flush()  # need order.id before the redemption row can reference it

    if promo_quote is not None:
        db.add(
            PromoCodeRedemption(
                promo_code_id=promo_quote.promo_code_id,
                user_id=user.id,
                payment_order_id=order.id,
                discount_amount=promo_quote.discount_amount,
                currency_code=promo_quote.currency_code,
                status="reserved",
            )
        )

    await db.commit()
    await db.refresh(order)
    return order, display_price.program.program_name


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
        if order.promo_code_id is not None:
            await promo_service.confirm_redemption(db, order.id)
    elif status == "failed" and order.status == "created":
        order.status = "failed"
        if order.promo_code_id is not None:
            await promo_service.release_redemption(db, order.id)

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
