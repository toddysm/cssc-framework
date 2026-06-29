import time

from cssc_common.cache import TTLCache


def test_zero_ttl_always_calls_producer():
    cache = TTLCache(0)
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return calls["n"]

    assert cache.get_or_set("k", producer) == 1
    assert cache.get_or_set("k", producer) == 2


def test_caches_within_ttl():
    cache = TTLCache(60)
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return calls["n"]

    assert cache.get_or_set("k", producer) == 1
    assert cache.get_or_set("k", producer) == 1
    assert calls["n"] == 1


def test_clear_evicts():
    cache = TTLCache(60)
    cache.get_or_set("k", lambda: "v")
    cache.clear()
    assert cache.get_or_set("k", lambda: "v2") == "v2"


def test_expiry(monkeypatch):
    cache = TTLCache(1)
    base = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: base[0])
    assert cache.get_or_set("k", lambda: "first") == "first"
    base[0] += 2.0
    assert cache.get_or_set("k", lambda: "second") == "second"
