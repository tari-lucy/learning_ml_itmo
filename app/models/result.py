from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from models.task import Task

class Result(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    transcription: Optional[str] = None
    diarization: Optional[str] = None
    protocol: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Связь с задачей (обязательная, один-к-одному)
    task_id: int = Field(foreign_key="task.id", unique=True)
    task: Optional["Task"] = Relationship(back_populates="result")

    def __str__(self) -> str:
        return f"Id: {self.id}. Task: {self.task_id}"
