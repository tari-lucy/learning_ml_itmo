from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import Session
from database.database import init_db, get_database_engine
from models.user import User
from models.task import Task
from models.transaction import Transaction
from models.result import Result
from models.ml_model import MLModel

# --- Подготовка данных (переносим seed_data из старого main.py) ---

def seed_data():
    """Создание демо-данных при первом запуске"""
    from services.crud.user import create_user, get_user_by_email
    from services.crud.ml_model import create_ml_model, get_model_by_name
    from services.crud.transaction import top_up_balance
    from models.user import User
    from models.ml_model import MLModel

    engine = get_database_engine()
    with Session(engine) as session:
        # ML-модели
        if not get_model_by_name("whisper", session):
            create_ml_model(MLModel(name="whisper", description="Транскрибация аудио и диаризация спикеров (Replicate)", cost=10.0), session)
            create_ml_model(MLModel(name="summary", description="Краткое саммари совещания на основе транскрипта (vsellm)", cost=5.0), session)

        # Демо-пользователь
        if not get_user_by_email("demo@meeting.ru", session):
            demo = create_user(User(email="demo@meeting.ru", password="demo123", name="Demo User"), session)
            top_up_balance(session, demo.id, 100.0)

        # Администратор
        if not get_user_by_email("admin@meeting.ru", session):
            admin = create_user(User(email="admin@meeting.ru", password="admin123", name="Admin", role="admin"), session)
            top_up_balance(session, admin.id, 500.0)


# --- Жизненный цикл приложения ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Выполняется при старте и остановке сервера"""
    # При старте: создаём таблицы + демо-данные
    init_db()
    seed_data()
    print("Сервер запущен, БД готова")
    yield
    # При остановке (если нужно что-то почистить)
    print("Сервер остановлен")


# --- Создание приложения ---

app = FastAPI(
    title="MeetingScribe API",
    description="AI-секретарь совещаний — REST API",
    version="1.0.0",
    lifespan=lifespan
)

from routes.auth import auth_router
app.include_router(auth_router)

from routes.balance import balance_router
app.include_router(balance_router)

from routes.predict import predict_router
app.include_router(predict_router)

from routes.history import history_router
app.include_router(history_router)

# --- Корневой эндпоинт для проверки ---

@app.get("/")
def root():
    return {"message": "MeetingScribe API работает", "docs": "/docs"}