from models.transaction import Transaction
from models.user import User
from sqlmodel import Session, select, func
from typing import List, Optional

def create_transaction(
    session: Session,
    user_id: int,
    amount: float,
    type: str,
    task_id: Optional[int] = None
) -> Transaction:
    """Создать транзакцию (пополнение или списание)"""
    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        type=type,
        task_id=task_id
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction

def get_user_balance(session: Session, user_id: int) -> float:
    """Баланс = сумма всех транзакций пользователя"""
    statement = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.user_id == user_id
    )
    balance = session.exec(statement).one()
    return float(balance)

def top_up_balance(session: Session, user_id: int, amount: float) -> Transaction:
    """Пополнение баланса"""
    return create_transaction(session, user_id, amount=amount, type="credit")

def deduct_balance(session: Session, user_id: int, amount: float, task_id: int = None) -> Transaction:
    """Списание с проверкой баланса"""
    balance = get_user_balance(session, user_id)
    if balance < amount:
        raise ValueError(f"Недостаточно кредитов. Баланс: {balance}, нужно: {amount}")
    return create_transaction(session, user_id, amount=-amount, type="debit", task_id=task_id)

def get_user_transactions(session: Session, user_id: int) -> List[Transaction]:
    """История транзакций пользователя, отсортированная по дате"""
    statement = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
    )
    return session.exec(statement).all()