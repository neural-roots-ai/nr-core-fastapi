# program_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.program import data_access as program_db
from src.db import get_db
from logger import trace_execution
from src.constants import ProgramConstants
from src.authentication import dependencies

router = APIRouter(dependencies=[Depends(dependencies.get_current_user)])

@trace_execution
@router.get("/get-program-detail")
async def get_program_details(program_id: int, country, db: Session = Depends(get_db)):
    response = await program_db.get_program_details(program_id, country, db)
    if not response:
        return HTTPException(status_code=404, detail=ProgramConstants.PROGRAM_NOT_FOUND)
    return response

@trace_execution
@router.get("/get-program-list-by-category")
async def get_program_list_by_category(country, db: Session = Depends(get_db)):
    response = await program_db.get_program_list_by_category(country, db)
    if not response:
        return HTTPException(status_code=404, detail=ProgramConstants.PROGRAM_NOT_FOUND)
    return response

@trace_execution
@router.get("/get-program-list-by-type")
async def get_program_list_by_type(country, db: Session = Depends(get_db)):
    response = await program_db.get_program_list_by_type(country, db)
    if not response:
        return HTTPException(status_code=404, detail=ProgramConstants.PROGRAM_NOT_FOUND)
    return response

@trace_execution
@router.get("/get-learning-page-reviews")
async def get_learning_page_review_list(db: Session = Depends(get_db)):
    response = await program_db.get_learning_page_review_list(db)
    if not response:
        return HTTPException(status_code=404, detail=ProgramConstants.REVIEW_NOT_FOUND)
    return response

@trace_execution
@router.get("/get-learning-page-faqs")
async def get_learning_page_faq(db: Session = Depends(get_db)):
    response = await program_db.get_learning_page_faq(db)
    if not response:
        return HTTPException(status_code=404, detail="review not found")
    return response


@trace_execution
@router.get("/get-curriculum-by-program-id")
async def get_curriculum_by_program_id(program_id, db: Session = Depends(get_db)):
    response = await program_db.get_curriculum_by_program_id(program_id, db)
    if not response:
        return HTTPException(status_code=404, detail="review not found")
    return response


@trace_execution
@router.get("/get-project-list")
async def get_project_list(db: Session = Depends(get_db)):
    response = await program_db.get_project_list(db)
    if not response:
        return HTTPException(status_code=404, detail="review not found")
    return response


@trace_execution
@router.get("/get-program-reviews-list")
async def get_program_review_list(db: Session = Depends(get_db)):
    response = await program_db.get_program_review_list(db)
    if not response:
        return HTTPException(status_code=404, detail=ProgramConstants.REVIEW_NOT_FOUND)
    return response


@trace_execution
@router.get("/get-program-mapping-list")
async def get_program_mapping_list(db: Session = Depends(get_db)):
    response = await program_db.get_program_mapping_list(db)
    if not response:
        return HTTPException(status_code=404, detail=ProgramConstants.REVIEW_NOT_FOUND)
    return response

@trace_execution
@router.get("/get-image-mapping-list")
async def get_image_mapping_list(db: Session = Depends(get_db)):
    response = await program_db.get_image_mapping_list(db)
    if not response:
        return HTTPException(status_code=404, detail=ProgramConstants.PROGRAM_FEE_NOT_FOUND)
    return response

@trace_execution
@router.get("/get-mentor-list")
async def get_mentor_list(db: Session = Depends(get_db)):
    response = await program_db.get_mentor_list(db)
    if not response:
        return HTTPException(status_code=404, detail=ProgramConstants.PROGRAM_FEE_NOT_FOUND)
    return response
