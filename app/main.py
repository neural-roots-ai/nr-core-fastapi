import uvicorn
from fastapi import FastAPI
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from src.authentication.routes import router as auth_router
from src.users.routes import router as users_router
from src.program.routes import router as program_router
from src.notification.routes import router as notification_router
#from apscheduler.schedulers.background import BackgroundScheduler
#from src.notification.data_acces import email_job_scheduler_level
#from src.db import get_db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(program_router, prefix="/program", tags=["program"])
app.include_router(notification_router, prefix="/notification", tags=["notification"])

# @app.on_event("startup")
# def init_data():
#     scheduler = BackgroundScheduler()
#     job_name = "email_scheduler"
#     is_email_sent_level_1 = False
#     is_email_sent_level_2 = False
#     is_email_sent_level_3 = False
#     db = next(get_db())
#     args_level_1 = [job_name, db, False, False, False, 3]
#     args_level_2 = [job_name, db, True, False, False, 6]
#     args_level_3 = [job_name, db, True, True, False, 10]

#     scheduler.add_job(email_job_scheduler_level, 'cron', second='*/5', args=args_level_1)
#     scheduler.add_job(email_job_scheduler_level, 'cron', second='*/5', args=args_level_2)
#     scheduler.add_job(email_job_scheduler_level, 'cron', second='*/5', args=args_level_3)
#     scheduler.start()

@app.get("/")
def read_root():
    return {"message": "Welcome to FastAPI authentication and authorization example"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)