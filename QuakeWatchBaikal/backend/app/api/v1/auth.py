from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.domain import User
from app.api.deps import get_current_user

router = APIRouter()

COOKIE_NAME = "access_token"


class AuthSchema(BaseModel):
    username: str
    password: str


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=3600 * 24,
        path="/",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: AuthSchema,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # Проверяем, не занят ли username
    result = await db.execute(select(User).where(User.username == data.username))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким логином уже зарегистрирован",
        )

    # Записываем логин в колонку username (а email оставляем None или пустым)
    new_user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    access_token = create_access_token(str(new_user.id))
    _set_auth_cookie(response, access_token)

    return {
        "message": "Регистрация выполнена",
        "user": {"id": new_user.id, "username": new_user.username},
    }


@router.post("/login")
async def login(
    data: AuthSchema,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # Ищем пользователя по username
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    access_token = create_access_token(str(user.id))
    _set_auth_cookie(response, access_token)

    return {
        "message": "Успешный вход",
        "user": {"id": user.id, "username": user.username},
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"message": "Выход выполнен"}


@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username}
