import json
import logging
from typing import Any, Dict

import replicate
from openai import OpenAI

from database.config import get_settings

logger = logging.getLogger(__name__)

WHISPER_DIARIZATION_MODEL = "thomasmol/whisper-diarization:1495a9cddc83b2203b0d8d3516e38b80fd1572ebc4bc5700ac1da56a9b3ed886"


def run_prediction(model_name: str, features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Диспетчер: по имени модели вызывает нужный backend.
    Возвращает словарь полей для Result (transcription, diarization, protocol, summary).
    Незаполненные поля остаются None.
    """
    if model_name == "whisper":
        return _run_whisper(features)
    if model_name == "summary":
        return _run_summary(features)
    if model_name == "protocol":
        return _run_protocol(features)
    raise ValueError(f"Неизвестная модель: {model_name}")


def _run_whisper(features: Dict[str, Any]) -> Dict[str, Any]:
    """Транскрипция + диаризация через Replicate."""
    settings = get_settings()
    audio_path = features["audio_path"]

    logger.info(f"run_whisper: отправляю {audio_path} в Replicate")

    client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN, timeout=600.0)
    with open(audio_path, "rb") as audio_file:
        output = client.run(WHISPER_DIARIZATION_MODEL, input={"file": audio_file, "language": "ru", "group_segments": True})

    segments = output.get("segments", []) if isinstance(output, dict) else []
    transcription = " ".join(seg.get("text", "").strip() for seg in segments).strip()
    diarization = _format_diarization(segments)

    logger.info(f"run_whisper: получен результат, {len(segments)} сегментов, {len(transcription)} символов")

    return {"transcription": transcription, "diarization": diarization, "protocol": None, "summary": None}


def _format_diarization(segments: list) -> str:
    """Форматирует сегменты Replicate в читаемый вид: [Speaker X, 00:15-00:30]: текст"""
    if not segments:
        return ""
    lines = []
    for seg in segments:
        speaker = seg.get("speaker", "?")
        start = _format_time(seg.get("start", 0))
        end = _format_time(seg.get("end", 0))
        text = seg.get("text", "").strip()
        lines.append(f"[{speaker}, {start}-{end}]: {text}")
    return "\n".join(lines)


def _format_time(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def _run_summary(features: Dict[str, Any]) -> Dict[str, Any]:
    """Саммаризация транскрипта через vsellm (OpenAI-совместимый API)."""
    settings = get_settings()
    transcription = features["transcription"]

    logger.info(f"run_summary: отправляю транскрипт длиной {len(transcription)} символов в vsellm")

    client = OpenAI(api_key=settings.VSELLM_API_KEY, base_url=settings.VSELLM_BASE_URL)

    system_prompt = """Ты — AI-ассистент для бизнес-совещаний. Твоя задача — превратить транскрипт совещания в структурированное саммари, которое даёт полное понимание о чём шёл разговор и к чему пришли.

Правила:
- Пиши по-русски, деловым языком, без воды и канцелярита
- Не придумывай факты — опирайся только на то что есть в транскрипте
- Если в транскрипте есть имена спикеров (Speaker 0, Speaker 1 и т.п.) — используй их, иначе говори обезличенно
- Если какого-то раздела нет в совещании — пропусти его, не пиши «не обсуждалось»
- Объём разделов пропорционален длине и насыщенности совещания: для часового разговора «Краткая суть» — это абзац из 5-10 предложений, а не одна строка

Структура ответа:

**Краткая суть**
Связный абзац о том, что это было за совещание, кто участвовал, какие главные темы обсуждались и к чему пришли. Этого блока должно хватить чтобы понять контекст не читая дальше.

**Обсуждённые темы**
Детальный маркированный список ключевых тем. По каждой теме — 2-4 предложения: о чём говорили, какие были позиции, какие аргументы звучали.

**Принятые решения**
Конкретные решения, о которых договорились. Формулируй их точно, как они прозвучали. Если решений нет — пропусти раздел.

**Задачи и ответственные**
Action items в формате: «Кто → что → срок (если озвучен)». Если в транскрипте нет явных задач — пропусти раздел.

**Открытые вопросы**
То, что обсуждали, но не решили. Или то что отложили на следующую встречу. Если всё решили — пропусти раздел."""

    user_prompt = f"Вот транскрипт совещания. Сделай саммари по правилам выше.\n\n---\n\n{transcription}"

    response = client.chat.completions.create(model="deepseek/deepseek-v3.2", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], temperature=0.3)

    summary_text = response.choices[0].message.content or ""
    logger.info(f"run_summary: получен саммари, {len(summary_text)} символов")

    return {"transcription": None, "diarization": None, "protocol": None, "summary": summary_text}

def _run_protocol(features: Dict[str, Any]) -> Dict[str, Any]:
    """Генерация протокола совещания через vsellm (OpenAI-совместимый API)."""
    settings = get_settings()
    transcription = features["transcription"]

    logger.info(f"run_protocol: отправляю транскрипт длиной {len(transcription)} символов в vsellm")

    client = OpenAI(api_key=settings.VSELLM_API_KEY, base_url=settings.VSELLM_BASE_URL)

    system_prompt = """Ты — корпоративный секретарь совета директоров. Твоя задача — оформить транскрипт совещания в формальный
протокол, который можно подшить в дело и разослать участникам и руководству.

Протокол — это НЕ пересказ ключевых смыслов. Это документ, который фиксирует:
- кто что сказал (с указанием спикера)
- как развивалась дискуссия
- к каким именно формулировкам пришли
- кто за что отвечает с конкретными сроками

Стилистические правила:
- Деловой, формальный язык. Без разговорных оборотов
- По-русски, без англицизмов где есть русский эквивалент
- Не сокращай и не упрощай решения — приводи их в той формулировке, в которой они прозвучали
- Если в транскрипте есть имена спикеров (Speaker 0, Speaker 1) — используй их при указании авторства реплик
- Если в обсуждении звучали цифры, даты, названия — обязательно сохрани их точно
- Если какого-то раздела по теме не было — пропусти его полностью, НЕ пиши «не обсуждалось»

Структура протокола:

**1. Тема совещания**
Одно предложение — о чём встреча. Если у встречи было явное название/повестка, проговоренная в начале — используй её.

**2. Участники**
Список всех уникальных спикеров. Формат: «Speaker 0, Speaker 1, ...» или их имена, если они звучали в обсуждении.

**3. Повестка**
Маркированный список тем, которые обсуждались. Одна тема — одна строка.

**4. Ход обсуждения**
По каждой теме из повестки — отдельный подраздел. В каждом подразделе:
- Минимум 4-6 предложений
- С указанием авторства реплик: «Speaker 0 предложил X. Speaker 1 возразил, что Y. После обсуждения...»
- Сохраняй ключевые формулировки и аргументы
- Если в репликах были цифры/факты/даты — приведи их точно

**5. Принятые решения**
Нумерованный список. Каждое решение оформляй в формате:
«Решение N. <Чёткая формулировка>. Инициатор: Speaker X (если можно установить).»
Если решений не было — пропусти раздел.

**6. Поручения**
Таблица в формате Markdown:

| Ответственный | Задача | Срок |
|---|---|---|
| Speaker 0 | <конкретное действие> | <если назван срок, иначе «не указан»> |

Если поручений не было — пропусти раздел.

**7. Вопросы для проработки**
Список того, что обсуждали, но не приняли решения. С указанием, на какую следующую встречу/срок отложили (если звучало).
Если все вопросы решили — пропусти раздел.

**8. Особые мнения и разногласия**
Если в обсуждении прозвучали явные разногласия или спикер выразил несогласие — зафиксируй:
«Speaker X высказал мнение, что <позиция>, но решение было принято иначе.»
Если разногласий не было — пропусти раздел.

ВАЖНО: протокол должен быть подробнее саммари минимум в 2 раза. Раздел «Ход обсуждения» может занимать несколько абзацев на
каждую тему."""

    user_prompt = f"Вот транскрипт совещания. Сделай протокол по правилам выше.\n\n---\n\n{transcription}"

    response = client.chat.completions.create(model="deepseek/deepseek-v3.2", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], temperature=0.3)

    protocol_text = response.choices[0].message.content or ""
    logger.info(f"run_protocol: получен протокол, {len(protocol_text)} символов")

    return {"transcription": None, "diarization": None, "protocol": protocol_text, "summary": None}
