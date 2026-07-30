"""Existing course-catalog tables (owned by the Django app).

Only the columns this service actually needs are mapped. Read-mostly:
this service never writes to these tables.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Country(Base):
    __tablename__ = "country"

    country_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProgramCategory(Base):
    __tablename__ = "program_category"

    program_category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    program_category_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProgramType(Base):
    __tablename__ = "program_type"

    program_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_type: Mapped[str] = mapped_column(String(50), nullable=False)
    program_type_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Program(Base):
    __tablename__ = "program"

    program_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_name: Mapped[str] = mapped_column(String(100), nullable=False)
    program_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    program_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    program_img: Mapped[str | None] = mapped_column(String(100), nullable=True)
    program_category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("program_category.program_category_id"), nullable=False
    )
    program_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("program_type.program_type_id"), nullable=False
    )
    program_duration: Mapped[str] = mapped_column(String(2), nullable=False)
    program_start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProgramFee(Base):
    __tablename__ = "program_fee"

    program_fee_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("program.program_id"), nullable=False)
    program_fee: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_link: Mapped[str] = mapped_column(String(100), nullable=False)
    country_id: Mapped[int] = mapped_column(Integer, ForeignKey("country.country_id"), nullable=False)
    discount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
