from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from models.user import User
    from models.task import Task

class TransactionStatus(str, Enum):
    RESERVED = "reserved"      # средства заморожены, задача в обработке
    CONFIRMED = "confirmed"    # списание / пополнение подтверждено
    CANCELLED = "cancelled"    # резерв отменён, средства вернулись


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    amount: float 
    type: str                  # "credit" или "debit"
    status: str = Field(default=TransactionStatus.CONFIRMED.value)  # ← НОВОЕ
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: int = Field(foreign_key="user.id")
    user: Optional["User"] = Relationship(back_populates="transactions")
    task_id: Optional[int] = Field(default=None, foreign_key="task.id")
    task: Optional["Task"] = Relationship(back_populates="transaction")

    def __str__(self) -> str:
        return f"Id: {self.id}. Type: {self.type}. Amount: {self.amount}"