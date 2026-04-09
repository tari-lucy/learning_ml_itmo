from models.user import User
from sqlmodel import Session, select
from typing import List, Optional

def create_user(user: User, session: Session) -> User:
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def get_all_users(session: Session) -> List[User]:
    statement = select(User)
    return session.exec(statement).all()

def get_user_by_id(user_id: int, session: Session) -> Optional[User]:
    statement = select(User).where(User.id == user_id)
    return session.exec(statement).first()

def get_user_by_email(email: str, session: Session) -> Optional[User]:
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()

def delete_user(user_id: int, session: Session) -> bool:
    user = get_user_by_id(user_id, session)
    if user:
        session.delete(user)
        session.commit()
        return True
    return False