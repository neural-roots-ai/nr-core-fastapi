from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.users.schemas import User  as UserModel
from src.authentication.dependencies import get_current_user, get_db

router = APIRouter()

@router.get("/me", response_model=UserModel)
def read_users_me(current_user: UserModel = Depends(get_current_user)):
    return current_user
