import json
import logging
import os
import time
from typing import Any, Dict

import pika
from pika.exceptions import AMQPConnectionError, StreamLostError, ConnectionClosedByBroker

from sqlmodel import Session

from database.config import get_settings
from database.database import get_database_engine
from services.crud.task import get_task_by_id, update_task_status, create_result
from services.crud.transaction import confirm_reserve, cancel_reserve
from models.task import TaskStatus
from models.result import Result
from models.ml_model import MLModel
from worker.ml import run_prediction

logger = logging.getLogger(__name__)

# Идентификатор воркера для логов. В docker-compose мы прокинем его через env.
WORKER_ID = os.environ.get("WORKER_ID", "worker-?")


def _process_message(body: bytes) -> None:
    """..."""
    try:
        message: Dict[str, Any] = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"[{WORKER_ID}] невалидный JSON в сообщении: {e}")
        return

    task_id = message.get("task_id")
    features = message.get("features")
    model_name = message.get("model")

    if not isinstance(task_id, int):
        logger.error(f"[{WORKER_ID}] отсутствует или некорректный task_id в сообщении: {message}")
        return
    if not isinstance(features, dict):
        logger.error(f"[{WORKER_ID}] отсутствует или некорректный features для task_id={task_id}")
        return
    if not isinstance(model_name, str) or not model_name:
        logger.error(f"[{WORKER_ID}] отсутствует или некорректный model для task_id={task_id}")
        return

    logger.info(f"[{WORKER_ID}] получил task_id={task_id}, model={model_name}")


    engine = get_database_engine()
    with Session(engine) as session:
        task = get_task_by_id(task_id, session)
        if not task:
            logger.error(f"[{WORKER_ID}] task_id={task_id} не найден в БД, пропускаем сообщение")
            return

        transaction = task.transaction
        if not transaction:
            logger.error(f"[{WORKER_ID}] task_id={task_id} не имеет зарезервированной транзакции, пропускаем")
            return

        try:
            # Фаза 1: переводим задачу в processing — клиент при опросе увидит что воркер её взял
            update_task_status(task_id, TaskStatus.PROCESSING, session)

            # Фаза 2: mock-предикт (в реальности — вызов тяжёлой ML-модели)
            prediction = run_prediction(model_name, features)

            # Фаза 3: сохраняем Result
            result = Result(task_id=task_id, transcription=prediction["transcription"], diarization=prediction["diarization"], protocol=prediction["protocol"], summary=prediction["summary"])
            create_result(result, session)

            # Фаза 4: помечаем task как done
            update_task_status(task_id, TaskStatus.DONE, session)

            # Фаза 5: подтверждаем резерв — средства окончательно списаны
            confirm_reserve(session, transaction.id)

            logger.info(f"[{WORKER_ID}] успешно обработал task_id={task_id}")

        except Exception as e:
            logger.error(f"[{WORKER_ID}] ошибка при обработке task_id={task_id}: {e}")
            # Компенсация: помечаем task как error и возвращаем средства юзеру
            try:
                update_task_status(task_id, TaskStatus.ERROR, session)
                cancel_reserve(session, transaction.id)
                logger.info(f"[{WORKER_ID}] откат выполнен: task_id={task_id} помечен error, резерв отменён")
            except Exception as compensate_error:
                logger.error(f"[{WORKER_ID}] КРИТИЧНО: не удалось откатить task_id={task_id}: {compensate_error}")


def _on_message(channel, method, properties, body: bytes) -> None:
    """
    Callback для pika. Вызывается на каждое сообщение из очереди.
    После обработки всегда подтверждает сообщение (ack), даже при ошибке —
    иначе RabbitMQ будет бесконечно возвращать "битое" сообщение этому же воркеру.
    """
    try:
        _process_message(body)
    except Exception as e:
        logger.error(f"[{WORKER_ID}] неожиданная ошибка в обработчике: {e}")
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def start_worker() -> None:
    """
    Главный цикл воркера. Подключается к RabbitMQ, подписывается на очередь
    и обрабатывает сообщения. При разрыве соединения пытается переподключиться через 5 секунд.
    """
    settings = get_settings()
    queue_name = settings.RABBITMQ_QUEUE

    while True:
        try:
            credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
            connection_params = pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT, credentials=credentials, heartbeat=600)

            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()

            # Объявляем очередь. Параметры должны совпадать с publisher'ом (durable=True).
            channel.queue_declare(queue=queue_name, durable=True)

            # prefetch_count=1: не забирай следующее сообщение, пока не обработал текущее.
            # Это правильный режим для долгих задач — иначе быстрый воркер нагребёт себе
            # все сообщения, а медленный будет простаивать.
            channel.basic_qos(prefetch_count=1)

            channel.basic_consume(queue=queue_name, on_message_callback=_on_message)

            logger.info(f"[{WORKER_ID}] запущен, жду сообщения из очереди '{queue_name}'")
            channel.start_consuming()

        except (AMQPConnectionError, StreamLostError, ConnectionClosedByBroker) as e:
            logger.error(f"[{WORKER_ID}] соединение с RabbitMQ потеряно: {e}. Переподключение через 5 сек")
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info(f"[{WORKER_ID}] остановка по Ctrl+C")
            break


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    start_worker()