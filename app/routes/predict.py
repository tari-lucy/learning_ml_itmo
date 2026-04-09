from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from database.database import get_session
from services.crud.user import get_user_by_id
from services.crud.ml_model import get_model_by_name
from services.crud.transaction import get_user_balance, deduct_balance
from services.crud.task import create_task, update_task_status, create_result
from models.task import Task, TaskStatus
from models.result import Result
from schemas.predict import PredictRequest, PredictResponse

predict_router = APIRouter(prefix="/predict", tags=["ML-предсказания"])

@predict_router.post("/", response_model=PredictResponse, status_code=201)
def make_prediction(data: PredictRequest, session: Session = Depends(get_session)):
    """Отправить данные на ML-предсказание"""
    user = get_user_by_id(data.user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    model = get_model_by_name(data.model_name, session)
    if not model:
        raise HTTPException(status_code=404, detail=f"Модель '{data.model_name}' не найдена")
    balance = get_user_balance(session, data.user_id)
    if balance < model.cost:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно кредитов. Баланс: {balance}, нужно: {model.cost}"
        )

    task = create_task(
        Task(input_data=data.input_data, user_id=data.user_id, model_id=model.id),
        session
    )

    deduct_balance(session, data.user_id, model.cost, task_id=task.id)

    update_task_status(task.id, TaskStatus.DONE, session)
    result = create_result(
        Result(
            task_id=task.id,
            transcription="[Заглушка] Транскрибация аудио...",
            diarization="[Заглушка] Спикер 1, Спикер 2",
            protocol="[Заглушка] Протокол совещания",
            summary="[Заглушка] Краткое саммари встречи"
        ),
        session
    )

    return PredictResponse(
        task_id=task.id,
        status="done",
        model_name=data.model_name,
        credits_charged=model.cost,
        result=result.summary
    )