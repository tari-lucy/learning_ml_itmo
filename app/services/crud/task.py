from models.task import Task, TaskStatus
from models.result import Result
from sqlmodel import Session, select
from typing import List, Optional

def create_task(task: Task, session: Session) -> Task:
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

def get_task_by_id(task_id: int, session: Session) -> Optional[Task]:
    return session.exec(select(Task).where(Task.id == task_id)).first()

def get_user_tasks(user_id: int, session: Session) -> List[Task]:
    """Все задачи пользователя, новые сверху"""
    statement = (
        select(Task)
        .where(Task.user_id == user_id)
        .order_by(Task.created_at.desc())
    )
    return session.exec(statement).all()

def update_task_status(task_id: int, status: TaskStatus, session: Session) -> Optional[Task]:
    task = get_task_by_id(task_id, session)
    if task:
        task.status = status.value
        session.add(task)
        session.commit()
        session.refresh(task)
    return task

def create_result(result: Result, session: Session) -> Result:
    session.add(result)
    session.commit()
    session.refresh(result)
    return result

def get_result_by_task(task_id: int, session: Session) -> Optional[Result]:
    return session.exec(select(Result).where(Result.task_id == task_id)).first()