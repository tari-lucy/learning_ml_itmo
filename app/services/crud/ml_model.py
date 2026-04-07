from models.ml_model import MLModel
from sqlmodel import Session, select
from typing import List, Optional

def create_ml_model(model: MLModel, session: Session) -> MLModel:
    session.add(model)
    session.commit()
    session.refresh(model)
    return model

def get_all_models(session: Session) -> List[MLModel]:
    return session.exec(select(MLModel)).all()

def get_model_by_id(model_id: int, session: Session) -> Optional[MLModel]:
    return session.exec(select(MLModel).where(MLModel.id == model_id)).first()

def get_model_by_name(name: str, session: Session) -> Optional[MLModel]:
    return session.exec(select(MLModel).where(MLModel.name == name)).first()