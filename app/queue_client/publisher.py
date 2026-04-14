import json
import logging
from datetime import datetime
from typing import Any, Dict

import aio_pika
from aio_pika.exceptions import AMQPConnectionError

from database.config import get_settings

logger = logging.getLogger(__name__)


def _build_amqp_url() -> str:
    """Собирает URL подключения к RabbitMQ из настроек."""
    settings = get_settings()
    return f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"

async def publish_task(task_id: int, features: Dict[str, Any], model_name: str) -> None:
    """
    Асинхронно публикует ML-задачу в очередь RabbitMQ.

    Args:
        task_id: ID задачи в БД (нужен воркеру чтобы найти Task и записать Result)
        features: входные данные для ML-модели (например {"input_data": "audio.mp3"})
        model_name: имя модели ("whisper", "diarization", "summary")

    Raises:
        AMQPConnectionError: если RabbitMQ недоступен
    """
    settings = get_settings()
    queue_name = settings.RABBITMQ_QUEUE

    message_body = {
        "task_id": task_id,
        "features": features,
        "model": model_name,
        "timestamp": datetime.utcnow().isoformat(),
    }
    body_bytes = json.dumps(message_body).encode("utf-8")

    try:
        connection = await aio_pika.connect_robust(_build_amqp_url())

        async with connection:
            channel = await connection.channel()

            await channel.declare_queue(queue_name, durable=True)

            message = aio_pika.Message(
                body=body_bytes,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            )

            await channel.default_exchange.publish(
                message,
                routing_key=queue_name,
            )

            logger.info(f"Опубликована задача task_id={task_id} в очередь {queue_name}")

    except AMQPConnectionError as e:
        logger.error(f"Не удалось подключиться к RabbitMQ: {e}")
        raise