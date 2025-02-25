from pydantic import BaseModel
from datetime import datetime

class ProgramCategoryBase(BaseModel):
    program_category: str | None = None
    program_category_sequence: int
    is_active: bool

class ProgramTypeBase(BaseModel):
    program_type_sequence: int
    program_type: str
    is_active: bool

class ProgramBase(BaseModel):
    program_name: str
    program_sequence: int
    tag: str
    program_img: str
    program_category_id: int
    program_type_id: int
    program_duration: str
    program_start_date: datetime
    is_active: bool

class ReviewBase(BaseModel):
    review_sequence: int
    review_type: str
    reviewer_name: str
    review_desc: str | None = None
    program_type: int
    is_active: bool

class FAQBase(BaseModel):
    faq_sequence: int
    faq_type: str
    faq_question: str
    faq_answer: str | None = None
    is_active: bool

class CountryBase(BaseModel):
    country: str
    is_active: bool

class ProgramCategoryDB(ProgramCategoryBase):
    program_category_id: int
    created_on: datetime
    updated_on: datetime

    class Config:
        orm_mode = True

class ProgramTypeDB(ProgramTypeBase):
    program_type_id: int
    created_on: datetime
    updated_on: datetime

    class Config:
        orm_mode = True

class ProgramDB(ProgramBase):
    program_id: int
    created_on: datetime
    updated_on: datetime

    class Config:
        orm_mode = True

class ReviewDB(ReviewBase):
    review_id: int
    created_on: datetime
    updated_on: datetime

    class Config:
        orm_mode = True

class FAQDB(FAQBase):
    faq_id: int
    created_on: datetime
    updated_on: datetime

    class Config:
        orm_mode = True

class CountryDB(CountryBase):
    country_id: int
    created_on: datetime
    updated_on: datetime

    class Config:
        orm_mode = True