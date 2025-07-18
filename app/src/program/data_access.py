from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from src.program.models import Program, ProgramCategory, ProgramType, Review, FAQ
from src.program import models
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

async def get_program_details(program_id: int, country: str, db: Session = Depends(get_db)):
    country_id = db.query(models.Country).filter(
        models.Country.country == country, models.Country.is_active == True
        ).first().country_id

    result = db.query(models.Program, models.ProgramCategory, models.ProgramType, models.ProgramFee)\
                .join(models.ProgramCategory, models.Program.program_category_id == models.ProgramCategory.program_category_id)\
                .join(models.ProgramType, models.Program.program_type_id == models.ProgramType.program_type_id)\
                .join(models.ProgramFee, models.Program.program_id == models.ProgramFee.program_id)\
                .filter(
                    models.Program.is_active == True,
                    models.ProgramType.is_active == True,
                    models.ProgramCategory.is_active == True,
                    models.ProgramFee.is_active == True,
                    models.Program.program_id == program_id,
                    models.ProgramFee.country_id == country_id,
                ).first()

    if result is not None:
        program, program_category, program_type, program_fee = result

        curriculum = db.query(models.Curriculum).filter(
        models.Curriculum.program_id == program_id, models.Curriculum.is_active==True
        ).all()
        
        faq = db.query(models.FAQ).filter(
            models.FAQ.faq_type.in_(["General", program_type.program_type]),
            models.FAQ.is_active==True
            ).all()
        
        program_review = db.query(models.Review).filter(
            models.Review.program_type== program_type.program_type_id,
            models.Review.review_type == program_category.program_category,
            models.Review.is_active == True
            ).all()
        
        program_project = db.query(models.Project).filter(
            models.Project.program_id== program_id,
            models.Project.is_active == True
            ).all()

    if country_id and result and len(program_review) and len(program_project) and len(curriculum) and len(faq):
        return {
            "program_id": program.program_id,
            "program_name": program.program_name,
            "program_sequence": program.program_sequence,
            "tag": program.tag,
            "program_img": program.program_img,
            "program_category": program_category.program_category,
            "program_type": program_type.program_type,
            "program_duration": program.program_duration,
            "program_start_date": program.program_start_date,
            "program_fee": program_fee.program_fee,
            "discount": program_fee.discount,
            "payment_link": program_fee.payment_link,
            "country": country,
            "curriculum": [curriculum_item for curriculum_item in curriculum],
            "faq": [faq_item for faq_item in faq],      
            "program_review": [program_review_item for program_review_item in program_review],
            "program_project": [program_project_item for program_project_item in program_project]
        }


async def get_program_list_by_category(country: str, db: Session = Depends(get_db)):

    response = {}

    country_id = db.query(models.Country.country_id).filter(
        models.Country.country == country, models.Country.is_active == True
        ).first()
    
    if country_id:
        result = db.query(models.Program, models.ProgramCategory, models.ProgramFee)\
                    .join(models.ProgramCategory, models.Program.program_category_id == models.ProgramCategory.program_category_id)\
                    .join(models.ProgramFee, models.Program.program_id == models.ProgramFee.program_id)\
                    .filter(
                        models.Program.is_active == True,
                        models.ProgramCategory.is_active == True,
                        models.ProgramFee.is_active == True,
                        models.ProgramFee.country_id == country_id[0],
                    ).all()
    
        if result:
            for program_data, program_category_data, program_fee_data in result:
                if program_category_data.program_category not in response:
                    response[program_category_data.program_category] = []

                if program_category_data.program_category in response.keys():
                        response[program_category_data.program_category].append({
                            "program_id": program_data.program_id,
                            "program_name": program_data.program_name,
                            "program_sequence": program_data.program_sequence,
                            "tag": program_data.tag,
                            "program_img": program_data.program_img,
                            "program_category": program_category_data.program_category,
                            "program_duration": program_data.program_duration,
                            "program_start_date": program_data.program_start_date,
                            "program_fee": program_fee_data.program_fee,
                            "discount": program_fee_data.discount,
                            "payment_link": program_fee_data.payment_link,
                            "country": country
                        })

            return response

async def get_program_list_by_type(country: str, db: Session = Depends(get_db)):

    response = {}

    country_id = db.query(models.Country.country_id).filter(
        models.Country.country == country, models.Country.is_active == True
        ).first()
    
    if country_id:
        result = db.query(models.Program, models.ProgramType, models.ProgramFee)\
                    .join(models.ProgramType, models.Program.program_type_id == models.ProgramType.program_type_id)\
                    .join(models.ProgramFee, models.Program.program_id == models.ProgramFee.program_id)\
                    .filter(
                        models.Program.is_active == True,
                        models.ProgramType.is_active == True,
                        models.ProgramFee.is_active == True,
                        models.ProgramFee.country_id == country_id[0],
                    ).all()
    
        if result:
            for program_data, program_type_data, program_fee_data in result:
                if program_type_data.program_type not in response:
                    response[program_type_data.program_type] = []

                if program_type_data.program_type in response.keys():
                        response[program_type_data.program_type].append({
                            "program_id": program_data.program_id,
                            "program_name": program_data.program_name,
                            "program_sequence": program_data.program_sequence,
                            "tag": program_data.tag,
                            "program_img": program_data.program_img,
                            "program_category": program_type_data.program_type,
                            "program_duration": program_data.program_duration,
                            "program_start_date": program_data.program_start_date,
                            "program_fee": program_fee_data.program_fee,
                            "discount": program_fee_data.discount,
                            "payment_link": program_fee_data.payment_link,
                            "country": country
                        })

            return response
        
