import os


print("*"*100)
print("*"*100)
print("*"*100)
print(os.getenv('POSTGRES_DB_USERNAME'))
print(os.getenv('POSTGRES_DB_PASSWORD'))
print(os.getenv('POSTGRES_DB_HOST'))
print(os.getenv('POSTGRES_DB_PORT'))
print(os.getenv('FAST_API_SECRET_KEY'))
print(os.getenv('SMTP_SERVER'))
print(os.getenv('SMTP_PORT'))
print(os.getenv('SMTP_USERNAME'))
print(os.getenv('SMTP_PASSWORD'))
print("*"*100)
print("*"*100)
print("*"*100)


SECRET_KEY =  os.getenv('FAST_API_SECRET_KEY') # Replace with a strong, random secret key
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
SMTP_PORT = os.getenv('SMTP_PORT')  # For TLS
SMTP_USERNAME = os.getenv('POSTGRES_DB_USERNAME') # Your email address
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD') # Your email password or app password (recommended)