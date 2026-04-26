import time
from datetime import datetime, timezone
from fastapi import HTTPException, status
from jose import jwt, JWTError
from database.config import get_settings

settings = get_settings()


def create_access_token(user_id: int) -> str:
    payload = {"user_id": user_id, "expires": time.time() + settings.JWT_EXPIRE_SECONDS}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_access_token(token: str) -> dict:
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        expire = data.get("expires")
        if expire is None:
            raise HTTPException(status_code=400, detail="Токен без срока действия")
        if datetime.now(timezone.utc) > datetime.fromtimestamp(expire, timezone.utc):
            raise HTTPException(status_code=403, detail="Срок действия токена истёк")
        return data
    except JWTError:
        raise HTTPException(status_code=400, detail="Невалидный токен")