from fastapi import APIRouter, Depends
from sqlmodel import Session
from typing import List
from database.database import get_session
from services.crud.task import get_user_tasks
from services.crud.transaction import get_user_transactions
from schemas.history import TaskHistoryItem, TransactionHistoryItem
from auth.authenticate import authenticate

history_router = APIRouter(prefix="/history", tags=["История"])


@history_router.get("/predictions", response_model=List[TaskHistoryItem])
def get_predictions_history(current_user_id: int = Depends(authenticate), session: Session = Depends(get_session)):
    """История ML-запросов текущего пользователя"""
    tasks = get_user_tasks(current_user_id, session)
    return [
        TaskHistoryItem(
            id=t.id,
            input_data=t.input_data,
            status=t.status,
            model_id=t.model_id,
            model_name=t.model.name,
            created_at=t.created_at,
        )
        for t in tasks
    ]


@history_router.get("/transactions", response_model=List[TransactionHistoryItem])
def get_transactions_history(current_user_id: int = Depends(authenticate), session: Session = Depends(get_session)):
    """История транзакций текущего пользователя"""
    return get_user_transactions(session, current_user_id)