import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models.user import User
from models.transaction import Transaction, TransactionStatus


def test_get_balance_of_new_user_is_zero(client: TestClient):
    """Только что зарегистрированный юзер видит balance=0."""
    client.post("/auth/signup", json={"email": "freshuser@test.ru", "password": "freshpass", "name": "Свежий Юзер"})
    login = client.post("/auth/signin", data={"username": "freshuser@test.ru", "password": "freshpass"})
    token = login.json()["access_token"]

    response = client.get("/balance/", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["balance"] == 0.0


def test_topup_success(auth_client: TestClient):
    """POST /balance/topup возвращает сообщение и новый баланс."""
    response = auth_client.post("/balance/topup", json={"amount": 50.0})

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["new_balance"] == 150.0, "100 (стартовый) + 50 = 150"


def test_topup_updates_balance_visible_in_get(auth_client: TestClient):
    """После topup GET /balance возвращает обновлённое значение."""
    auth_client.post("/balance/topup", json={"amount": 30.0})
    response = auth_client.get("/balance/")

    assert response.status_code == 200
    assert response.json()["balance"] == 130.0


def test_topup_accumulates(auth_client: TestClient):
    """Несколько topup подряд — суммы складываются корректно."""
    auth_client.post("/balance/topup", json={"amount": 10.0})
    auth_client.post("/balance/topup", json={"amount": 20.0})
    auth_client.post("/balance/topup", json={"amount": 5.0})

    response = auth_client.get("/balance/")
    assert response.json()["balance"] == 135.0, "100 + 10 + 20 + 5 = 135"


def test_topup_creates_credit_transaction(auth_client: TestClient, test_user: User, session: Session):
    """Каждый topup создаёт Transaction с type=credit, status=confirmed, task_id=None."""
    auth_client.post("/balance/topup", json={"amount": 77.0})

    transactions = session.exec(select(Transaction).where(Transaction.user_id == test_user.id)).all()
    assert len(transactions) == 1
    tx = transactions[0]
    assert tx.amount == 77.0
    assert tx.type == "credit"
    assert tx.status == TransactionStatus.CONFIRMED.value
    assert tx.task_id is None, "Пополнение не связано с задачей"


@pytest.mark.parametrize("invalid_amount,description", [
    (0, "нулевая сумма"),
    (-100, "отрицательная сумма"),
])
def test_topup_invalid_amount_rejected(auth_client: TestClient, invalid_amount, description):
    """Pydantic-валидация: amount должен быть > 0. Защита от «пополнения в минус»."""
    response = auth_client.post("/balance/topup", json={"amount": invalid_amount})
    assert response.status_code == 422, f"Ожидали 422 на «{description}», получили {response.status_code}"


@pytest.mark.parametrize("method,path", [
    ("GET", "/balance/"),
    ("POST", "/balance/topup"),
])
def test_balance_requires_auth(client: TestClient, method, path):
    """Все эндпоинты баланса требуют JWT — без него 401."""
    response = client.request(method, path, json={"amount": 100} if method == "POST" else None)
    assert response.status_code == 401


def test_balance_isolation_between_users(client: TestClient, test_user: User, second_user: User):
    """Видит ли юзер А не видит баланс юзера B, и topup от A не меняет баланс B """
    login_a = client.post("/auth/signin", data={"username": test_user.email, "password": "testpass"})
    login_b = client.post("/auth/signin", data={"username": second_user.email, "password": "otherpass"})
    token_a = login_a.json()["access_token"]
    token_b = login_b.json()["access_token"]

    client.post("/balance/topup", json={"amount": 200}, headers={"Authorization": f"Bearer {token_a}"})

    balance_a = client.get("/balance/", headers={"Authorization": f"Bearer {token_a}"}).json()
    balance_b = client.get("/balance/", headers={"Authorization": f"Bearer {token_b}"}).json()

    assert balance_a["balance"] == 300.0, "A: 100 + 200 = 300"
    assert balance_b["balance"] == 50.0, "B не должен меняться от действий A"
