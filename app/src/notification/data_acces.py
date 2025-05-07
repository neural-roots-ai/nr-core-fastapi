import psycopg2
from src.notification import models
import logger
from datetime import datetime, timezone, timedelta
from src.notification.core import email_notification
 
@logger.trace_execution
def get_candidate_info_list(skip, limit, db, *args, **kwargs):
    candidate_list = db.query(models.CandidateInfo).where(models.CandidateInfo.is_active==True)

    if not candidate_list:
        return None
    return candidate_list

def get_candidate_info_list_(skip, limit, db, *args, **kwargs):
    candidate_list = db.query(models.CandidateInfo).filter(models.CandidateInfo.is_active==True)\
                        .order_by(models.CandidateInfo.updated_on)\
                        .offset(skip).limit(limit).all()
    if not candidate_list:
        return None
    return candidate_list

@logger.trace_execution
async def add_candidate_info(candidate_form, db):
    email_level = 0
    try:
        candidate = models.CandidateInfo(**candidate_form.dict())
        status, email_content=get_email_content(
            email_level, candidate.program_type_id, candidate.program_category_id, db
            )
        
        candidate_exists = db.query(models.CandidateInfo).filter(
            models.CandidateInfo.email_address == candidate.email_address,
            models.CandidateInfo.is_active==True).first()
        
        if candidate_exists:
            email_notification.send_email(candidate, email_content)
            return {"status": True, "message": "Candidate already exists"}
        
        if status:
            candidate.is_email_sent_level_0 = True
            candidate.email_level_0_id = email_content.email_content_id
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            email_notification.send_email(candidate, email_content)
            return candidate

    except Exception as e:
        db.rollback()
        return None

@logger.trace_execution
def get_email_content(email_level, program_type__id, program_category_id, db):
    status = False
    if (program_type__id and program_category_id and email_level) is not None:
        email_content = db.query( models.EmailContent)\
            .filter(models.EmailContent.email_level==email_level, 
            models.EmailContent.program_type_id==program_type__id,
            models.EmailContent.program_category_id==program_category_id,
            models.EmailContent.is_active==True).first()    
        status=True
           
    elif (program_category_id and email_level) is not None and program_type__id is None:
        email_content = db.query(
            models.EmailContent).filter(models.EmailContent.email_level==email_level,
            models.EmailContent.program_category_id==program_category_id,
            models.EmailContent.is_active==True).first()
        status=True
        
    elif program_type__id and email_level and program_category_id is None:
        email_content = db.query(
            models.EmailContent).filter(models.EmailContent.email_level==email_level, 
            models.EmailContent.program_type_id==program_type__id,
            models.EmailContent.is_active==True).first()
        status=True

    elif (program_type__id or email_level or program_category_id) is None:
        email_content = db.query(models.EmailContent)\
            .filter(
                models.EmailContent.email_level==email_level,
                models.EmailContent.is_active==True
                ).first()
        status=True
    else:
        email_content = None
        status=False

    return status, email_content

@logger.trace_execution
def email_job_scheduler_level(job_name, db, is_email_sent_level_1, is_email_sent_level_2, is_email_sent_level_3, days):

    email_job_scheduler = db.query(models.JobScheduler).filter(models.JobScheduler.job_name == job_name, models.JobScheduler.is_active == True).first()
    
    job_execution = models.JobExecution()
    job_execution.job_name = job_name
    job_execution.job_id = email_job_scheduler.job_id
    job_execution.job_start_time = datetime.now(timezone.utc)
    db.add(job_execution)
    db.commit()
    db.refresh(job_execution)

    if email_job_scheduler:
        # check do we have any email to send
        candidate_list = db.query(models.CandidateInfo) \
            .filter(
            models.CandidateInfo.is_active == True,
            models.CandidateInfo.is_email_sent_level_0 == True,
            models.CandidateInfo.is_email_sent_level_1 == (is_email_sent_level_1 or None) ,
            models.CandidateInfo.is_email_sent_level_2 == (is_email_sent_level_2 or None),
            models.CandidateInfo.is_email_sent_level_3 == (is_email_sent_level_3 or None)
        ).all()

        for candidate in candidate_list:
            if candidate.created_on.date() + timedelta(days=days) == datetime.now(timezone.utc).date():
                email_level, email_content_status, email_content = get_email_level_and_content(candidate, db)
                if email_content_status:
                    email_notification.send_email(
                        candidate, email_content.subject, body=email_content.content
                    )
                    db.query(models.CandidateInfo).filter(models.CandidateInfo.email_address == candidate.email_address).update(
                            {
                                f"is_email_sent_level_{email_level}": True,
                                f"email_level_{email_level}_id": email_content.email_content_id
                            }
                        )
                    db.commit()
                    db.refresh(candidate)

        db.query(models.JobExecution).filter(models.JobExecution.job_execution_id==job_execution.job_execution_id)\
            .update({"job_end_time": datetime.now(timezone.utc)})
        db.commit()

@logger.trace_execution
def get_email_level_and_content(candidate, db):
    if not candidate.is_email_sent_level_1:
        email_level = 1
    elif not candidate.is_email_sent_level_2:
        email_level = 2
    elif not candidate.is_email_sent_level_3:
        email_level = 3
    else:
        return -1, False, None

    email_content_status, email_content = get_email_content(
        email_level, candidate.program_type_id, candidate.program_category_id, db
    )
    return email_level, email_content_status, email_content


