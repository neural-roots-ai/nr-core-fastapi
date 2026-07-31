"""Promo code / coupon tables (owned by this service, see
sql/005_promo_codes.sql). Additive - no coupon/promo table existed anywhere
in NRDB before this (confirmed against live schema).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PromoCode(Base):
    __tablename__ = "promo_code"
    __table_args__ = (UniqueConstraint("code", name="uq_promo_code_code"),)

    promo_code_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)  # always stored/matched uppercase
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'PERCENTAGE' | 'FIXED_AMOUNT'
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # NULL = valid in any currency; required for FIXED_AMOUNT (enforced by a
    # DB CHECK constraint, not just app code).
    currency_code: Mapped[str | None] = mapped_column(String(3), ForeignKey("currency.currency_code"), nullable=True)
    max_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_order_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    applicable_program_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("program.program_id"), nullable=True
    )
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_redemptions_per_user: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    times_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PromoCodeRedemption(Base):
    """One row per attempted use, 1:1 with a payment_order. status starts
    'reserved' at order creation (inside the same transaction that locks
    promo_code and increments times_used), moves to 'confirmed' when the
    order is paid, or 'released' if the order fails - see
    app/services/promo_service.py.
    """

    __tablename__ = "promo_code_redemption"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    promo_code_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("promo_code.promo_code_id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("auth_user.id"), nullable=False)
    payment_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_order.id"), nullable=False, unique=True
    )
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currency.currency_code"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="reserved")
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
