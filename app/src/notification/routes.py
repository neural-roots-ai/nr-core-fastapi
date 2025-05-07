# program_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.notification import data_acces as notification_data_access
from src.db import get_db
from typing import List, Annotated
import logger 
from src.notification import schemas
from src.authentication import dependencies
from src.users.model import User


router = APIRouter(dependencies=[Depends(dependencies.get_current_user)])

@logger.trace_execution
@router.get("/get-candidate-info-list", response_model=List[schemas.CandidateGetResponse])
async def get_candidate_info_list(skip=0, limit=100,db: Session = Depends(get_db)):
    res = await notification_data_access.get_candidate_info_list(skip, limit, db)
    if not res:
        return HTTPException(status_code=400, detail="No candidate info found")
    return res

@logger.trace_execution
@router.post("/add-candidate-info")
async def add_candidate_info(candidate_form: schemas.CandidateInfoCreate, db: Session = Depends(get_db)):
    res = await notification_data_access.add_candidate_info(candidate_form, db)
    if not res:
        return HTTPException(status_code=400, detail="Respone not found")
    if res.get("status"):
        return res
    return res