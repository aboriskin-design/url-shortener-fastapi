import pytest

@pytest.mark.asyncio
async def test_search_by_original_url(client):
    created = await client.post("/links/shorten", json={"original_url": "https://example.com"})
    assert created.status_code == 200
    orig = created.json()["original_url"]  # будет с / на конце

    s = await client.get("/links/search", params={"original_url": orig})
    assert s.status_code == 200

    items = s.json()
    assert isinstance(items, list)
    assert len(items) >= 1