import os

SECRET_KEY =  os.getenv('SECRET_KEY') # Replace with a strong, random secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

PostgreSQL_ ={
    "user": os.getenv('POSTGRES_DB_USERNAME'),
    "password": os.getenv('POSTGRES_DB_PASSWORD'),
    "host": os.getenv('POSTGRES_DB_HOST'),
    "port": os.getenv('POSTGRES_DB_PORT'),
    "database": "NRDB"
}

DATABASE_URL = f"postgresql://{PostgreSQL_['user']}:{PostgreSQL_['password']}@{PostgreSQL_['host']}:{PostgreSQL_['port']}/{PostgreSQL_['database']}"

SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = os.getenv('SMTP_PORT')
SMTP_USERNAME = os.getenv('POSTGRES_DB_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')