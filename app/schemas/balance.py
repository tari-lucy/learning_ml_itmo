from pydantic import BaseModel, Field

class BalanceResponse(BaseModel):
    user_id: int
    balance: float

class TopUpRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Сумма пополнения (больше 0)")

class TopUpResponse(BaseModel):
    message: str
    new_balance: float