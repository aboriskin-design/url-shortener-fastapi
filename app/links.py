import random
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import delete_cached_url, get_cached_url, set_cached_url
from app.config import settings
from app.db import get_db
from app.models import ExpiredLink, Link, User
from app.schemas import (
    ExpiredLinkItem,
    LinkCreate,
    LinkCreateResponse,
    LinkSearchItem,
    LinkStatsResponse,
    LinkUpdate,
)

router = APIRouter(prefix="/links", tags=["links"])


def gen_code(n: int = 7) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def is_expired(link: Link) -> bool:
    if link.expires_at is None:
        return False

    now = datetime.now(timezone.utc)
    exp = link.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)

    return exp <= now


async def get_user_from_header_optional(request: Request, db: AsyncSession) -> User | None:
    auth = request.headers.get("Authorization")
    if not auth:
        return None

    if not auth.lower().startswith("bearer "):
        return None

    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        return None

    user = await db.scalar(select(User).where(User.id == user_id))
    return user


async def get_user_from_header_required(request: Request, db: AsyncSession) -> User:
    user = await get_user_from_header_optional(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="нужна авторизация")
    return user


@router.post("/shorten", response_model=LinkCreateResponse)
async def shorten_link(
    payload: LinkCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # expires_at: если в прошлом — ругаемся
    if payload.expires_at is not None:
        now = datetime.now(timezone.utc)
        exp = payload.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now:
            raise HTTPException(status_code=400, detail="expires_at уже в прошлом")

    # если дали custom_alias — используем как short_code
    if payload.custom_alias:
        short_code = payload.custom_alias
        exists = await db.scalar(select(Link.id).where(Link.short_code == short_code))
        if exists is not None:
            raise HTTPException(status_code=409, detail="такой alias уже занят")
    else:
        short_code = gen_code()
        for _ in range(10):
            exists = await db.scalar(select(Link.id).where(Link.short_code == short_code))
            if exists is None:
                break
            short_code = gen_code()
        else:
            raise HTTPException(status_code=500, detail="не смог сгенерировать короткий код")

    # если пользователь залогинен — привязываем к нему
    user = await get_user_from_header_optional(request, db)
    owner_id = user.id if user else None

    link = Link(
        short_code=short_code,
        original_url=str(payload.original_url),
        expires_at=payload.expires_at,
        owner_id=owner_id,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)

    base = str(request.base_url).rstrip("/")
    short_url = f"{base}/{link.short_code}"

    return LinkCreateResponse(
        short_code=link.short_code,
        short_url=short_url,
        original_url=link.original_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


@router.get("/expired", response_model=list[ExpiredLinkItem])
async def get_expired_links(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(ExpiredLink).order_by(ExpiredLink.id.desc()).limit(50)
        )
    ).all()

    result = []
    for r in rows:
        result.append(
            ExpiredLinkItem(
                short_code=r.short_code,
                original_url=r.original_url,
                deleted_reason=r.deleted_reason,
                deleted_at=r.deleted_at,
            )
        )
    return result


@router.get("/search", response_model=list[LinkSearchItem])
async def search_links(
    original_url: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(select(Link).where(Link.original_url == original_url))
    links = result.all()

    items = []
    for link in links:
        if is_expired(link):
            await db.execute(delete(Link).where(Link.id == link.id))
            await db.commit()
            delete_cached_url(link.short_code)
            continue

        items.append(
            LinkSearchItem(
                short_code=link.short_code,
                original_url=link.original_url,
                created_at=link.created_at,
                expires_at=link.expires_at,
            )
        )

    return items


@router.get("/{short_code}")
async def redirect_to_original(
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    cached_url = get_cached_url(short_code)
    if cached_url is not None:
        print("[cache hit]", short_code)

        now = datetime.now(timezone.utc)
        await db.execute(
            update(Link)
            .where(Link.short_code == short_code)
            .values(
                clicks=Link.clicks + 1,
                last_accessed_at=now,
            )
        )
        await db.commit()

        return RedirectResponse(url=cached_url, status_code=307)

    print("[cache miss]", short_code)

    link = await db.scalar(select(Link).where(Link.short_code == short_code))
    if link is None:
        raise HTTPException(status_code=404, detail="ссылка не найдена")

    if is_expired(link):
        await db.execute(delete(Link).where(Link.id == link.id))
        await db.commit()
        delete_cached_url(short_code)
        raise HTTPException(status_code=404, detail="ссылка истекла")

    now = datetime.now(timezone.utc)
    await db.execute(
        update(Link)
        .where(Link.id == link.id)
        .values(
            clicks=Link.clicks + 1,
            last_accessed_at=now,
        )
    )
    await db.commit()

    set_cached_url(short_code, link.original_url)
    return RedirectResponse(url=link.original_url, status_code=307)


@router.get("/{short_code}/stats", response_model=LinkStatsResponse)
async def link_stats(
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    link = await db.scalar(select(Link).where(Link.short_code == short_code))
    if link is None:
        raise HTTPException(status_code=404, detail="ссылка не найдена")

    if is_expired(link):
        await db.execute(delete(Link).where(Link.id == link.id))
        await db.commit()
        delete_cached_url(short_code)
        raise HTTPException(status_code=404, detail="ссылка истекла")

    return LinkStatsResponse(
        short_code=link.short_code,
        original_url=link.original_url,
        created_at=link.created_at,
        clicks=link.clicks,
        last_accessed_at=link.last_accessed_at,
        expires_at=link.expires_at,
    )


@router.put("/{short_code}")
async def update_link(
    short_code: str,
    payload: LinkUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_from_header_required(request, db)

    link = await db.scalar(select(Link).where(Link.short_code == short_code))
    if link is None:
        raise HTTPException(status_code=404, detail="ссылка не найдена")

    if link.owner_id != user.id:
        raise HTTPException(status_code=403, detail="нельзя менять чужую ссылку")

    await db.execute(
        update(Link)
        .where(Link.id == link.id)
        .values(original_url=str(payload.original_url))
    )
    await db.commit()

    delete_cached_url(short_code)

    return {"status": "ok", "message": "ссылка обновлена"}


@router.delete("/{short_code}")
async def delete_link(
    short_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_from_header_required(request, db)

    link = await db.scalar(select(Link).where(Link.short_code == short_code))
    if link is None:
        raise HTTPException(status_code=404, detail="ссылка не найдена")

    if link.owner_id != user.id:
        raise HTTPException(status_code=403, detail="нельзя удалить чужую ссылку")

    await db.execute(delete(Link).where(Link.id == link.id))
    await db.commit()

    delete_cached_url(short_code)

    return {"status": "ok", "message": "ссылка удалена"}