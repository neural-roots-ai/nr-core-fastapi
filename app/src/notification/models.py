from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, Time
from src.db import Base
from sqlalchemy.sql import func
from datetime import datetime, timezone


class CandidateInfo(Base):
    __tablename__ = "candidate_info"

    candidate_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(15), nullable=False)
    last_name = Column(String(15), nullable=False)
    work_experience = Column(String(5))
    email_address = Column(String(250), nullable=False, unique=True)
    candidate_phone = Column(String(15), unique=True)
    country_code = Column(String(5))
    candidate_country = Column(String(20))
    qualification = Column(String(20))
    program_type_id = Column(Integer)
    program_category_id = Column(Integer)
    enroll_rource = Column(String(20))
    is_enrolled = Column(Boolean)
    enroll_type = Column(String(20))
    program_id = Column(Integer)
    is_email_sent_level_0 = Column(Boolean)
    email_level_0_id = Column(Integer)
    is_email_sent_level_1 = Column(Boolean)
    email_level_1_id = Column(Integer)
    is_email_sent_level_2 = Column(Boolean)
    email_level_2_id = Column(Integer)
    is_email_sent_level_3 = Column(Boolean)
    email_level_3_id = Column(Integer)
    created_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, nullable=False)


class EmailContent(Base):
    __tablename__ = "email_content"

    email_content_id = Column(Integer, primary_key=True, index=True)
    email_level = Column(Integer, nullable=False)
    email_from = Column(String(50))
    subject = Column(String(100), nullable=False)
    content = Column(String(2000), nullable=False)
    program_category_id = Column(Integer)
    program_type_id = Column(Integer)
    project_id = Column(Integer)
    created_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_on = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, nullable=False)

class JobScheduler(Base):
    __tablename__ = 'job_scheduler'
    job_id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(20), nullable=False)
    job_description = Column(String(100))
    created_on = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)
    updated_on = Column(DateTime(timezone=True), onupdate=datetime.now(timezone.utc))
    is_active = Column(Boolean, nullable=False)


class JobExecution(Base):
    __tablename__ = 'job_execution'
    job_execution_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, nullable=False)
    job_start_time = Column(DateTime(timezone=True), nullable=False)
    job_end_time = Column(Time(timezone=True))
    job_name = Column(String, nullable=False)
    job_error_desc = Column(String)