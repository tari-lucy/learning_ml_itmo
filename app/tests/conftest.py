import pytest
from typing import Generator, List, Dict, Any
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from main import app
from database.database import get_session
from models.user import User
from models.ml_model import MLModel
from auth.hash_password import HashPassword


# --- 1. Движок тестовой БД ---

@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


# --- 2. Сессия к тестовой БД ---

@pytest.fixture(name="session")
def session_fixture(engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


# --- 3. TestClient с подменой БД ---

@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# --- 4. Seed: ML-модели whisper и summary ---

@pytest.fixture(name="seeded_models")
def seeded_models_fixture(session: Session) -> Dict[str, MLModel]:
    whisper = MLModel(name="whisper", description="Транскрибация (тестовая)", cost=10.0)
    summary = MLModel(name="summary", description="Саммари (тестовая)", cost=5.0)
    session.add(whisper)
    session.add(summary)
    session.commit()
    session.refresh(whisper)
    session.refresh(summary)
    return {"whisper": whisper, "summary": summary}


# --- 5. Тестовый пользователь ---

@pytest.fixture(name="test_user")
def test_user_fixture(session: Session) -> User:
    hasher = HashPassword()
    user = User(email="testuser@test.ru", password=hasher.create_hash("testpass"), name="Test User", role="user", balance=100.0)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# --- 6. Второй юзер (для проверки изоляции данных между пользователями) ---

@pytest.fixture(name="second_user")
def second_user_fixture(session: Session) -> User:
    hasher = HashPassword()
    user = User(email="seconduser@test.ru", password=hasher.create_hash("otherpass"), name="Second User", role="user", balance=50.0)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# --- 7. Авторизованный клиент (test_user залогинен, JWT в заголовке) ---

@pytest.fixture(name="auth_client")
def auth_client_fixture(client: TestClient, test_user: User) -> TestClient:
    response = client.post("/auth/signin", data={"username": test_user.email, "password": "testpass"})
    assert response.status_code == 200, f"Login в auth_client упал: {response.text}"
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


# --- 8. Мок publish_task (не дёргаем RabbitMQ) ---

@pytest.fixture(name="mock_publish_task")
def mock_publish_task_fixture(monkeypatch) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []

    async def fake_publish(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("routes.predict.publish_task", fake_publish)
    return calls


# --- 9. Мок publish_task с имитацией падения RabbitMQ ---

@pytest.fixture(name="mock_publish_task_amqp_error")
def mock_publish_task_amqp_error_fixture(monkeypatch):
    from aio_pika.exceptions import AMQPConnectionError

    async def failing_publish(**kwargs):
        raise AMQPConnectionError("Тестовая имитация: RabbitMQ недоступен")

    monkeypatch.setattr("routes.predict.publish_task", failing_publish)
