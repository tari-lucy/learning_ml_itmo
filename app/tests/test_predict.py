from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models.user import User
from models.task import Task, TaskStatus
from models.result import Result
from models.transaction import Transaction, TransactionStatus


# Фейковый mp3-файл для тестов
FAKE_AUDIO_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x00fake-mp3-content"


# --- POST /predict/whisper — успешный сценарий ---

def test_whisper_success_returns_202(auth_client: TestClient, seeded_models, mock_publish_task):
    """Успешная отправка на транскрибацию возвращает 202 и данные задачи."""
    response = auth_client.post("/predict/whisper", files={"audio": ("test.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")}, data={"title": "Тестовая встреча"})

    assert response.status_code == 202, f"Ожидали 202, получили {response.status_code}: {response.text}"
    data = response.json()
    assert "task_id" in data
    assert data["model_name"] == "whisper"
    assert data["credits_charged"] == 10.0
    assert data["status"] == "pending"


def test_whisper_creates_task_in_db(auth_client: TestClient, seeded_models, mock_publish_task, session: Session, test_user: User):
    """После POST в БД появляется Task с нужными полями и статусом pending."""
    response = auth_client.post("/predict/whisper", files={"audio": ("meeting.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")}, data={"title": "Планёрка"})
    task_id = response.json()["task_id"]

    task = session.get(Task, task_id)
    assert task is not None, "Task не создался в БД"
    assert task.user_id == test_user.id
    assert task.model_id == seeded_models["whisper"].id
    assert task.status == TaskStatus.PENDING.value
    assert task.title == "Планёрка"


def test_whisper_reserves_balance(auth_client: TestClient, seeded_models, mock_publish_task, session: Session, test_user: User):
    """Успешное списание при выполнении ML-запроса."""
    auth_client.post("/predict/whisper", files={"audio": ("a.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")}, data={"title": ""})

    session.refresh(test_user)
    assert test_user.balance == 90.0, "Баланс должен уменьшиться на 10 (стоимость whisper)"

    transactions = session.exec(select(Transaction).where(Transaction.user_id == test_user.id)).all()
    assert len(transactions) == 1
    tx = transactions[0]
    assert tx.type == "debit"
    assert tx.amount == -10.0
    assert tx.status == TransactionStatus.RESERVED.value, "Статус должен быть RESERVED до обработки воркером"


def test_whisper_publishes_task_to_queue(auth_client: TestClient, seeded_models, mock_publish_task):
    """publish_task вызвана с правильными параметрами — сообщение ушло в очередь."""
    response = auth_client.post("/predict/whisper", files={"audio": ("b.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")}, data={"title": ""})
    task_id = response.json()["task_id"]

    assert len(mock_publish_task) == 1, "publish_task должна быть вызвана ровно 1 раз"
    call = mock_publish_task[0]
    assert call["task_id"] == task_id
    assert call["model_name"] == "whisper"
    assert "audio_path" in call["features"]


# --- POST /predict/whisper — отказы ---

