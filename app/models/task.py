from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from models.user import User
    from models.ml_model import MLModel
    from models.result import Result
    from models.transaction import Transaction

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"

class Task(SQLModel, table=True):
    model_config = {"protected_namespaces": ()}
    id: Optional[int] = Field(default=None, primary_key=True)
    input_data: str                                        # путь к файлу или описание входных данных
    title: Optional[str] = Field(default=None, max_length=200)
    status: str = Field(default=TaskStatus.PENDING.value)  # "pending", "processing", "done", "error"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Связь с пользователем (обязательная)
    user_id: int = Field(foreign_key="user.id")
    user: Optional["User"] = Relationship(back_populates="tasks")

    # Связь с ML-моделью (обязательная)
    model_id: int = Field(foreign_key="mlmodel.id")
    model: Optional["MLModel"] = Relationship(back_populates="tasks")

    # Связь с результатом (необязательная — результат появится после обработки)
    result: Optional["Result"] = Relationship(back_populates="task")

    # Связь с транзакцией списания (необязательная — списание после успешной обработки)
    transaction: Optional["Transaction"] = Relationship(back_populates="task")

    def __str__(self) -> str:
        return f"Id: {self.id}. Status: {self.status}. Model: {self.model_id}"