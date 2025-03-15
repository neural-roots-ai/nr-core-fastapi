from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from src.authentication.utils import verify_password, get_password_hash, create_access_token
from src.authentication.models import TokenData
from src.users.model import User
from settings import SECRET_KEY, ALGORITHM
from logger import trace_execution
from src.db import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

@trace_execution
def get_user(db: Session, username: str):
    user = db.query(User).filter(User.username==username).first()
    return user

@trace_execution
def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username==username).first()
    if not user:
        return False
    verify_password_status = verify_password(password, user.hashed_password)
    if not verify_password_status:
        return False
    return user

@trace_execution
def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


