from fastapi.testclient import TestClient
from sqlmodel import Session

from models.user import User


FAKE_AUDIO_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x00fake-mp3-content"


def test_history_predictions_empty_for_new_user(auth_client: TestClient):
    """У только что зарегистрированного юзера история ML-запросов пустая."""
    response = auth_client.get("/history/predictions")

    assert response.status_code == 200
    assert response.json() == []


def test_history_predictions_after_whisper(auth_client: TestClient, seeded_models, mock_publish_task):
    """После отправки whisper задача появляется в /history/predictions с нужными полями."""
    auth_client.post("/predict/whisper", files={"audio": ("meeting.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")}, data={"title": "Важная встреча"})

    response = auth_client.get("/history/predictions")

    assert response.status_code == 200
    history = response.json()
    assert len(history) == 1
    assert history[0]["model_name"] == "whisper"
    assert history[0]["title"] == "Важная встреча"
    assert history[0]["status"] == "pending"


def test_history_transactions_after_topup(auth_client: TestClient):
    """После пополнения в /history/transactions появляется запись type=credit."""
    auth_client.post("/balance/topup", json={"amount": 50.0})

    response = auth_client.get("/history/transactions")

    assert response.status_code == 200
    history = response.json()
    assert len(history) == 1
    assert history[0]["type"] == "credit"
    assert history[0]["amount"] == 50.0
    assert history[0]["task_id"] is None


def test_history_transactions_after_topup_and_predict(auth_client: TestClient, seeded_models, mock_publish_task):
    """
    После пополнения и отправки whisper в истории транзакций ДВЕ записи:
    credit (topup) + debit (резерв под задачу).
    """
    auth_client.post("/balance/topup", json={"amount": 50.0})
    predict_response = auth_client.post("/predict/whisper", files={"audio": ("a.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")}, data={"title": ""})
    task_id = predict_response.json()["task_id"]

    response = auth_client.get("/history/transactions")
    history = response.json()

    assert len(history) == 2
    types = {tx["type"] for tx in history}
    assert types == {"credit", "debit"}, f"Ожидали credit + debit, получили {types}"

    debit_tx = next(tx for tx in history if tx["type"] == "debit")
    assert debit_tx["task_id"] == task_id, "Debit-транзакция должна быть связана с задачей"
    assert debit_tx["amount"] == -10.0


def test_history_isolation_between_users(client: TestClient, test_user: User, second_user: User):
    """Юзер A видит только свою историю, юзер B — только свою."""
    login_a = client.post("/auth/signin", data={"username": test_user.email, "password": "testpass"})
    login_b = client.post("/auth/signin", data={"username": second_user.email, "password": "otherpass"})
    token_a = login_a.json()["access_token"]
    token_b = login_b.json()["access_token"]

    # A пополняет себе, B — нет
    client.post("/balance/topup", json={"amount": 200}, headers={"Authorization": f"Bearer {token_a}"})

    history_a = client.get("/history/transactions", headers={"Authorization": f"Bearer {token_a}"}).json()
    history_b = client.get("/history/transactions", headers={"Authorization": f"Bearer {token_b}"}).json()

    assert len(history_a) == 1, "A сделал 1 topup"
    assert len(history_b) == 0, "B не должен видеть операции A"
