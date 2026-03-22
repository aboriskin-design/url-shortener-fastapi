import pytest
from datetime import datetime, timedelta, timezone


@pytest.mark.asyncio
async def test_update_link_put_requires_auth(client):
    r = await client.post("/links/shorten", json={"original_url": "https://example.com"})
    assert r.status_code == 200
    short_code = r.json()["short_code"]

    upd = await client.put(f"/links/{short_code}", json={"original_url": "https://example.org"})
    assert upd.status_code in (401, 403)


@pytest.mark.asyncio
async def test_update_link_put(client, auth_headers):
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    short_code = r.json()["short_code"]

    upd = await client.put(
        f"/links/{short_code}",
        json={"original_url": "https://example.org"},
        headers=auth_headers,
    )
    assert upd.status_code in (200, 204)

    redir = await client.get(f"/links/{short_code}", follow_redirects=False)
    assert redir.status_code in (301, 302, 307, 308)
    loc = redir.headers.get("location", "")
    assert "example.org" in loc


@pytest.mark.asyncio
async def test_delete_link_requires_auth(client):
    r = await client.post("/links/shorten", json={"original_url": "https://example.com"})
    assert r.status_code == 200
    short_code = r.json()["short_code"]

    d = await client.delete(f"/links/{short_code}")
    assert d.status_code in (401, 403)


@pytest.mark.asyncio
async def test_delete_link(client, auth_headers):
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    short_code = r.json()["short_code"]

    d = await client.delete(f"/links/{short_code}", headers=auth_headers)
    assert d.status_code in (200, 204)

    g = await client.get(f"/links/{short_code}", follow_redirects=False)
    assert g.status_code in (404, 410)


@pytest.mark.asyncio
async def test_stats_endpoint(client):
    r = await client.post("/links/shorten", json={"original_url": "https://example.com"})
    assert r.status_code == 200
    short_code = r.json()["short_code"]

    s1 = await client.get(f"/links/{short_code}/stats")
    assert s1.status_code == 200
    body1 = s1.json()
    assert "original_url" in body1
    assert "created_at" in body1
    assert "clicks" in body1

    await client.get(f"/links/{short_code}", follow_redirects=False)

    s2 = await client.get(f"/links/{short_code}/stats")
    assert s2.status_code == 200
    body2 = s2.json()
    assert body2.get("clicks", 0) >= body1.get("clicks", 0)


@pytest.mark.asyncio
async def test_custom_alias_unique(client):
    alias = "myalias123"
    r1 = await client.post("/links/shorten", json={"original_url": "https://example.com", "custom_alias": alias})
    assert r1.status_code == 200
    assert r1.json()["short_code"] == alias

    r2 = await client.post("/links/shorten", json={"original_url": "https://example.org", "custom_alias": alias})
    assert r2.status_code in (400, 409)


@pytest.mark.asyncio
async def test_expires_at_in_past_is_rejected(client):
    r = await client.post("/links/shorten", json={
        "original_url": "https://example.com",
        "expires_at": "2000-01-01T00:00:00Z"
    })
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_expires_at_future_is_ok(client):
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    r = await client.post("/links/shorten", json={
        "original_url": "https://example.com",
        "expires_at": future
    })
    assert r.status_code == 200

    data = r.json()
    assert "short_code" in data