"""Promo code validation and atomic redemption.

Two entry points, deliberately different in strictness:
  - `quote()`  - read-only preview (no row lock, no reservation). Used by the
    /programs/{id}/fee price preview so a mistyped/expired code just shows
    "invalid" inline instead of failing the whole price lookup.
  - `redeem()` - authoritative. Locks the promo_code row (SELECT ... FOR
    UPDATE) before counting/validating so concurrent checkouts against a
    limited-quantity code can't oversell it, then reserves a slot by
    incrementing times_used. Must run inside the same DB transaction as the
    payment_order insert it belongs to (see payment_service.create_order) -
    both commit together, or neither does.

Currency safety: a promo scoped to one currency (`currency_code` set - always
true for FIXED_AMOUNT, optionally true for a capped PERCENTAGE) can only be
redeemed when the buyer is being charged in exactly that currency
(`natively_chargeable=True`). Reapplying a GBP-denominated discount to an
INR settlement amount would silently mismatch units, so it's rejected
outright rather than guessed at - see README "Regional pricing".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.db.models.promo import PromoCode, PromoCodeRedemption

PROMO_ERROR_CODE = "promo_code_invalid"


@dataclass(frozen=True)
class PromoQuote:
    promo_code_id: int
    code: str
    discount_type: str
    discount_value: Decimal
    max_discount_amount: Decimal | None
    currency_code: str
    discount_amount: Decimal
    payable_amount: Decimal


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_discount(
    *, discount_type: str, discount_value: Decimal, max_discount_amount: Decimal | None, amount: Decimal
) -> Decimal:
    raw = amount * discount_value / Decimal(100) if discount_type == "PERCENTAGE" else discount_value
    if max_discount_amount is not None:
        raw = min(raw, max_discount_amount)
    raw = max(min(raw, amount), Decimal("0"))
    return _quantize(raw)


def _normalize_code(code: str) -> str:
    return code.strip().upper()


def _validate_window_and_scope(promo: PromoCode, *, program_id: int, currency_code: str, amount: Decimal) -> None:
    now = datetime.now(timezone.utc)
    if not promo.is_active:
        raise ValidationAppError("This promo code is no longer active.", code=PROMO_ERROR_CODE)
    if promo.starts_at and now < promo.starts_at:
        raise ValidationAppError("This promo code isn't active yet.", code=PROMO_ERROR_CODE)
    if promo.expires_at and now > promo.expires_at:
        raise ValidationAppError("This promo code has expired.", code=PROMO_ERROR_CODE)
    if promo.applicable_program_id is not None and promo.applicable_program_id != program_id:
        raise ValidationAppError("This promo code isn't valid for this program.", code=PROMO_ERROR_CODE)
    if promo.currency_code is not None and promo.currency_code != currency_code:
        raise ValidationAppError(
            f"This promo code is only valid for {promo.currency_code} purchases.", code=PROMO_ERROR_CODE
        )
    if promo.min_order_amount is not None and amount < promo.min_order_amount:
        raise ValidationAppError(
            f"This promo code requires a minimum order of {promo.min_order_amount} {currency_code}.",
            code=PROMO_ERROR_CODE,
        )


def _to_quote(promo: PromoCode, *, currency_code: str, amount: Decimal) -> PromoQuote:
    discount_amount = compute_discount(
        discount_type=promo.discount_type,
        discount_value=promo.discount_value,
        max_discount_amount=promo.max_discount_amount,
        amount=amount,
    )
    return PromoQuote(
        promo_code_id=promo.promo_code_id,
        code=promo.code,
        discount_type=promo.discount_type,
        discount_value=promo.discount_value,
        max_discount_amount=promo.max_discount_amount,
        currency_code=currency_code,
        discount_amount=discount_amount,
        payable_amount=_quantize(amount - discount_amount),
    )


async def quote(db: AsyncSession, *, code: str, program_id: int, currency_code: str, amount: Decimal) -> PromoQuote:
    """Read-only preview - safe to call from an unauthenticated GET."""
    promo = (
        await db.execute(select(PromoCode).where(PromoCode.code == _normalize_code(code)))
    ).scalar_one_or_none()
    if promo is None:
        raise ValidationAppError("This promo code doesn't exist.", code=PROMO_ERROR_CODE)
    _validate_window_and_scope(promo, program_id=program_id, currency_code=currency_code, amount=amount)
    return _to_quote(promo, currency_code=currency_code, amount=amount)


async def redeem(
    db: AsyncSession,
    *,
    code: str,
    program_id: int,
    user_id: int,
    currency_code: str,
    amount: Decimal,
    natively_chargeable: bool,
) -> PromoQuote:
    """Locks, validates, and reserves a usage slot. Caller commits (or lets
    the surrounding session roll back on error) together with the
    payment_order it belongs to."""
    stmt = select(PromoCode).where(PromoCode.code == _normalize_code(code)).with_for_update()
    promo = (await db.execute(stmt)).scalar_one_or_none()
    if promo is None:
        raise ValidationAppError("This promo code doesn't exist.", code=PROMO_ERROR_CODE)

    _validate_window_and_scope(promo, program_id=program_id, currency_code=currency_code, amount=amount)

    if promo.currency_code is not None and not natively_chargeable:
        raise ValidationAppError(
            "This promo code isn't available for your currency/region right now.", code=PROMO_ERROR_CODE
        )

    if promo.max_redemptions is not None and promo.times_used >= promo.max_redemptions:
        raise ValidationAppError("This promo code has reached its usage limit.", code=PROMO_ERROR_CODE)

    existing_uses = (
        await db.execute(
            select(func.count())
            .select_from(PromoCodeRedemption)
            .where(
                PromoCodeRedemption.promo_code_id == promo.promo_code_id,
                PromoCodeRedemption.user_id == user_id,
                PromoCodeRedemption.status.in_(["reserved", "confirmed"]),
            )
        )
    ).scalar_one()
    if existing_uses >= promo.max_redemptions_per_user:
        raise ValidationAppError("You've already used this promo code.", code=PROMO_ERROR_CODE)

    promo.times_used += 1
    return _to_quote(promo, currency_code=currency_code, amount=amount)


def apply_to_amount(quote_: PromoQuote, amount: Decimal) -> Decimal:
    """Reapplies an already-reserved quote's discount to a second amount
    (the settlement leg, when it's priced in a different currency than the
    display leg) - only ever called when the quote is currency-agnostic
    (PERCENTAGE, no currency_code), which `redeem()` guarantees via the
    natively_chargeable check above."""
    discount = compute_discount(
        discount_type=quote_.discount_type,
        discount_value=quote_.discount_value,
        max_discount_amount=quote_.max_discount_amount,
        amount=amount,
    )
    return _quantize(amount - discount)


async def confirm_redemption(db: AsyncSession, payment_order_id: int) -> None:
    redemption = (
        await db.execute(select(PromoCodeRedemption).where(PromoCodeRedemption.payment_order_id == payment_order_id))
    ).scalar_one_or_none()
    if redemption is not None and redemption.status == "reserved":
        redemption.status = "confirmed"


async def release_redemption(db: AsyncSession, payment_order_id: int) -> None:
    stmt = (
        select(PromoCodeRedemption)
        .where(PromoCodeRedemption.payment_order_id == payment_order_id)
        .with_for_update()
    )
    redemption = (await db.execute(stmt)).scalar_one_or_none()
    if redemption is None or redemption.status != "reserved":
        return
    redemption.status = "released"
    promo = await db.get(PromoCode, redemption.promo_code_id)
    if promo is not None and promo.times_used > 0:
        promo.times_used -= 1
