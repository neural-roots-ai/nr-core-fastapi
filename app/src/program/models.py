from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db import Base

class ProgramCategory(Base):
    __tablename__ = "program_category"
    program_category_id = Column(Integer, primary_key=True, index=True)
    program_category = Column(String(50))
    program_category_sequence = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False)
    created_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    programs = relationship("Program", back_populates="category")

class ProgramType(Base):
    __tablename__ = "program_type"
    program_type_id = Column(Integer, primary_key=True, index=True)
    program_type_sequence = Column(Integer, nullable=False)
    program_type = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False)
    created_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    programs = relationship("Program", back_populates="type")

class Program(Base):
    __tablename__ = "program"
    program_id = Column(Integer, primary_key=True, index=True)
    program_name = Column(String(50), nullable=False)
    program_sequence = Column(Integer, nullable=False)
    tag = Column(String(100), nullable=False)
    program_img = Column(String(100), nullable=False)
    program_category_id = Column(Integer, ForeignKey("program_category.program_category_id"), nullable=False)
    program_type_id = Column(Integer, ForeignKey("program_type.program_type_id"), nullable=False)
    program_duration = Column(String(2), nullable=False)
    program_start_date = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, nullable=False)
    created_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    category = relationship("ProgramCategory", back_populates="programs")
    type = relationship("ProgramType", back_populates="programs")

class Review(Base):
    __tablename__ = "review"
    review_id = Column(Integer, primary_key=True, index=True)
    review_sequence = Column(Integer, nullable=False)
    review_type = Column(String(20), nullable=False)
    reviewer_name = Column(String(50), nullable=False)
    review_desc = Column(String(500))
    program_type = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False)
    created_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class FAQ(Base):
    __tablename__ = "faq"
    faq_id = Column(Integer, primary_key=True, index=True)
    faq_sequence = Column(Integer, nullable=False)
    faq_type = Column(String(20), nullable=False)
    faq_question = Column(String(100), nullable=False)
    faq_answer = Column(String(500))
    is_active = Column(Boolean, nullable=False)
    updated_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class Country(Base):
    __tablename__ = "country"
    country_id = Column(Integer, primary_key=True, index=True)
    country = Column(String(50), nullable=False)
    created_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, nullable=False)
