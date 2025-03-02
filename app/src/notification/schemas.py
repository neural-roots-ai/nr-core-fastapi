from typing import Optional
from pydantic import BaseModel
from datetime import datetime

# Candidate Info Models and Schemas
class CandidateInfoBase(BaseModel):
    first_name: str
    last_name: str
    work_experience: Optional[str] = None
    email_address: str
    candidate_phone: Optional[str] = None
    country_code: Optional[str] = None
    candidate_country: Optional[str] = None
    qualification: Optional[str] = None
    program_type_id: Optional[int] = None
    program_category_id: Optional[int] = None
    enroll_rource: Optional[str] = None
    is_enrolled: Optional[bool] = None
    enroll_type: Optional[str] = None
    program_id: Optional[int] = None
    is_email_sent_level_0: Optional[bool] = None
    email_level_0_id: Optional[int] = None
    is_email_sent_level_1: Optional[bool] = None
    email_level_1_id: Optional[int] = None
    is_email_sent_level_2: Optional[bool] = None
    email_level_2_id: Optional[int] = None
    is_email_sent_level_3: Optional[bool] = None
    email_level_3_id: Optional[int] = None

class CandidateInfoCreate(CandidateInfoBase):
    created_on: datetime = datetime.now()
    updated_on: datetime = datetime.now()
    is_active: bool = True

class CandidateInfoUpdate(CandidateInfoBase):
    pass

class CandidateCreateResponse(BaseModel):
    candidate_id: int
    class Config:
        orm_mode = True

class CandidateGetResponse(CandidateInfoBase):
    candidate_id: int
    class Config:
        orm_mode = True

# Email Content Models and Schemas
class EmailContentBase(BaseModel):
    email_level: int
    email_from: Optional[str] = None
    subject: str
    content: str
    program_category_id: Optional[int] = None
    program_type_id: Optional[int] = None
    project_id: Optional[int] = None

class EmailContentCreate(EmailContentBase):
    pass

class EmailContentUpdate(EmailContentBase):
    pass

class EmailContent(EmailContentBase):
    email_content_id: int

    class Config:
        orm_mode = True