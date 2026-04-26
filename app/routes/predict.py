import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session

from database.database import get_session
from services.crud.ml_model import get_model_by_name
from services.crud.transaction import get_user_balance, reserve_balance, cancel_reserve
from services.crud.task import create_task, get_task_by_id, get_result_by_task, update_result_speakers
from models.task import Task, TaskStatus
from schemas.predict import SummaryRequest, PredictAcceptedResponse, PredictStatusResponse, SpeakerNamesRequest
from queue_client.publisher import publish_task
from aio_pika.exceptions import AMQPConnectionError
from auth.authenticate import authenticate

predict_router = APIRouter(prefix="/predict", tags=["ML-предсказания"])

UPLOADS_DIR = Path("/app/uploads")
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}


@predict_router.post("/whisper", response_model=PredictAcceptedResponse, status_code=202)
async def submit_whisper(audio: UploadFile = File(...), title: str = Form(""), current_user_id: int = Depends(authenticate), session: Session =
Depends(get_session)):
    """Транскрибация + диаризация аудио (через Replicate)."""
    model = get_model_by_name("whisper", session)
    if not model:
        raise HTTPException(status_code=404, detail="Модель 'whisper' не найдена")

    balance = get_user_balance(session, current_user_id)
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

    task = create_task(Task(input_data=str(saved_path), user_id=current_user_id, model_id=model.id, title=title.strip() or None), session)

    try:
        transaction = reserve_balance(session, current_user_id, model.cost, task.id)
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
async def submit_summary(data: SummaryRequest, current_user_id: int = Depends(authenticate), session: Session = Depends(get_session)):
    """Саммаризация готового транскрипта из предыдущей задачи whisper."""
    model = get_model_by_name("summary", session)
    if not model:
        raise HTTPException(status_code=404, detail="Модель 'summary' не найдена")

    source_task = get_task_by_id(data.source_task_id, session)
    if not source_task:
        raise HTTPException(status_code=404, detail=f"Исходная задача {data.source_task_id} не найдена")
    if source_task.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Чужая задача — доступ запрещён")
    if source_task.status != TaskStatus.DONE.value:
        raise HTTPException(status_code=400, detail=f"Исходная задача {data.source_task_id} ещё не обработана (статус: {source_task.status})")

    source_result = get_result_by_task(source_task.id, session)
    transcript_text = source_result.diarization if source_result and source_result.diarization else (source_result.transcription if source_result else None)
    if not transcript_text:
        raise HTTPException(status_code=400, detail=f"У исходной задачи {data.source_task_id} нет транскрипта")


    balance = get_user_balance(session, current_user_id)
    if balance < model.cost:
        raise HTTPException(status_code=400, detail=f"Недостаточно кредитов. Баланс: {balance}, нужно: {model.cost}")

    task = create_task(Task(input_data=f"source_task={source_task.id}", user_id=current_user_id, model_id=model.id, title=f"Саммари: {source_task.title}" if source_task.title else None), session)

    try:
        transaction = reserve_balance(session, current_user_id, model.cost, task.id)
    except ValueError as e:
        task.status = TaskStatus.ERROR.value
        session.add(task)
        session.commit()
        raise HTTPException(status_code=400, detail=str(e))

    try:
        await publish_task(task_id=task.id, features={"source_task_id": source_task.id, "transcription": transcript_text}, model_name="summary")
    except AMQPConnectionError:
        cancel_reserve(session, transaction.id)
        task.status = TaskStatus.ERROR.value
        session.add(task)
        session.commit()
        raise HTTPException(status_code=503, detail="Сервис очереди задач временно недоступен. Попробуйте позже.")

    return PredictAcceptedResponse(task_id=task.id, model_name="summary", credits_charged=model.cost)


