import pytest

@pytest.mark.asyncio
async def test_redirect_unknown_code(client):
    r = await client.get("/links/NO_SUCH_CODE", follow_redirects=False)
    assert r.status_code in (404, 410)

@pytest.mark.asyncio
async def test_stats_unknown_code(client):
    r = await client.get("/links/NO_SUCH_CODE/stats")
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_update_unknown_code(client, auth_headers):
    r = await client.put("/links/NO_SUCH_CODE", json={"original_url": "https://example.com"}, headers=auth_headers)
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_delete_unknown_code(client, auth_headers):
    r = await client.delete("/links/NO_SUCH_CODE", headers=auth_headers)
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_search_not_found(client):
    r = await client.get("/links/search", params={"original_url": "https://no-such-domain-12345.com/"})
    assert r.status_code == 200
    assert r.json() == [] or len(r.json()) == 0

@pytest.mark.asyncio
async def test_invalid_custom_alias(client):
    # если у тебя валидация alias строгая, это закроет ветку ошибок
    r = await client.post("/links/shorten", json={"original_url": "https://example.com", "custom_alias": "!!bad"})
    assert r.status_code in (400, 422)