def test_whisper_insufficient_balance_returns_400(client: TestClient, seeded_models, mock_publish_task):
    """Запрет списания при недостаточном балансе"""
    # Создаём юзера с balance=0 через signup
    client.post("/auth/signup", json={"email": "poor@test.ru", "password": "poorpass", "name": "Бедняк"})
    login = client.post("/auth/signin", data={"username": "poor@test.ru", "password": "poorpass"})
    token = login.json()["access_token"]

    response = client.post("/predict/whisper", files={"audio": ("a.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")}, data={"title": ""}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 400, f"Ожидали 400 на недостаток баланса, получили {response.status_code}"
    assert "недостаточно" in response.json()["detail"].lower()


def test_whisper_insufficient_balance_no_task_created(client: TestClient, seeded_models, mock_publish_task, session: Session):
    """При отказе 400 задача в БД не создаётся, publish_task не вызывается."""
    client.post("/auth/signup", json={"email": "poor2@test.ru", "password": "poorpass", "name": "Бедняк 2"})
    login = client.post("/auth/signin", data={"username": "poor2@test.ru", "password": "poorpass"})
    token = login.json()["access_token"]

    client.post("/predict/whisper", files={"audio": ("a.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")}, data={"title": ""}, headers={"Authorization": f"Bearer {token}"})

    tasks = session.exec(select(Task)).all()
    assert len(tasks) == 0, "При 400 задача не должна создаваться"
    assert len(mock_publish_task) == 0, "При 400 publish_task не должна вызываться"


def test_whisper_invalid_file_format(auth_client: TestClient, seeded_models, mock_publish_task):
    """Неподдерживаемый формат файла (.txt) → 400."""
    response = auth_client.post("/predict/whisper", files={"audio": ("readme.txt", b"not audio at all", "text/plain")}, data={"title": ""})

    assert response.status_code == 400
    assert "формат" in response.json()["detail"].lower()


def test_whisper_amqp_error_refunds_balance(auth_client: TestClient, seeded_models, mock_publish_task_amqp_error, session: Session, test_user: User):
    """Отсутствие списания при ошибке ML-запроса».
    Когда RabbitMQ упал — резерв отменяется, баланс возвращается юзеру, task=ERROR, ответ 503. """
    response = auth_client.post("/predict/whisper", files={"audio": ("a.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")}, data={"title": ""})

    assert response.status_code == 503, f"При падении RabbitMQ ожидали 503, получили {response.status_code}"

    # Баланс вернулся
    session.refresh(test_user)
    assert test_user.balance == 100.0, "Баланс должен вернуться после отмены резерва"

    # Транзакция помечена CANCELLED
    transactions = session.exec(select(Transaction).where(Transaction.user_id == test_user.id)).all()
    assert len(transactions) == 1
    assert transactions[0].status == TransactionStatus.CANCELLED.value

    # Task помечен ERROR
    tasks = session.exec(select(Task).where(Task.user_id == test_user.id)).all()
    assert len(tasks) == 1
    assert tasks[0].status == TaskStatus.ERROR.value


def test_whisper_without_token_returns_401(client: TestClient, seeded_models):
    """Без токена /predict/whisper → 401."""
    response = client.post("/predict/whisper", files={"audio": ("a.mp3", FAKE_AUDIO_BYTES, "audio/mpeg")}, data={"title": ""})
    assert response.status_code == 401


# --- POST /predict/summary ---

def _create_done_whisper_task(session: Session, user_id: int, whisper_model_id: int, transcription: str = "Привет, это транскрипт") -> Task:
    """Хелпер: создаёт whisper-задачу в статусе DONE с результатом, чтобы тесты summary могли её использовать."""
    task = Task(input_data="/app/uploads/fake.mp3", user_id=user_id, model_id=whisper_model_id, status=TaskStatus.DONE.value, title="Исходник для саммари")
    session.add(task)
    session.commit()
    session.refresh(task)

    result = Result(task_id=task.id, transcription=transcription, diarization="[SPEAKER_01]: тест")
    session.add(result)
    session.commit()
    return task


def test_summary_success(auth_client: TestClient, seeded_models, mock_publish_task, session: Session, test_user: User):
    """Саммари из готовой whisper-задачи → 202, списано 5 кредитов."""
    source = _create_done_whisper_task(session, test_user.id, seeded_models["whisper"].id)

    response = auth_client.post("/predict/summary", json={"source_task_id": source.id})

    assert response.status_code == 202
    assert response.json()["model_name"] == "summary"
    assert response.json()["credits_charged"] == 5.0

    session.refresh(test_user)
    assert test_user.balance == 95.0, "100 - 5 = 95"


def test_summary_source_not_found(auth_client: TestClient, seeded_models, mock_publish_task):
    """Саммари от несуществующей задачи → 404."""
    response = auth_client.post("/predict/summary", json={"source_task_id": 99999})
    assert response.status_code == 404


def test_summary_source_from_other_user(auth_client: TestClient, seeded_models, mock_publish_task, session: Session, second_user: User):
    """Нельзя делать саммари из чужой задачи → 403."""
    source = _create_done_whisper_task(session, second_user.id, seeded_models["whisper"].id, transcription="Чужой секретный транскрипт")

    response = auth_client.post("/predict/summary", json={"source_task_id": source.id})
    assert response.status_code == 403


def test_summary_source_not_done_yet(auth_client: TestClient, seeded_models, mock_publish_task, session: Session, test_user: User):
    """Если исходная whisper-задача ещё в processing или pending — саммари запрещено (400)."""
    source = Task(input_data="/app/uploads/x.mp3", user_id=test_user.id, model_id=seeded_models["whisper"].id, status=TaskStatus.PROCESSING.value)
    session.add(source)
    session.commit()
    session.refresh(source)

    response = auth_client.post("/predict/summary", json={"source_task_id": source.id})
    assert response.status_code == 400
    assert "ещё не обработана" in response.json()["detail"].lower()


def test_summary_source_without_transcription(auth_client: TestClient, seeded_models, mock_publish_task, session: Session, test_user: User):
    """Если у исходной задачи нет Result.transcription → 400."""
    source = Task(input_data="/app/uploads/x.mp3", user_id=test_user.id, model_id=seeded_models["whisper"].id, status=TaskStatus.DONE.value)
    session.add(source)
    session.commit()
    session.refresh(source)
    # Намеренно НЕ создаём Result — симулируем битое состояние БД

    response = auth_client.post("/predict/summary", json={"source_task_id": source.id})
    assert response.status_code == 400
    assert "транскрипта" in response.json()["detail"].lower()


# --- GET /predict/{task_id} — получение статуса/результата ---

def test_get_status_of_pending_task(auth_client: TestClient, seeded_models, mock_publish_task, session: Session, test_user: User):
    """GET возвращает 200 и статус pending у только что созданной задачи."""
    task = Task(input_data="/app/uploads/p.mp3", user_id=test_user.id, model_id=seeded_models["whisper"].id, status=TaskStatus.PENDING.value)
    session.add(task)
    session.commit()
    session.refresh(task)

    response = auth_client.get(f"/predict/{task.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task.id
    assert data["status"] == "pending"
    assert data["model_name"] == "whisper"
    assert data["transcription"] is None, "У pending-задачи не должно быть результата"


def test_get_status_of_done_task_returns_full_result(auth_client: TestClient, seeded_models, mock_publish_task, session: Session, test_user: User):
    """Получение результата предсказания"""
    task = _create_done_whisper_task(session, test_user.id, seeded_models["whisper"].id, transcription="Итоговый транскрипт встречи")

    response = auth_client.get(f"/predict/{task.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "done"
    assert data["transcription"] == "Итоговый транскрипт встречи"
    assert data["diarization"] == "[SPEAKER_01]: тест"


def test_get_status_not_found(auth_client: TestClient, seeded_models):
    """Несуществующий task_id → 404."""
    response = auth_client.get("/predict/99999")
    assert response.status_code == 404


def test_get_status_of_other_user_task(auth_client: TestClient, seeded_models, mock_publish_task, session: Session, second_user: User):
    """Нельзя посмотреть результат чужой задачи → 403."""
    task = _create_done_whisper_task(session, second_user.id, seeded_models["whisper"].id, transcription="Секрет второго юзера")

    response = auth_client.get(f"/predict/{task.id}")
    assert response.status_code == 403
