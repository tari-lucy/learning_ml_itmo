from fastapi import APIRouter, Depends
from sqlmodel import Session
from database.database import get_session
from services.crud.transaction import get_user_balance, top_up_balance
from schemas.balance import BalanceResponse, TopUpRequest, TopUpResponse
from auth.authenticate import authenticate

balance_router = APIRouter(prefix="/balance", tags=["Баланс"])


@balance_router.get("/", response_model=BalanceResponse)
def get_balance(current_user_id: int = Depends(authenticate), session: Session = Depends(get_session)):
    """Получить баланс текущего пользователя"""
    balance = get_user_balance(session, current_user_id)
    return BalanceResponse(user_id=current_user_id, balance=balance)


@balance_router.post("/topup", response_model=TopUpResponse)
def topup(data: TopUpRequest, current_user_id: int = Depends(authenticate), session: Session = Depends(get_session)):
    """Пополнить баланс текущего пользователя"""
    top_up_balance(session, current_user_id, data.amount)
    new_balance = get_user_balance(session, current_user_id)
    return TopUpResponse(message="Баланс пополнен", new_balance=new_balance)