async def get_learning_page_review_list(db: Session = Depends(get_db)):
    result: list[models.Review] = db.query(models.Review).filter(
        models.Review.is_active == True, models.Review.review_type.in_(["Guided Project"])
        ).order_by(models.Review.review_sequence).all()
    if result:
        response = []
        for review_data in result:
            response.append({
                "review_id": review_data.review_id,
                "review_sequence": review_data.review_sequence,
                "reviewer_name": review_data.reviewer_name,
                "review_desc": review_data.review_desc,
                "review_type": review_data.review_type,
                "program_type": review_data.program_type,
                "is_active": review_data.is_active
            })
        return response
    
async def get_learning_page_faq(db: Session = Depends(get_db)):
    result: list[models.FAQ] = db.query(models.FAQ).filter(
        models.FAQ.is_active == True, models.FAQ.faq_type=="General"
        ).order_by(models.FAQ.faq_sequence).all()
    if result:
        response = []
        for faq_data in result:
            response.append({
                "faq_id": faq_data.faq_id,
                "faq_sequence": faq_data.faq_sequence,
                "faq_type": faq_data.faq_type,
                "faq_question": faq_data.faq_question,
                "faq_answer": faq_data.faq_answer,
                "is_active": faq_data.is_active
            })
        return response

async def get_curriculum_by_program_id(program_id:int, db: Session = Depends(get_db)):
    result: list = db.query(models.Curriculum, models.Topic)\
        .join(models.Topic, models.Curriculum.curriculum_id == models.Topic.curriculum_id)\
        .filter(
            models.Curriculum.is_active == True, models.Topic.is_active == True, 
            models.Curriculum.program_id == program_id
        ).order_by(models.Curriculum.program_id).all()
    if result:
        response = {}
        for curriculum_data, topic_data in result:
            topic_dict = {
                "topic_id": topic_data.topic_id,
                "curriculum_id": topic_data.curriculum_id,
                "topic": topic_data.topic,
                "module_id": topic_data.module_id,
                "is_active": topic_data.is_active
            }
            if curriculum_data.curriculum_title not in response:
                response[curriculum_data.curriculum_title] = {
                    "curriculum_id": curriculum_data.curriculum_id,
                    "program_id": curriculum_data.program_id,
                    "module_id": curriculum_data.module_id,
                    "curriculum_title": curriculum_data.curriculum_title,
                    "topic_list": [topic_dict],
                    "is_active": curriculum_data.is_active
                }
            else:
                response[curriculum_data.curriculum_title]["topic_list"].append(topic_dict)
        return response

async def get_project_list(db: Session = Depends(get_db)):
    result: list[models.Project] = db.query(models.Project).filter(
        models.Project.is_active == True
        ).order_by(models.Project.project_sequence).all()
    if result:
        response = []
        for project_data in result:
            response.append({
                "project_id": project_data.project_id,
                "program_id": project_data.program_id,
                "project_title": project_data.project_title,
                "project_description": project_data.project_description,
                "project_outcome": project_data.project_outcome,
                "project_sequence": project_data.project_sequence,
                "project_img": project_data.project_img,
                "project_tag": project_data.project_tag,
                "is_active": project_data.is_active
            })
        return response
    

async def get_program_review_list(db: Session = Depends(get_db)):
    result: list[models.Review] = db.query(models.Review)\
        .filter(models.Review.is_active == True)\
        .order_by(models.Review.review_sequence)\
        .all()
    
    if result:
        response = []
        for review_data in result:
            response.append({
                "review_id": review_data.review_id,
                "review_sequence": review_data.review_sequence,
                "reviewer_name": review_data.reviewer_name,
                "review_desc": review_data.review_desc,
                "review_type": review_data.review_type,
                "program_type": review_data.program_type,
                "is_active": review_data.is_active
            })
        return response

async def get_program_mapping_list(db: Session = Depends(get_db)):
    response = []
    result: list[models.ProgramMapping] = db.query(models.ProgramMapping)\
        .filter(models.ProgramMapping.is_active == True)\
        .all()
    
    if result:
        for program_mapping_data in result:
            response.append({
                "id": program_mapping_data.id,
                "name": program_mapping_data.name,
                "value": program_mapping_data.value,
                "desc": program_mapping_data.desc,
                "is_active": program_mapping_data.is_active
            })
    return response

async def get_image_mapping_list(db: Session = Depends(get_db)):
    response = []
    result: list[models.ImageMapping] = db.query(models.ImageMapping)\
        .filter(models.ImageMapping.is_active == True)\
        .all()
    
    if result:
        for image_mapping_data in result:
            response.append({
                "id": image_mapping_data.id,
                "name": image_mapping_data.name,
                "img_path": image_mapping_data.img_path,
                "desc": image_mapping_data.desc,
                "is_active": image_mapping_data.is_active
            })
    return response

async def get_mentor_list(db: Session = Depends(get_db)):
    response = []
    result: list[models.Mentor] = db.query(models.Mentor)\
        .filter(models.Mentor.is_active == True)\
        .all()
    
    if result:
        for mentor_data in result:
            response.append({
                "mentor_id": mentor_data.mentor_id,
                "name": mentor_data.name,
                "degree": mentor_data.degree,
                "work_exp": mentor_data.work_exp,
                "company": mentor_data.company,
                "university": mentor_data.university,
                "img": mentor_data.img,
                "skills": mentor_data.skills,
                "created_on": mentor_data.created_on,
                "updated_on": mentor_data.updated_on,
                "is_active": mentor_data.is_active,
    })
    return response
