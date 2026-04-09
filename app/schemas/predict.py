from pydantic import BaseModel, Field
from typing import Optional

class PredictRequest(BaseModel):
    user_id: int
    input_data: str = Field(..., min_length=1, description="Данные для предсказания (путь к файлу)")
    model_name: str = Field(default="whisper", description="Название модели: whisper, diarization, summary")

class PredictResponse(BaseModel):
    task_id: int
    status: str
    model_name: str
    credits_charged: float
    result: Optional[str] = None
