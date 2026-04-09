from database.config import get_settings
from database.database import init_db, get_database_engine
from sqlmodel import Session

from models.user import User
from models.ml_model import MLModel
from models.task import Task, TaskStatus
from models.result import Result

from services.crud.user import create_user, get_all_users, get_user_by_email
from services.crud.ml_model import create_ml_model, get_all_models, get_model_by_name
from services.crud.transaction import (
    top_up_balance, deduct_balance, get_user_balance, get_user_transactions
)
from services.crud.task import create_task, update_task_status, create_result, get_user_tasks


def seed_data(session: Session):
    """Инициализация демо-данных (идемпотентная)"""

    # --- ML-модели (создаём только если ещё нет) ---
    if not get_model_by_name("whisper", session):
        create_ml_model(MLModel(name="whisper", description="Транскрибация аудио в текст", cost=10.0), session)
        create_ml_model(MLModel(name="diarization", description="Определение спикеров", cost=5.0), session)
        create_ml_model(MLModel(name="summary", description="Саммари и протокол совещания", cost=8.0), session)
        print("ML-модели созданы")
    else:
        print("ML-модели уже существуют")

    # --- Демо-пользователь ---
    if not get_user_by_email("demo@meeting.ru", session):
        demo = create_user(User(email="demo@meeting.ru", password="demo123", name="Demo User"), session)
        top_up_balance(session, demo.id, 100.0)
        print(f"Демо-пользователь создан: {demo}")
    else:
        print("Демо-пользователь уже существует")

    # --- Демо-администратор ---
    if not get_user_by_email("admin@meeting.ru", session):
        admin = create_user(User(email="admin@meeting.ru", password="admin123", name="Admin", role="admin"), session)
        top_up_balance(session, admin.id, 500.0)
        print(f"Администратор создан: {admin}")
    else:
        print("Администратор уже существует")


def test_scenarios(session: Session):
    """Тестирование основных сценариев"""

    print("\n========== ТЕСТИРОВАНИЕ ==========\n")

    # 1. Получаем демо-пользователя
    demo = get_user_by_email("demo@meeting.ru", session)
    print(f"1. Пользователь: {demo}")

    # 2. Проверяем баланс
    balance = get_user_balance(session, demo.id)
    print(f"2. Баланс: {balance} кредитов")

    # 3. Пополняем баланс
    top_up_balance(session, demo.id, 50.0)
    balance = get_user_balance(session, demo.id)
    print(f"3. Пополнили +50. Баланс: {balance} кредитов")

    # 4. Создаём задачу
    whisper = get_model_by_name("whisper", session)
    task = create_task(
        Task(input_data="meeting_2026-04-07.mp3", user_id=demo.id, model_id=whisper.id),
        session
    )
    print(f"4. Задача создана: {task}")

    # 5. Списываем кредиты за задачу
    deduct_balance(session, demo.id, whisper.cost, task_id=task.id)
    balance = get_user_balance(session, demo.id)
    print(f"5. Списали -{whisper.cost} за whisper. Баланс: {balance} кредитов")

    # 6. Обновляем статус задачи
    update_task_status(task.id, TaskStatus.DONE, session)
    print(f"6. Статус задачи обновлён: {TaskStatus.DONE.value}")

    # 7. Сохраняем результат
    result = create_result(
        Result(
            task_id=task.id,
            transcription="Иван: Добрый день. Мария: Здравствуйте.",
            diarization="Спикер 1: Иван, Спикер 2: Мария",
            protocol="Обсуждение плана на Q2. Решение: утвердить бюджет.",
            summary="Планёрка по бюджету Q2. Бюджет утверждён."
        ),
        session
    )
    print(f"7. Результат сохранён: {result}")

    # 8. История транзакций
    print(f"\n8. История транзакций пользователя {demo.name}:")
    transactions = get_user_transactions(session, demo.id)
    for t in transactions:
        print(f"   {t.type:6} | {t.amount:+.1f} | {t.created_at.strftime('%Y-%m-%d %H:%M')}")

    # 9. История задач
    print(f"\n9. Задачи пользователя {demo.name}:")
    tasks = get_user_tasks(demo.id, session)
    for t in tasks:
        print(f"   Задача #{t.id} | {t.status} | модель: {t.model_id} | {t.created_at.strftime('%Y-%m-%d %H:%M')}")

    # 10. Все пользователи
    print(f"\n10. Все пользователи:")
    for u in get_all_users(session):
        bal = get_user_balance(session, u.id)
        print(f"   {u.name} ({u.email}) | роль: {u.role} | баланс: {bal}")

    # 11. Проверка: недостаточно средств
    print(f"\n11. Попытка списать 9999 кредитов:")
    try:
        deduct_balance(session, demo.id, 9999)
    except ValueError as e:
        print(f"   Ошибка (ожидаемо): {e}")


if __name__ == "__main__":
    settings = get_settings()
    print(f"App: {settings.APP_NAME}")
    print(f"Debug: {settings.DEBUG}")

    # Инициализация БД
    init_db()
    print("Таблицы созданы")

    # Демо-данные + тесты
    engine = get_database_engine()
    with Session(engine) as session:
        seed_data(session)
        test_scenarios(session)