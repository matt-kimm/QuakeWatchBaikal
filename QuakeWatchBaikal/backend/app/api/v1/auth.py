from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.domain import User

router = APIRouter(prefix="/auth", tags=["Auth"])

class UserRegister(BaseModel):
    username: str
    email: str | None = None
    password: str

@router.post("/register")
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    exists = await db.execute(select(User).where(User.username == data.username))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь уже существует")
    user = User(username=data.username, email=data.email, hashed_password=hash_password(data.password))
    db.add(user)
    await db.commit()
    return {"message": "Регистрация успешна"}

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return {"access_token": create_access_token(user.username), "token_type": "bearer"}
