from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class TaskHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    input_data: str
    status: str
    model_id: int
    model_name: str
    title: Optional[str] = None
    created_at: datetime

class TransactionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: float
    type: str
    task_id: int | None = None
    created_at: datetime