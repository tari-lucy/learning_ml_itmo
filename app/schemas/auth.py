from pydantic import BaseModel, Field

# Что приходит при регистрации
class UserCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="Email пользователя")
    password: str = Field(..., min_length=4, description="Пароль (минимум 4 символа)")
    name: str = Field(..., description="Имя пользователя")

# Что приходит при авторизации
class UserLogin(BaseModel):
    email: str
    password: str

# Что возвращаем (БЕЗ пароля!)
class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str

    class Config:
        from_attributes = True