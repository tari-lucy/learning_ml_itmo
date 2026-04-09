from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from database.database import get_session
from services.crud.user import get_user_by_id
from services.crud.task import get_user_tasks
from services.crud.transaction import get_user_transactions
from schemas.history import TaskHistoryItem, TransactionHistoryItem

history_router = APIRouter(prefix="/history", tags=["История"])

@history_router.get("/predictions/{user_id}", response_model=List[TaskHistoryItem])
def get_predictions_history(user_id: int, session: Session = Depends(get_session)):
    """История ML-запросов пользователя"""

    user = get_user_by_id(user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return get_user_tasks(user_id, session)

@history_router.get("/transactions/{user_id}", response_model=List[TransactionHistoryItem])
def get_transactions_history(user_id: int, session: Session = Depends(get_session)):
    """История транзакций пользователя"""

    user = get_user_by_id(user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return get_user_transactions(session, user_id)