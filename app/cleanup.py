import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import delete_cached_url
from app.db import AsyncSessionLocal
from app.models import ExpiredLink, Link
from app.config import settings


async def cleanup_once():
    # делаю отдельную сессию, чтобы не зависеть от запросов
    async with AsyncSessionLocal() as session:  # type: AsyncSession
        now = datetime.now(timezone.utc)

        # 1) удаляем истекшие по expires_at
        expired_links = (await session.scalars(
            select(Link).where(Link.expires_at.is_not(None)).where(Link.expires_at <= now)
        )).all()

        for link in expired_links:
            session.add(ExpiredLink(
                short_code=link.short_code,
                original_url=link.original_url,
                created_at=link.created_at,
                expires_at=link.expires_at,
                clicks=link.clicks,
                last_accessed_at=link.last_accessed_at,
                deleted_reason="expired",
            ))
            await session.delete(link)
            delete_cached_url(link.short_code)

        # 2) удаляем неиспользуемые N дней
        days = settings.INACTIVE_DAYS
        border = now - timedelta(days=days)

        inactive_links = (await session.scalars(
            select(Link).where(
                (Link.last_accessed_at.is_(None) & (Link.created_at <= border)) |
                (Link.last_accessed_at.is_not(None) & (Link.last_accessed_at <= border))
            )
        )).all()

        for link in inactive_links:
            session.add(ExpiredLink(
                short_code=link.short_code,
                original_url=link.original_url,
                created_at=link.created_at,
                expires_at=link.expires_at,
                clicks=link.clicks,
                last_accessed_at=link.last_accessed_at,
                deleted_reason="inactive",
            ))
            await session.delete(link)
            delete_cached_url(link.short_code)

        await session.commit()


async def cleanup_loop():
    while True:
        try:
            await cleanup_once()
        except Exception as e:
            # по-студенчески: просто печатаю ошибку
            print("[cleanup error]", e)

        await asyncio.sleep(60)  # раз в минуту