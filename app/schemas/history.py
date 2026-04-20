from pydantic import BaseModel
from datetime import datetime

class TaskHistoryItem(BaseModel):
    id: int
    input_data: str
    status: str
    model_id: int
    model_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionHistoryItem(BaseModel):
    id: int
    amount: float
    type: str
    task_id: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True
