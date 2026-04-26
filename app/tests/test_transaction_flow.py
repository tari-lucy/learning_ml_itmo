import pytest
from sqlmodel import Session

from models.user import User
from models.task import Task
from models.transaction import TransactionStatus
from services.crud.transaction import reserve_balance, confirm_reserve, cancel_reserve


def _create_task(session: Session, user_id: int, model_id: int) -> Task:
    """Хелпер: создаёт задачу (Transaction требует task_id как FK)."""
    task = Task(input_data="/app/uploads/x.mp3", user_id=user_id, model_id=model_id)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def test_reserve_then_confirm_locks_balance(session: Session, test_user: User, seeded_models):
    """Успешное списание при выполнении ML-запроса"""
    task = _create_task(session, test_user.id, seeded_models["whisper"].id)

    tx = reserve_balance(session, test_user.id, 10.0, task.id)
    session.refresh(test_user)
    assert tx.status == TransactionStatus.RESERVED.value
    assert test_user.balance == 90.0, "При reserve баланс уменьшается сразу"

    confirmed = confirm_reserve(session, tx.id)
    session.refresh(test_user)
    assert confirmed.status == TransactionStatus.CONFIRMED.value
    assert test_user.balance == 90.0, "При confirm баланс НЕ должен меняться повторно"


def test_reserve_then_cancel_refunds_balance(session: Session, test_user: User, seeded_models):
    """Отсутствие списания при ошибке ML-запроса"""
    task = _create_task(session, test_user.id, seeded_models["whisper"].id)

    tx = reserve_balance(session, test_user.id, 10.0, task.id)
    session.refresh(test_user)
    assert test_user.balance == 90.0

    cancelled = cancel_reserve(session, tx.id)
    session.refresh(test_user)
    assert cancelled.status == TransactionStatus.CANCELLED.value
    assert test_user.balance == 100.0, "При cancel баланс возвращается юзеру"


def test_cannot_confirm_twice(session: Session, test_user: User, seeded_models):
    """Защита от двойного подтверждения: после CONFIRMED повторный confirm → ValueError."""
    task = _create_task(session, test_user.id, seeded_models["whisper"].id)
    tx = reserve_balance(session, test_user.id, 10.0, task.id)
    confirm_reserve(session, tx.id)

    with pytest.raises(ValueError, match="статус"):
        confirm_reserve(session, tx.id)
