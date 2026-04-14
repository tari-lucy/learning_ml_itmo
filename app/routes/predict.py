from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from database.database import get_session
from services.crud.user import get_user_by_id
from services.crud.ml_model import get_model_by_name
from services.crud.transaction import get_user_balance, reserve_balance, cancel_reserve
from services.crud.task import create_task, get_task_by_id, get_result_by_task
from models.task import Task, TaskStatus
from schemas.predict import PredictRequest, PredictAcceptedResponse, PredictStatusResponse
from queue_client.publisher import publish_task
from aio_pika.exceptions import AMQPConnectionError

predict_router = APIRouter(prefix="/predict", tags=["ML-предсказания"])


@predict_router.post("/", response_model=PredictAcceptedResponse, status_code=202)
async def submit_prediction(data: PredictRequest, session: Session = Depends(get_session)):
    """
    Принять данные на ML-предсказание и поставить задачу в очередь.
    Возвращает task_id сразу, не дожидаясь обработки.
    Средства резервируются в момент приёма задачи и подтверждаются воркером
    после успешной обработки (либо возвращаются при ошибке).
    """
    user = get_user_by_id(data.user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    model = get_model_by_name(data.model_name, session)
    if not model:
        raise HTTPException(status_code=404, detail=f"Модель '{data.model_name}' не найдена")

    # если у юзера явно не хватает кредитов.
    balance = get_user_balance(session, data.user_id)
    if balance < model.cost:
        raise HTTPException(status_code=400, detail=f"Недостаточно кредитов. Баланс: {balance}, нужно: {model.cost}")

    # Создаём задачу в БД со статусом pending.
    task = create_task(Task(input_data=data.input_data, user_id=data.user_id, model_id=model.id), session)

    # Резервируем средства. reserve_balance атомарно уменьшает user.balance и создаёт Transaction(status=reserved, task_id=task.id).
    try:
        transaction = reserve_balance(session, data.user_id, model.cost, task.id)
    except ValueError as e:
        # Маловероятный случай: между get_user_balance и reserve_balance
        # кто-то (параллельный запрос) успел списать баланс. Помечаем task как error.
        task.status = TaskStatus.ERROR.value
        session.add(task)
        session.commit()
        raise HTTPException(status_code=400, detail=str(e))

    # Публикуем задачу в очередь. Если очередь недоступна — откатываем резерв.
    try:
        await publish_task(task_id=task.id, features={"input_data": data.input_data}, model_name=data.model_name)
    except AMQPConnectionError:
        # Откатываем резерв: возвращаем средства на баланс и помечаем task как error.
        cancel_reserve(session, transaction.id)
        task.status = TaskStatus.ERROR.value
        session.add(task)
        session.commit()
        raise HTTPException(status_code=503, detail="Сервис очереди задач временно недоступен. Попробуйте позже.")

    return PredictAcceptedResponse(task_id=task.id, model_name=data.model_name, credits_charged=model.cost)


@predict_router.get("/{task_id}", response_model=PredictStatusResponse)
def get_prediction_status(task_id: int, session: Session = Depends(get_session)):
    """
    Проверить статус задачи и получить результат, если он готов.
    Клиент опрашивает этот эндпоинт периодически (polling).
    """
    task = get_task_by_id(task_id, session)
    if not task:
        raise HTTPException(status_code=404, detail=f"Задача {task_id} не найдена")

    response = PredictStatusResponse(task_id=task.id, status=task.status, model_name=task.model.name)

    # Если задача завершена — подгружаем результат
    if task.status == TaskStatus.DONE.value:
        result = get_result_by_task(task.id, session)
        if result:
            response.transcription = result.transcription
            response.diarization = result.diarization
            response.protocol = result.protocol
            response.summary = result.summary

    return response