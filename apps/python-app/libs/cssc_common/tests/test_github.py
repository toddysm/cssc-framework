import httpx

from cssc_common.github import GitHubClient, _next_link


def _client(handler):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url="https://api.github.com", transport=transport)
    return GitHubClient(client=http, owner="o", repo="r", cache_ttl=0)


def test_get_returns_json():
    client = _client(lambda req: httpx.Response(200, json={"hello": "world"}))
    assert client.get("/x") == {"hello": "world"}


def test_get_all_plain_array():
    client = _client(lambda req: httpx.Response(200, json=[1, 2, 3]))
    assert client.get_all("/list") == [1, 2, 3]


def test_get_all_items_key():
    client = _client(lambda req: httpx.Response(200, json={"items": [1, 2]}))
    assert client.get_all("/search", items_key="items") == [1, 2]


def test_get_all_caches_within_ttl():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(200, json=[calls["n"]])

    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url="https://api.github.com", transport=transport)
    client = GitHubClient(client=http, cache_ttl=60)

    first = client.get_all("/p")
    second = client.get_all("/p")
    assert first == second == [1]
    assert calls["n"] == 1


def test_raises_for_http_error():
    client = _client(lambda req: httpx.Response(404, json={"message": "nope"}))
    try:
        client.get("/missing")
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 404
    else:  # pragma: no cover - guard
        raise AssertionError("expected HTTPStatusError")


def test_next_link_parses_rel_next():
    header = '<https://api.github.com/x?page=2>; rel="next", <https://api.github.com/x?page=9>; rel="last"'
    assert _next_link(header) == "https://api.github.com/x?page=2"
    assert _next_link(None) is None
