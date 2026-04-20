from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from database.database import get_session
from services.crud.user import create_user, get_user_by_email
from models.user import User
from schemas.auth import UserCreate, UserResponse
from auth.hash_password import HashPassword
from auth.jwt_handler import create_access_token

auth_router = APIRouter(prefix="/auth", tags=["Авторизация"])
hash_password = HashPassword()


@auth_router.post("/signup", response_model=UserResponse, status_code=201)
def signup(user_data: UserCreate, session: Session = Depends(get_session)):
    """Регистрация нового пользователя"""
    existing = get_user_by_email(user_data.email, session)
    if existing:
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")

    hashed = hash_password.create_hash(user_data.password)
    new_user = User(email=user_data.email, password=hashed, name=user_data.name)
    return create_user(new_user, session)


@auth_router.post("/signin")
def signin(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    """Авторизация → возвращает JWT-токен"""
    user = get_user_by_email(form_data.username, session)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if not hash_password.verify_hash(form_data.password, user.password):
        raise HTTPException(status_code=403, detail="Неверный пароль")

    access_token = create_access_token(user.id)
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id, "name": user.name, "role": user.role}