@predict_router.post("/protocol", response_model=PredictAcceptedResponse, status_code=202)
async def submit_protocol(data: SummaryRequest, current_user_id: int = Depends(authenticate), session: Session = Depends(get_session)):
    """Генерация протокола из готового транскрипта предыдущей задачи whisper."""
    model = get_model_by_name("protocol", session)
    if not model:
        raise HTTPException(status_code=404, detail="Модель 'protocol' не найдена")

    source_task = get_task_by_id(data.source_task_id, session)
    if not source_task:
        raise HTTPException(status_code=404, detail=f"Исходная задача {data.source_task_id} не найдена")
    if source_task.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Чужая задача — доступ запрещён")
    if source_task.status != TaskStatus.DONE.value:
        raise HTTPException(status_code=400, detail=f"Исходная задача {data.source_task_id} ещё не обработана (статус: {source_task.status})")

    source_result = get_result_by_task(source_task.id, session)
    transcript_text = source_result.diarization if source_result and source_result.diarization else (source_result.transcription if source_result else None)
    if not transcript_text:
        raise HTTPException(status_code=400, detail=f"У исходной задачи {data.source_task_id} нет транскрипта")

    balance = get_user_balance(session, current_user_id)
    if balance < model.cost:
        raise HTTPException(status_code=400, detail=f"Недостаточно кредитов. Баланс: {balance}, нужно: {model.cost}")

    task = create_task(Task(input_data=f"source_task={source_task.id}", user_id=current_user_id, model_id=model.id, title=f"Протокол: {source_task.title}" if source_task.title else None), session)

    try:
        transaction = reserve_balance(session, current_user_id, model.cost, task.id)
    except ValueError as e:
        task.status = TaskStatus.ERROR.value
        session.add(task)
        session.commit()
        raise HTTPException(status_code=400, detail=str(e))

    try:
        await publish_task(task_id=task.id, features={"source_task_id": source_task.id, "transcription": transcript_text}, model_name="protocol")
    except AMQPConnectionError:
        cancel_reserve(session, transaction.id)
        task.status = TaskStatus.ERROR.value
        session.add(task)
        session.commit()
        raise HTTPException(status_code=503, detail="Сервис очереди задач временно недоступен. Попробуйте позже.")

    return PredictAcceptedResponse(task_id=task.id, model_name="protocol", credits_charged=model.cost)

@predict_router.patch("/{task_id}/speakers", response_model=PredictStatusResponse)
def update_speakers(task_id: int, data: SpeakerNamesRequest, current_user_id: int = Depends(authenticate), session: Session =
Depends(get_session)):
    """Сохранить имена спикеров (например {SPEAKER_00: Иван, SPEAKER_01: Анна}). Применяется при отображении транскрипта, саммари и протокола."""
    task = get_task_by_id(task_id, session)
    if not task:
        raise HTTPException(status_code=404, detail=f"Задача {task_id} не найдена")
    if task.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Чужая задача — доступ запрещён")
    if task.status != TaskStatus.DONE.value:
        raise HTTPException(status_code=400, detail=f"Задача {task_id} ещё не обработана (статус: {task.status})")

    result = update_result_speakers(task_id, data.speaker_names, session)
    if not result:
        raise HTTPException(status_code=404, detail=f"Результат для задачи {task_id} не найден")

    return PredictStatusResponse(task_id=task.id, status=task.status, model_name=task.model.name, transcription=result.transcription, diarization=result.diarization, protocol=result.protocol, summary=result.summary, speaker_names=result.speaker_names)

@predict_router.get("/{task_id}", response_model=PredictStatusResponse)
def get_prediction_status(task_id: int, current_user_id: int = Depends(authenticate), session: Session = Depends(get_session)):
    """Проверить статус задачи и получить результат, если он готов."""
    task = get_task_by_id(task_id, session)
    if not task:
        raise HTTPException(status_code=404, detail=f"Задача {task_id} не найдена")
    if task.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Чужая задача — доступ запрещён")

    response = PredictStatusResponse(task_id=task.id, status=task.status, model_name=task.model.name)

    if task.status == TaskStatus.DONE.value:
        result = get_result_by_task(task.id, session)
        if result:
            response.transcription = result.transcription
            response.diarization = result.diarization
            response.protocol = result.protocol
            response.summary = result.summary
            response.speaker_names = result.speaker_names

            # Для summary/protocol — если своих имён нет, подтягиваем из исходной whisper-задачи
            if not response.speaker_names and task.model.name in ("summary", "protocol") and task.input_data and task.input_data.startswith("source_task="):
                try:
                    source_id = int(task.input_data.split("=", 1)[1])
                    source_result = get_result_by_task(source_id, session)
                    if source_result and source_result.speaker_names:
                        response.speaker_names = source_result.speaker_names
                except (ValueError, IndexError):
                    pass  # невалидный input_data — пропускаем

    return response