import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models.user import User
from auth.hash_password import HashPassword


# --- SIGNUP ---

def test_signup_success(client: TestClient, session: Session):
    """Регистрация нового юзера: 201, юзер в БД, balance=0, роль по умолчанию 'user'."""
    response = client.post("/auth/signup", json={"email": "newuser@test.ru", "password": "strongpass", "name": "Новый Юзер"})

    assert response.status_code == 201, f"Ожидали 201, получили {response.status_code}: {response.text}"
    data = response.json()
    assert data["email"] == "newuser@test.ru"
    assert data["name"] == "Новый Юзер"
    assert data["role"] == "user"

    user_in_db = session.exec(select(User).where(User.email == "newuser@test.ru")).first()
    assert user_in_db is not None, "Юзер не появился в БД после signup"
    assert user_in_db.balance == 0.0, "Новый юзер должен иметь balance=0"


def test_signup_hashes_password(client: TestClient, session: Session):
    """Пароль в БД должен быть хэширован (bcrypt), не в чистом виде."""
    plain_password = "mysecret123"
    client.post("/auth/signup", json={"email": "hashtest@test.ru", "password": plain_password, "name": "Hash Test"})

    user_in_db = session.exec(select(User).where(User.email == "hashtest@test.ru")).first()
    assert user_in_db.password != plain_password, "Пароль не должен сохраняться в plain text"
    assert user_in_db.password.startswith("$2"), "Ожидали bcrypt-хэш (начинается с $2)"
    assert HashPassword().verify_hash(plain_password, user_in_db.password) is True


def test_signup_duplicate_email_rejected(client: TestClient, test_user: User):
    """Регистрация с уже занятым email → 409."""
    response = client.post("/auth/signup", json={"email": test_user.email, "password": "anypass", "name": "Дубликат"})

    assert response.status_code == 409
    assert "уже существует" in response.json()["detail"].lower()


@pytest.mark.parametrize("invalid_payload,description", [
    ({"email": "not-an-email", "password": "somepass", "name": "Valid Name"}, "невалидный email"),
    ({"email": "ok@test.ru", "password": "abc", "name": "Valid Name"}, "пароль короче 4 символов"),
    ({"email": "ok@test.ru", "password": "somepass", "name": "A"}, "имя короче 2 символов"),
])
def test_signup_invalid_input_rejected(client: TestClient, invalid_payload, description):
    """Pydantic-валидация схемы UserCreate: невалидные данные → 422."""
    response = client.post("/auth/signup", json=invalid_payload)
    assert response.status_code == 422, f"Ожидали 422 на «{description}», получили {response.status_code}"


# --- SIGNIN ---

def test_signin_success(client: TestClient, test_user: User):
    """Вход под существующим юзером: 200 и полный набор полей в ответе."""
    response = client.post("/auth/signin", data={"username": test_user.email, "password": "testpass"})

    assert response.status_code == 200, f"Ожидали 200, получили {response.status_code}: {response.text}"
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user_id"] == test_user.id
    assert data["name"] == test_user.name
    assert data["role"] == test_user.role


def test_signin_is_repeatable(client: TestClient, test_user: User):
    """Повторная авторизация работает — каждый раз выдаётся валидный токен."""
    first = client.post("/auth/signin", data={"username": test_user.email, "password": "testpass"})
    second = client.post("/auth/signin", data={"username": test_user.email, "password": "testpass"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["user_id"] == second.json()["user_id"] == test_user.id


def test_signin_wrong_password_rejected(client: TestClient, test_user: User):
    """Правильный email, неверный пароль → 403."""
    response = client.post("/auth/signin", data={"username": test_user.email, "password": "wrongpassword"})
    assert response.status_code == 403


# --- ЗАЩИТА ЭНДПОИНТОВ ---

def test_protected_endpoint_without_token(client: TestClient):
    """Защищённый эндпоинт без Authorization-заголовка → 401."""
    response = client.get("/balance/")
    assert response.status_code == 401


def test_protected_endpoint_with_broken_token(client: TestClient):
    """Битый JWT-токен → 400 (ловит jose.JWTError)."""
    response = client.get("/balance/", headers={"Authorization": "Bearer this-is-not-a-real-jwt"})
    assert response.status_code == 400


def test_protected_endpoint_with_expired_token(client: TestClient, test_user: User):
    """Истёкший JWT-токен → 403 (отдельная ветка в verify_access_token, не JWTError)."""
    import time
    from jose import jwt
    from database.config import get_settings

    settings = get_settings()
    expired_payload = {"user_id": test_user.id, "expires": time.time() - 10}
    expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    response = client.get("/balance/", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 403, f"Ожидали 403 на истёкший токен, получили {response.status_code}"
    assert "истёк" in response.json()["detail"].lower()
