"""Tables owned by this service (see sql/002_payment_tables.sql)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import BIGINT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentOrder(Base):
    __tablename__ = "payment_order"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("auth_user.id"), nullable=False, index=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("program.program_id"), nullable=False)
    # Exactly one of program_fee_id (legacy, country-keyed) or program_price_id
    # (new, currency-keyed - see app.db.models.pricing.ProgramPrice) is set,
    # depending on which pricing source resolved this order's amount.
    program_fee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("program_fee.program_fee_id"), nullable=True
    )
    program_price_id: Mapped[int | None] = mapped_column(
        BIGINT, ForeignKey("program_price.program_price_id"), nullable=True
    )
    country_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("country.country_id"), nullable=True)
    razorpay_order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # What Razorpay actually charges/settles (currently always INR - see
    # settings.SETTLEMENT_CURRENCY / RAZORPAY_CHARGE_CURRENCIES).
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_subunits: Mapped[int] = mapped_column(BIGINT, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    # What the buyer was actually shown before checkout (e.g. GBP), which can
    # differ from amount/currency above when Razorpay settlement forces a
    # conversion to INR - see sql/004_payment_order_display_currency.sql.
    display_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    display_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    # Denormalized promo summary for receipts/order history - promo_code_redemption
    # (app.db.models.promo) is the source of truth for enforcement.
    promo_code_id: Mapped[int | None] = mapped_column(BIGINT, ForeignKey("promo_code.promo_code_id"), nullable=True)
    promo_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    receipt: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PaymentTransaction(Base):
    __tablename__ = "payment_transaction"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    payment_order_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("payment_order.id"), nullable=False, index=True
    )
    razorpay_payment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    razorpay_signature: Mapped[str | None] = mapped_column(String(256), nullable=True)
    method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_subunits: Mapped[int] = mapped_column(BIGINT, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    bank: Mapped[str | None] = mapped_column(String(50), nullable=True)
    wallet: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vpa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    card_network: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CourseEnrollment(Base):
    __tablename__ = "course_enrollment"
    __table_args__ = (UniqueConstraint("user_id", "program_id", name="uq_user_program_enrollment"),)

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("auth_user.id"), nullable=False, index=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("program.program_id"), nullable=False)
    payment_order_id: Mapped[int | None] = mapped_column(BIGINT, ForeignKey("payment_order.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    enrolled_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
