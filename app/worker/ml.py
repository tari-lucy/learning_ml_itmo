import logging
import random
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


def run_prediction(model_name: str, features: Dict[str, Any]) -> Dict[str, str]:
    """
    Mock-реализация ML-предикта.
    Имитирует работу модели случайной задержкой и возвращает заглушки результата.
    В будущем (для конкурса ИТМО) тут будет реальный вызов Whisper/Diarization/Summary.

    Args:
        model_name: имя модели ("whisper", "diarization", "summary")
        features: входные данные, например {"input_data": "audio.mp3"}

    Returns:
        Словарь с четырьмя полями результата: transcription, diarization, protocol, summary
    """
    input_data = features.get("input_data", "unknown")

    # Имитируем работу модели: случайная задержка от 0.5 до 2 секунд.
    # Это нужно чтобы было видно как несколько воркеров параллельно обрабатывают задачи.
    processing_time = random.uniform(0.5, 2.0)
    logger.info(f"run_prediction: модель={model_name}, input={input_data}, займёт {processing_time:.2f}с")
    time.sleep(processing_time)

    return {
        "transcription": f"[Mock {model_name}] Транскрипция файла {input_data}. Это демо-результат воркера.",
        "diarization": f"[Mock {model_name}] Спикер 1 (0-15с), Спикер 2 (15-30с), Спикер 1 (30-45с)",
        "protocol": f"[Mock {model_name}] Протокол совещания по материалу {input_data}: обсудили план, назначили ответственных.",
        "summary": f"[Mock {model_name}] Краткое содержание: команда согласовала следующие шаги по проекту."
    }