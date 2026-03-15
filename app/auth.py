from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="invalid token")
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="invalid token")

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")

    return user


# optional auth (для shorten, чтобы можно было и гостем)
async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
) -> User | None:
    # OAuth2PasswordBearer по умолчанию требует токен, поэтому этот хак проще не использовать
    # вместо него ниже в links.py будем доставать токен вручную из заголовка, это проще
    return None


@router.post("/register")
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip().lower()

    if len(email) < 3 or "@" not in email:
        raise HTTPException(status_code=400, detail="email странный")

    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="пароль слишком короткий")

    exists = await db.scalar(select(User.id).where(User.email == email))
    if exists is not None:
        raise HTTPException(status_code=409, detail="такой email уже есть")

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"status": "ok", "user_id": user.id}


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip().lower()

    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status_code=401, detail="неверный логин/пароль")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="неверный логин/пароль")

    token = create_token(user.id)
    return TokenResponse(access_token=token)