import asyncio

from fastapi import FastAPI
from sqlalchemy import text

from app.auth import router as auth_router
from app.cleanup import cleanup_loop
from app.db import engine, init_db
from app.links import router as links_router

app = FastAPI(title="URL Shortener")

app.include_router(auth_router)
app.include_router(links_router)


@app.on_event("startup")
async def on_startup():
    await init_db()
    asyncio.create_task(cleanup_loop())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db_check")
async def db_check():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        val = result.scalar_one()
    return {"db": "ok", "value": val}