from pydantic import BaseModel, Field
from typing import Optional


class SummaryRequest(BaseModel):
    user_id: int
    source_task_id: int = Field(..., description="ID задачи whisper, из которой берём транскрипт")


class PredictAcceptedResponse(BaseModel):
    """Ответ POST /predict/* — задача принята в очередь, обработка идёт асинхронно"""
    task_id: int
    status: str = "pending"
    model_name: str
    credits_charged: float
    message: str = "Задача принята в обработку. Опросите GET /predict/{task_id} для получения результата."


class PredictStatusResponse(BaseModel):
    """Ответ GET /predict/{task_id}"""
    task_id: int
    status: str
    model_name: str
    transcription: Optional[str] = None
    diarization: Optional[str] = None
    protocol: Optional[str] = None
    summary: Optional[str] = None