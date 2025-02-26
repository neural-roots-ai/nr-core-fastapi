from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from src.program.models import Program, ProgramCategory, ProgramType, Review
from typing import List
from src.db import get_db

def create_program(program, db):
    db_program = Program(**program.dict())
    db.add(db_program)
    db.commit()
    db.refresh(db_program)
    return db_program

def read_program(program_id, db):
    db_program = db.query(Program).filter(Program.program_id == program_id).first()
    if db_program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return db_program

def update_program(program_id: int, program, db):
    db_program = db.query(Program).filter(Program.program_id == program_id).first()
    if db_program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    for key, value in program.dict(exclude_unset=True).items():
        setattr(db_program, key, value)
    db.commit()
    db.refresh(db_program)
    return db_program

def delete_program(program_id: int, db):
    db_program = db.query(Program).filter(Program.program_id == program_id).first()
    if db_program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    db.delete(db_program)
    db.commit()
    return db_program

def read_programs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db),):
    programs = db.query(Program).offset(skip).limit(limit).all()
    return programs

def get_program_list_by_program_type(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    programs = db.query(Program).filter(Program.program_type_id == 1).order_by(Program.program_sequence)\
        .offset(skip).limit(limit).all()
    return programs

def get_program_list_by_program_category(program_category_id, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):  
    programs = db.query(Program).filter(Program.program_category_id == program_category_id)\
        .offset(skip).limit(limit).all()
    return programs

def get_programs_list_by_type_and_category(skip, limit, db):
    programs = db.query(Program).join(ProgramType, Program.program_type_id == ProgramType.program_type_id)\
              .join(ProgramCategory, Program.program_category_id == ProgramCategory.program_category_id)\
              .filter(Program.is_active == True).order_by(Program.program_sequence)\
              .offset(skip).limit(limit).all()
    return programs

def get_programtype_and_reviews(skip, limit, db):
    programs = db.query(ProgramType).join(Review, Review.program_type == ProgramType.program_type_id)\
               .order_by(ProgramType.program_type_sequence)\
               .offset(skip).limit(limit).all()
    return programs