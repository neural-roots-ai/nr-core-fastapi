from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, TIMESTAMP
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


# SQLAlchemy Models
class ProgramFee(Base):
    __tablename__ = "program_fee"

    program_fee_id = Column(primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("program.program_id"), nullable=False)
    program_fee = Column(String(100), nullable=False)
    payment_link = Column(String(100), nullable=False)
    country_id = Column(Integer, ForeignKey("country.country_id"), nullable=False)
    created_on = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_on = Column(TIMESTAMP(timezone=True), nullable=False)
    discount = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False)

class ProgramDetail(Base):
    __tablename__ = "program_detail"

    program_detail_id = Column(primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("program.program_id"), nullable=False)
    program_desc = Column(String(500), nullable=False)
    median_salary = Column(Integer, nullable=False)
    created_on = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_on = Column(TIMESTAMP(timezone=True), nullable=False)
    job_opening = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False)
    faq_id = Column(Integer, ForeignKey("faq.faq_id"), nullable=False)
    review_id = Column(Integer, ForeignKey("review.review_id"), nullable=False)

class Curriculum(Base):
    __tablename__ = "curriculum"

    curriculum_id = Column(primary_key=True, index=True)
    module_id = Column(Integer, nullable=False)
    program_id = Column(Integer, ForeignKey("program.program_id"), nullable=False)
    curriculum_title = Column(String(50), nullable=False)
    topics = Column(String(500))
    module_duration = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False)
    updated_on = Column(TIMESTAMP(timezone=True), nullable=False)
    created_on = Column(TIMESTAMP(timezone=True), nullable=False)

class Topic(Base):
    __tablename__ = "topic"

    topic_id = Column(primary_key=True, index=True)
    curriculum_id = Column(Integer, ForeignKey("curriculum.curriculum_id"), nullable=False)
    module_id = Column(Integer, nullable=False)
    topic = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False)
    updated_on = Column(TIMESTAMP(timezone=True), nullable=False)
    created_on = Column(TIMESTAMP(timezone=True), nullable=False)

class Project(Base):
    __tablename__ = "project"

    project_id = Column(primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("program.program_id"), nullable=False)
    project_title = Column(String(100), nullable=False)
    project_description = Column(String(500), nullable=False)
    project_outcome = Column(String(500))
    project_sequence = Column(Integer, nullable=False)
    project_img = Column(String(500))
    project_tag = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False)
    updated_on = Column(TIMESTAMP(timezone=True), nullable=False)
    created_on = Column(TIMESTAMP(timezone=True), nullable=False)

class ProgramMapping(Base):
    __tablename__ = "program_mapping"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    value = Column(String(500), nullable=False)
    desc = Column(String(500), nullable=True)  # Optional field
    created_on = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_on = Column(TIMESTAMP(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False)