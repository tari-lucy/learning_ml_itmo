from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
import re

if TYPE_CHECKING:
    from models.transaction import Transaction
    from models.task import Task

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, min_length=5, max_length=255)
    password: str = Field(min_length=4)
    name: str
    role: str = Field(default="user")  # "user" или "admin"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    transactions: List["Transaction"] = Relationship(back_populates="user")
    tasks: List["Task"] = Relationship(back_populates="user")

    def __str__(self) -> str:
        return f"Id: {self.id}. Email: {self.email}. Role: {self.role}"

    def validate_email(self) -> bool:
        pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if not pattern.match(self.email):
            raise ValueError("Invalid email format")
        return True
    
    @property
    def task_count(self) -> int:
        return len(self.tasks)