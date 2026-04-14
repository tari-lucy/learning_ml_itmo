from pydantic import BaseModel, Field
from typing import Optional

class PredictRequest(BaseModel):
    user_id: int
    input_data: str = Field(..., min_length=1, description="Данные для предсказания (путь к файлу)")
    model_name: str = Field(default="whisper", description="Название модели: whisper, diarization, summary")

class PredictAcceptedResponse(BaseModel):
    """Ответ POST /predict — задача принята в очередь, обработка идёт асинхронно"""
    task_id: int
    status: str = "pending"
    model_name: str
    credits_charged: float
    message: str = "Задача принята в обработку. Опросите GET /predict/{task_id} для получения результата."

class PredictStatusResponse(BaseModel):
    """Ответ GET /predict/{task_id} — текущий статус задачи и результат если готов"""
    task_id: int
    status: str
    model_name: str
    transcription: Optional[str] = None
    diarization: Optional[str] = None
    protocol: Optional[str] = None
    summary: Optional[str] = None