import pytest

@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/auth/register", json={"email": "w1@test.com", "password": "123456"})
    r = await client.post("/auth/login", json={"email": "w1@test.com", "password": "wrong"})
    assert r.status_code in (401, 400)

@pytest.mark.asyncio
async def test_register_invalid_email(client):
    r = await client.post("/auth/register", json={"email": "not-an-email", "password": "123456"})
    assert r.status_code in (400, 422)

@pytest.mark.asyncio
async def test_login_unknown_user(client):
    r = await client.post("/auth/login", json={"email": "nouser@test.com", "password": "123456"})
    assert r.status_code in (401, 400)