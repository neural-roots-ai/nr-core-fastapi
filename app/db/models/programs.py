"""Learning-page/catalog tables (owned by the Django app, in NRDB).

Country, ProgramCategory, ProgramType, Program and ProgramFee are already
mapped in app.db.models.catalog (shared with the payments service) - import
those instead of redefining them here, since SQLAlchemy does not allow two
classes to map the same table name against the same declarative base.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Review(Base):
    __tablename__ = "review"

    review_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(50), nullable=False)
    review_desc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    program_type: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FAQ(Base):
    __tablename__ = "faq"

    faq_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faq_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    faq_type: Mapped[str] = mapped_column(String(20), nullable=False)
    faq_question: Mapped[str] = mapped_column(String(100), nullable=False)
    faq_answer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProgramDetail(Base):
    __tablename__ = "program_detail"

    program_detail_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("program.program_id"), nullable=False)
    program_desc: Mapped[str] = mapped_column(String(500), nullable=False)
    median_salary: Mapped[int] = mapped_column(Integer, nullable=False)
    job_opening: Mapped[int] = mapped_column(Integer, nullable=False)
    faq_id: Mapped[int] = mapped_column(Integer, ForeignKey("faq.faq_id"), nullable=False)
    review_id: Mapped[int] = mapped_column(Integer, ForeignKey("review.review_id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Curriculum(Base):
    __tablename__ = "curriculum"

    curriculum_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(Integer, nullable=False)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("program.program_id"), nullable=False)
    curriculum_title: Mapped[str] = mapped_column(String(50), nullable=False)
    topics: Mapped[str | None] = mapped_column(String(500), nullable=True)
    module_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Topic(Base):
    __tablename__ = "topic"

    topic_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum.curriculum_id"), nullable=False)
    module_id: Mapped[int] = mapped_column(Integer, nullable=False)
    topic: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Project(Base):
    __tablename__ = "project"

    project_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("program.program_id"), nullable=False)
    project_title: Mapped[str] = mapped_column(String(100), nullable=False)
    project_description: Mapped[str] = mapped_column(String(500), nullable=False)
    project_outcome: Mapped[str | None] = mapped_column(String(500), nullable=True)
    project_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    project_img: Mapped[str | None] = mapped_column(String(500), nullable=True)
    project_tag: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProgramMapping(Base):
    __tablename__ = "program_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    desc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ImageMapping(Base):
    __tablename__ = "image_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    img_path: Mapped[str] = mapped_column(String(100), nullable=False)
    desc: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Mentor(Base):
    __tablename__ = "mentor"

    mentor_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    degree: Mapped[str | None] = mapped_column(String, nullable=True)
    work_exp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    university: Mapped[str | None] = mapped_column(String, nullable=True)
    img: Mapped[str | None] = mapped_column(String, nullable=True)
    skills: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=True, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
