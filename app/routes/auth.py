from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from database.database import get_session
from services.crud.user import create_user, get_user_by_email
from models.user import User
from schemas.auth import UserCreate, UserLogin, UserResponse

auth_router = APIRouter(prefix="/auth", tags=["Авторизация"])

@auth_router.post("/signup", response_model=UserResponse, status_code=201)
def signup(user_data: UserCreate, session: Session = Depends(get_session)):
    """Регистрация нового пользователя"""

    # 1. Проверяем: может, такой email уже есть?
    existing = get_user_by_email(user_data.email, session)
    if existing:
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")

    # 2. Создаём пользователя (используем CRUD из services — не дублируем логику!)
    new_user = User(email=user_data.email, password=user_data.password, name=user_data.name)
    created = create_user(new_user, session)

    # 3. Возвращаем (FastAPI автоматически отфильтрует через UserResponse — без пароля)
    return created

@auth_router.post("/signin")
def signin(credentials: UserLogin, session: Session = Depends(get_session)):
    """Авторизация пользователя"""

    # 1. Ищем пользователя
    user = get_user_by_email(credentials.email, session)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # 2. Проверяем пароль (пока без хэширования — JWT будет позже)
    if user.password != credentials.password:
        raise HTTPException(status_code=403, detail="Неверный пароль")

    # 3. Успех
    return {"message": "Авторизация успешна", "user_id": user.id, "role": user.role}
