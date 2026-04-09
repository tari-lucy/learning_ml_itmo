from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from models.task import Task

class MLModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)       # "whisper", "diarization", "summary"
    description: str
    cost: float                                        # стоимость в кредитах за один запрос

    tasks: List["Task"] = Relationship(back_populates="model")

    def __str__(self) -> str:
        return f"Id: {self.id}. Model: {self.name}. Cost: {self.cost}"