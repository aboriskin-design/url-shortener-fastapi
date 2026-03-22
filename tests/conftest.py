import os
import pathlib

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# --- env ДО импортов приложения ---
TEST_DB_PATH = pathlib.Path("test.db").resolve()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ.setdefault("JWT_SECRET", "test_secret_123")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("INACTIVE_DAYS", "30")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")  # мы мокнем, так что не важно

from app.main import app  # noqa: E402
from app.db import engine  # noqa: E402
from app.models import Base  # noqa: E402


# --- fake cache вместо Redis ---
class FakeCache:
    def __init__(self):
        self.data = {}

    def _k(self, short_code: str) -> str:
        return f"short:{short_code}"

    def get(self, short_code: str):
        return self.data.get(self._k(short_code))

    def set(self, short_code: str, url: str):
        self.data[self._k(short_code)] = url

    def delete(self, short_code: str):
        self.data.pop(self._k(short_code), None)


@pytest.fixture(autouse=True)
def patch_cache(monkeypatch):
    fake = FakeCache()

    def get_cached_url(short_code: str):
        return fake.get(short_code)

    def set_cached_url(short_code: str, original_url: str, ttl_seconds: int = 3600):
        fake.set(short_code, original_url)
        return True

    def delete_cached_url(short_code: str):
        fake.delete(short_code)
        return True

    import app.cache as cache_mod
    monkeypatch.setattr(cache_mod, "get_cached_url", get_cached_url, raising=True)
    monkeypatch.setattr(cache_mod, "set_cached_url", set_cached_url, raising=True)
    monkeypatch.setattr(cache_mod, "delete_cached_url", delete_cached_url, raising=True)

    import app.links as links_mod
    if hasattr(links_mod, "get_cached_url"):
        monkeypatch.setattr(links_mod, "get_cached_url", get_cached_url, raising=False)
    if hasattr(links_mod, "set_cached_url"):
        monkeypatch.setattr(links_mod, "set_cached_url", set_cached_url, raising=False)
    if hasattr(links_mod, "delete_cached_url"):
        monkeypatch.setattr(links_mod, "delete_cached_url", delete_cached_url, raising=False)

    return fake


# --- чистим test.db ---
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


# --- создаём таблицы перед тестами ---
@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client):
    email = "test@test.com"
    password = "test12345"

    reg = await client.post("/auth/register", json={"email": email, "password": password})
    assert reg.status_code in (200, 201, 409)

    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200

    data = login.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"не нашел токен в login response: {data}"

    return {"Authorization": f"Bearer {token}"}