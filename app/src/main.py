# Заглушка, чтобы контейнер запустился
from fastapi import FastAPI

app = FastAPI(title="MeetingScribe")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "MeetingScribe работает"}
