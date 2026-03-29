from datetime import datetime
from enum import Enum


class MLModel:
    def __init__(self, model_id: str, name: str, description: str, cost: float):
        self.model_id = model_id
        self.name = name
        self.description = description
        self._cost = cost

    def predict(self, input_data: str) -> str:
        raise NotImplementedError


class WhisperModel(MLModel):
    def predict(self, input_data: str) -> str:
        # транскрибация аудиофайла в текст
        pass


class DiarizationModel(MLModel):
    def predict(self, input_data: str) -> str:
        # диаризация спикеров
        pass


class SummaryModel(MLModel):
    def predict(self, input_data: str) -> str:
        # суммаризация транскрибации
        pass


class User:
    def __init__(self, user_id: int, login: str, password: str, name: str, role: str):
        self.user_id = user_id
        self._login = login
        self._password = password
        self.name = name
        self._role = role

    def check_history(self) -> list:
        # проверить историю
        pass


class Admin(User):
    def __init__(self, user_id: int, login: str, password: str, name: str, role: str):
        super().__init__(user_id, login, password, name, role)

    def moderation_balance(self, user_id: int, add_credits: float) -> float:
        # модерация пополнения баланса пользователя
        pass

    def lookup_transactions(self) -> list:
        # посмотреть все транзакции
        pass


class Transaction:
    def __init__(
        self,
        transaction_id: int,
        amount: float,
        dateandtime: datetime,
        user_id: int,
        task_id: int = None,
    ):
        self.transaction_id = transaction_id
        self._amount = amount
        self.dateandtime = dateandtime
        self.user_id = user_id
        self.task_id = task_id

    def get_type(self):
        raise NotImplementedError

    def apply(self):
        raise NotImplementedError


class Balance:
    def __init__(self, user_id: int, amount: float = 0.0):
        self.user_id = user_id
        self._amount = amount

    def check(self) -> float:
        # проверка баланса
        pass

    def add(self, credits: float) -> float:
        # пополнение
        pass

    def deduct(self, credits: float) -> float:
        # списание
        pass


class DebitTransaction(Transaction):
    def get_type(self) -> str:
        return "debit"

    def apply(self) -> float:
        # списание с баланса
        pass


class CreditTransaction(Transaction):
    def get_type(self) -> str:
        return "credit"

    def apply(self) -> float:
        # пополнение кредитов на баланс
        pass


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class Task:
    def __init__(
        self,
        task_id: int,
        input_data: str,
        status: TaskStatus,
        user_id: int,
        model_name: str,
    ):
        self.task_id = task_id
        self.input_data = input_data
        self.status = status
        self.user_id = user_id
        self.model_name = model_name

    def processing(self) -> str:
        # запуск обработки задачи
        pass

    def update_status(self, new_status: TaskStatus) -> None:
        # смена статуса
        pass

    def validate(self) -> dict:
        # валидация данных
        pass


class Result:
    def __init__(
        self,
        result_id: int,
        task_id: int,
        transcription: str,
        diarization: str,
        protocol: str,
        summary: str,
    ):
        self.result_id = result_id
        self.task_id = task_id
        self._transcription = transcription
        self._diarization = diarization
        self._protocol = protocol
        self._summary = summary

    def get_documents(self) -> list:
        # вернуть все документы
        pass


class MeetingScribeService:
    def __init__(self):
        self._users = []
        self._tasks = []
        self._transactions = []
        self._models = []

    def register(self, user_login: str, user_password: str, user_name: str) -> User:
        # сервис регистрирует пользователя
        pass

    def auth(self, user_login: str, user_password: str) -> bool:
        # сервис авторизует пользователя
        pass

    def create_task(self, user_id: int, input_data: str, model_id: str) -> Task:
        # сервис создает задачу для пользователя
        pass

    def create_transaction(
        self, user_id: int, amount: float, task_id: int = None
    ) -> Transaction:
        # создание транзакции (debit или credit в зависимости от контекста) и списание денег
        pass

    def start_processing(self, task_id: int) -> Result:
        # запуск обработки
        pass

    def get_result(self, task_id: int) -> Result:
        # выдача результатов
        pass
