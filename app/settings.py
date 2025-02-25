SECRET_KEY = "1ff3eec8197cbf1a294e20a1c590155f2d0bdd2a5528495c2ab858ca1e45ba15"  # Replace with a strong, random secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

PostgreSQL_ ={
    "user": "neural_roots_stage",
    "password": "neuralroots",
    "host": "vps.neuralroots.in",
    "port": "5430",
    "database": "NRDB"
}
DATABASE_URL = f"postgresql://{PostgreSQL_['user']}:{PostgreSQL_['password']}@{PostgreSQL_['host']}:{PostgreSQL_['port']}/{PostgreSQL_['database']}"
