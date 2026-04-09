from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from database.database import get_session
from services.crud.user import get_user_by_id
from services.crud.transaction import get_user_balance, top_up_balance
from schemas.balance import BalanceResponse, TopUpRequest, TopUpResponse

balance_router = APIRouter(prefix="/balance", tags=["Баланс"])

@balance_router.get("/{user_id}", response_model=BalanceResponse)
def get_balance(user_id: int, session: Session = Depends(get_session)):
    """Получить текущий баланс пользователя"""
    user = get_user_by_id(user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    balance = get_user_balance(session, user_id)
    return BalanceResponse(user_id=user_id, balance=balance)

@balance_router.post("/topup", response_model=TopUpResponse)
def topup(data: TopUpRequest, session: Session = Depends(get_session)):
    """Пополнить баланс пользователя"""
    user = get_user_by_id(data.user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    top_up_balance(session, data.user_id, data.amount)
    new_balance = get_user_balance(session, data.user_id)
    return TopUpResponse(message="Баланс пополнен", new_balance=new_balance)