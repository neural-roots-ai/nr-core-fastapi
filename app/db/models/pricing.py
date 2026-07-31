"""Regional/multi-currency pricing tables (owned by this service, see
sql/003_currency_pricing.sql). Additive - does not touch any Django-owned
catalog table (country, program, program_fee, ...).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Currency(Base):
    __tablename__ = "currency"

    currency_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    currency_name: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    decimal_digits: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CountryCurrencyMap(Base):
    """Keyed by ISO 3166-1 alpha-2 country_code - what geo_service resolves
    from IP/CDN headers. `country_id` is an optional bridge to the
    Django-owned `country` table, used only by the legacy country_id-based
    program_fee fallback (see sql/003_currency_pricing.sql).
    """

    __tablename__ = "country_currency_map"

    country_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currency.currency_code"), nullable=False)
    country_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("country.country_id"), nullable=True, unique=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProgramPrice(Base):
    """Admin-managed regional price list: one row per (program, currency).

    Fixed amounts, not live FX conversions - see sql/003_currency_pricing.sql
    for the rationale. This is the source of truth for get_program_fee_details/
    create_order; the legacy per-country `program_fee` table is only used as a
    fallback for programs/currencies that haven't been backfilled here yet.
    """

    __tablename__ = "program_price"
    __table_args__ = (UniqueConstraint("program_id", "currency_code", name="uq_program_price_program_currency"),)

    program_price_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("program.program_id"), nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currency.currency_code"), nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
