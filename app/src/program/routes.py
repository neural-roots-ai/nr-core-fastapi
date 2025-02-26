# program_routes.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.program import data_access as program_data_access
from src.db import get_db
from src.program.schemas import ProgramDB, ProgramCategoryDB, ProgramJoinResponse, ProgramTypeReviews, FAQDB
from typing import List
from logger import trace_execution


router = APIRouter()

@trace_execution
@router.delete("/programs/{program_id}", response_model=ProgramDB)
async def delete_program(program_id: int, db: Session = Depends(get_db)):
    return program_data_access.delete_program(program_id, db)

@trace_execution
@router.get("/programs/", response_model=List[ProgramDB])
async def read_programs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db),):
    return program_data_access.read_programs(skip, limit, db)

@trace_execution
@router.get("/program-list-by-program-type/", response_model=List[ProgramDB])
async def get_program_list_by_program_type(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return program_data_access.get_program_list_by_program_type(skip, limit, db)

@trace_execution
@router.get("/program-list-by-program-category/", response_model=List[ProgramDB])
async def get_program_list_by_program_category(sample: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return program_data_access.get_program_list_by_program_category(sample, skip, limit, db)

@trace_execution
@router.get("/program-list-by-type-and-category/", response_model=List[ProgramJoinResponse])
async def get_programs_list_by_type_and_category(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return program_data_access.get_programs_list_by_type_and_category(skip, limit, db)

@trace_execution
@router.get("/programtype-list", response_model= List[ProgramTypeReviews])
async def get_programtype_and_reviews(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return program_data_access.get_programtype_and_reviews(skip, limit, db)

@trace_execution
@router.get("/faqs", response_model= List[FAQDB])
async def get_faqs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return program_data_access.get_faqs(skip, limit, db)