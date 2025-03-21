from pydantic import BaseModel
from datetime import datetime
from typing import Optional

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

class ProgramJoinResponse(ProgramBase):
    program_id: int
    created_on: datetime
    updated_on: datetime
    category: ProgramCategoryBase
    type: ProgramTypeBase

    class Config:
        orm_mode = True

class ProgramTypeReviews(ProgramTypeBase):
    program_type_id: int
    created_on: datetime
    updated_on: datetime
    reviews: ReviewDB

    class Config:
        orm_mode = True


class ProgramFeeBase(BaseModel):
    program_id: int
    program_fee: str
    payment_link: str
    country_id: int
    discount: int
    is_active: bool

class ProgramFeeCreate(ProgramFeeBase):
    pass

class ProgramFee(ProgramFeeBase):
    program_fee_id: int
    created_on: datetime
    updated_on: datetime

    class Config:
        orm_mode = True

class ProgramDetailBase(BaseModel):
    program_id: int
    program_desc: str
    median_salary: int
    job_opening: int
    is_active: bool
    faq_id: int
    review_id: int

class ProgramDetailCreate(ProgramDetailBase):
    pass

class ProgramCategorySchema(BaseModel):
    program_category_id: int
    program_category: str
    program_category_sequence: int
    is_active: bool
    created_on: datetime
    updated_on: datetime

    class Config:
        orm_mode = True
