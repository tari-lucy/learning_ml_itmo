from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from models.user import User
    from models.task import Task

class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    amount: float    # +100 (пополнение) или -30 (списание)
    type: str        # "credit" или "debit"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Связь с пользователем (обязательная)
    user_id: int = Field(foreign_key="user.id")
    user: Optional["User"] = Relationship(back_populates="transactions")

    # Связь с задачей (необязательная — пополнение не связано с задачей)
    task_id: Optional[int] = Field(default=None, foreign_key="task.id")
    task: Optional["Task"] = Relationship(back_populates="transaction")

    def __str__(self) -> str:
        return f"Id: {self.id}. Type: {self.type}. Amount: {self.amount}"