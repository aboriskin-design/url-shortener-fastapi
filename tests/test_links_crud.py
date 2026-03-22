import pytest

@pytest.mark.asyncio
async def test_create_link(client):
    payload = {"original_url": "https://example.com"}
    r = await client.post("/links/shorten", json=payload)
    assert r.status_code == 200

    data = r.json()
    assert "short_code" in data
    assert data["original_url"].rstrip("/") == "https://example.com"


@pytest.mark.asyncio
async def test_update_link_requires_auth(client):
    # без авторизации
    r = await client.post("/links/shorten", json={"original_url": "https://example.com"})
    short_code = r.json()["short_code"]

    # обновить
    upd = await client.put(f"/links/{short_code}", json={"original_url": "https://google.com"})
    assert upd.status_code in (401, 403)


@pytest.mark.asyncio
async def test_delete_link_requires_auth(client):
    r = await client.post("/links/shorten", json={"original_url": "https://example.com"})
    short_code = r.json()["short_code"]

    d = await client.delete(f"/links/{short_code}")
    assert d.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_invalid_url(client):
    # пустая строка должна валиться валидацией
    r = await client.post("/links/shorten", json={"original_url": ""})
    assert r.status_code in (400, 422)