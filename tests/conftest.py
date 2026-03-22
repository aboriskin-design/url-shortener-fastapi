import sys
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# чтобы "app" импортировался нормально
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac