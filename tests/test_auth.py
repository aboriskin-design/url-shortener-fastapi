import pytest


@pytest.mark.asyncio
async def test_register_and_login(client):
    reg = await client.post("/auth/register", json={"email": "test@test.com", "password": "test12345"})
    assert reg.status_code in (200, 201, 409)

    login = await client.post("/auth/login", json={"email": "test@test.com", "password": "test12345"})
    assert login.status_code == 200
    data = login.json()
    assert "access_token" in data