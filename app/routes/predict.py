import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session

from database.database import get_session
from services.crud.user import get_user_by_id
from services.crud.ml_model import get_model_by_name
from services.crud.transaction import get_user_balance, reserve_balance, cancel_reserve
from services.crud.task import create_task, get_task_by_id, get_result_by_task
from models.task import Task, TaskStatus
from schemas.predict import SummaryRequest, PredictAcceptedResponse, PredictStatusResponse
from queue_client.publisher import publish_task
from aio_pika.exceptions import AMQPConnectionError

predict_router = APIRouter(prefix="/predict", tags=["ML-предсказания"])

UPLOADS_DIR = Path("/app/uploads")
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}


@predict_router.post("/whisper", response_model=PredictAcceptedResponse, status_code=202)
async def submit_whisper(user_id: int = Form(...), audio: UploadFile = File(...), session: Session = Depends(get_session)):
    """Транскрибация + диаризация аудио (через Replicate)."""
    user = get_user_by_id(user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    model = get_model_by_name("whisper", session)
    if not model:
        raise HTTPException(status_code=404, detail="Модель 'whisper' не найдена")

    balance = get_user_balance(session, user_id)
    if balance < model.cost:
        raise HTTPException(status_code=400, detail=f"Недостаточно кредитов. Баланс: {balance}, нужно: {model.cost}")

    ext = Path(audio.filename or "").suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый формат аудио: {ext}. Разрешены: {','.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    saved_filename = f"{uuid.uuid4().hex}{ext}"
    saved_path = UPLOADS_DIR / saved_filename
    with open(saved_path, "wb") as f:
        f.write(await audio.read())

    task = create_task(Task(input_data=str(saved_path), user_id=user_id, model_id=model.id), session)

    try:
        transaction = reserve_balance(session, user_id, model.cost, task.id)
    except ValueError as e:
        task.status = TaskStatus.ERROR.value
        session.add(task)
        session.commit()
        raise HTTPException(status_code=400, detail=str(e))

    try:
        await publish_task(task_id=task.id, features={"audio_path": str(saved_path)}, model_name="whisper")
    except AMQPConnectionError:
        cancel_reserve(session, transaction.id)
        task.status = TaskStatus.ERROR.value
        session.add(task)
        session.commit()
        raise HTTPException(status_code=503, detail="Сервис очереди задач временно недоступен. Попробуйте позже.")

    return PredictAcceptedResponse(task_id=task.id, model_name="whisper", credits_charged=model.cost)


@predict_router.post("/summary", response_model=PredictAcceptedResponse, status_code=202)
async def submit_summary(data: SummaryRequest, session: Session = Depends(get_session)):
    """Саммаризация готового транскрипта из предыдущей задачи whisper."""
    user = get_user_by_id(data.user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    model = get_model_by_name("summary", session)
    if not model:
        raise HTTPException(status_code=404, detail="Модель 'summary' не найдена")

    source_task = get_task_by_id(data.source_task_id, session)
    if not source_task:
        raise HTTPException(status_code=404, detail=f"Исходная задача {data.source_task_id} не найдена")
    if source_task.status != TaskStatus.DONE.value:
        raise HTTPException(status_code=400, detail=f"Исходная задача {data.source_task_id} ещё не обработана (статус: {source_task.status})")

    source_result = get_result_by_task(source_task.id, session)
    if not source_result or not source_result.transcription:
        raise HTTPException(status_code=400, detail=f"У исходной задачи {data.source_task_id} нет транскрипта")

    balance = get_user_balance(session, data.user_id)
    if balance < model.cost:
        raise HTTPException(status_code=400, detail=f"Недостаточно кредитов. Баланс: {balance}, нужно: {model.cost}")

    task = create_task(Task(input_data=f"source_task={source_task.id}", user_id=data.user_id, model_id=model.id), session)

    try:
        transaction = reserve_balance(session, data.user_id, model.cost, task.id)
    except ValueError as e:
        task.status = TaskStatus.ERROR.value
        session.add(task)
        session.commit()
        raise HTTPException(status_code=400, detail=str(e))

    try:
        await publish_task(task_id=task.id, features={"source_task_id": source_task.id, "transcription": source_result.transcription}, model_name="summary")
    except AMQPConnectionError:
        cancel_reserve(session, transaction.id)
        task.status = TaskStatus.ERROR.value
        session.add(task)
        session.commit()
        raise HTTPException(status_code=503, detail="Сервис очереди задач временно недоступен. Попробуйте позже.")

    return PredictAcceptedResponse(task_id=task.id, model_name="summary", credits_charged=model.cost)


@predict_router.get("/{task_id}", response_model=PredictStatusResponse)
def get_prediction_status(task_id: int, session: Session = Depends(get_session)):
    """Проверить статус задачи и получить результат, если он готов."""
    task = get_task_by_id(task_id, session)
    if not task:
        raise HTTPException(status_code=404, detail=f"Задача {task_id} не найдена")

    response = PredictStatusResponse(task_id=task.id, status=task.status, model_name=task.model.name)

    if task.status == TaskStatus.DONE.value:
        result = get_result_by_task(task.id, session)
        if result:
            response.transcription = result.transcription
            response.diarization = result.diarization
            response.protocol = result.protocol
            response.summary = result.summary

    return response