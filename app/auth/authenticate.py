from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from auth.jwt_handler import verify_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/signin")

async def authenticate(token: str = Depends(oauth2_scheme)) -> int:
    if not token:
        raise HTTPException(status_code=403, detail="Требуется авторизация")
    data = verify_access_token(token)
    return data["user_id"]