# MeetingScribe — AI-секретарь совещаний

Веб-сервис для автоматической обработки аудиозаписей совещаний. На выходе — транскрипт с диаризацией спикеров и структурированное саммари.

## Как работает

Пользователь загружает аудио → FastAPI ставит задачу в RabbitMQ → один из двух воркеров забирает её и вызывает внешние ML-API → результат сохраняется в Postgres. Клиент опрашивает статус через `GET /predict/{task_id}`.

- **Транскрибация + диаризация:** Replicate (`thomasmol/whisper-diarization`)
- **Саммари:** vsellm (DeepSeek v3.2)

## Стек

FastAPI, RabbitMQ (aio-pika + pika), PostgreSQL (SQLModel), Nginx, Docker Compose

## Запуск

1. Скопируй `.env.example` → `.env` и `app/.env.example` → `app/.env`, заполни значения.
2. Получи токены: [Replicate](https://replicate.com/account/api-tokens) и [vsellm](https://vsellm.ru).
3. `docker compose up --build`

После старта:
- Swagger: http://localhost/docs
- RabbitMQ UI: http://localhost:15672

Демо-пользователи создаются автоматически: `demo@meeting.ru` (100 кредитов), `admin@meeting.ru` (500 кредитов).

## Функциональность

- Регистрация, авторизация, баланс в кредитах
- Асинхронная обработка через очередь с round-robin между двумя воркерами
- Средства резервируются при приёме задачи и подтверждаются/возвращаются по результату
- REST API со Swagger-документацией, история задач