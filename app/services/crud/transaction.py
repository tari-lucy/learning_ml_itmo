from models.transaction import Transaction, TransactionStatus
from models.user import User
from sqlmodel import Session, select
from typing import List


def get_user_balance(session: Session, user_id: int) -> float:
    """
    Возвращает текущий баланс пользователя. Просто читает поле user.balance.
    """
    user = session.get(User, user_id)
    if not user:
        raise ValueError(f"Пользователь {user_id} не найден")
    return user.balance


def top_up_balance(session: Session, user_id: int, amount: float) -> Transaction:
    """
    Пополнение баланса. Создаёт транзакцию со статусом CONFIRMED и увеличивает user.balance.
    """
    if amount <= 0:
        raise ValueError(f"Сумма пополнения должна быть положительной, получено: {amount}")

    user = session.get(User, user_id)
    if not user:
        raise ValueError(f"Пользователь {user_id} не найден")

    user.balance += amount

    transaction = Transaction(user_id=user_id, amount=amount, type="credit", status=TransactionStatus.CONFIRMED.value, task_id=None)
    session.add(user)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


def reserve_balance(session: Session, user_id: int, amount: float, task_id: int) -> Transaction:
    """
    Зарезервировать средства за задачу.
    Проверяет что баланса хватает, уменьшает user.balance,
    создаёт транзакцию со статусом RESERVED. Всё в одном коммите.
    Возвращает созданную транзакцию.
    Вызывающий код должен либо confirm_reserve, либо cancel_reserve её потом.
    """
    if amount <= 0:
        raise ValueError(f"Сумма резервирования должна быть положительной, получено: {amount}")

    user = session.get(User, user_id)
    if not user:
        raise ValueError(f"Пользователь {user_id} не найден")

    if user.balance < amount:
        raise ValueError(f"Недостаточно кредитов. Баланс: {user.balance}, нужно: {amount}")

    user.balance -= amount

    transaction = Transaction(user_id=user_id, amount=-amount, type="debit", status=TransactionStatus.RESERVED.value, task_id=task_id)
    session.add(user)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


def confirm_reserve(session: Session, transaction_id: int) -> Transaction:
    """
    Подтвердить резерв (задача успешно выполнена).
    Меняет статус RESERVED → CONFIRMED.
    Баланс НЕ трогаем — он уже был уменьшен при reserve_balance.
    """
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise ValueError(f"Транзакция {transaction_id} не найдена")

    if transaction.status != TransactionStatus.RESERVED.value:
        raise ValueError(f"Нельзя подтвердить транзакцию {transaction_id}: статус {transaction.status}, ожидался {TransactionStatus.RESERVED.value}")

    transaction.status = TransactionStatus.CONFIRMED.value
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


def cancel_reserve(session: Session, transaction_id: int) -> Transaction:
    """
    Отменить резерв (задача провалилась).
    Меняет статус RESERVED → CANCELLED и возвращает средства на баланс.
    Всё в одном коммите.
    """
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise ValueError(f"Транзакция {transaction_id} не найдена")

    if transaction.status != TransactionStatus.RESERVED.value:
        raise ValueError(f"Нельзя отменить транзакцию {transaction_id}: статус {transaction.status}, ожидался {TransactionStatus.RESERVED.value}")

    user = session.get(User, transaction.user_id)
    if not user:
        raise ValueError(f"Пользователь {transaction.user_id} не найден")

    transaction.status = TransactionStatus.CANCELLED.value
    user.balance += abs(transaction.amount)

    session.add(transaction)
    session.add(user)
    session.commit()
    session.refresh(transaction)
    return transaction


def get_user_transactions(session: Session, user_id: int) -> List[Transaction]:
    """История транзакций пользователя, отсортированная по дате. Без изменений."""
    statement = select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.created_at.desc())
    return session.exec(statement).all()