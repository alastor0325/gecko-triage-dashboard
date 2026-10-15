import io
import json

from triagedash import bmo


def test_fetch_meta_batches_and_caches(tmp_path, monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        return io.StringIO(json.dumps({"bugs": [{"id": 1, "groups": []}]}))

    monkeypatch.setattr(bmo.urllib.request, "urlopen", fake_urlopen)
    assert bmo.fetch_meta({1, 2}, tmp_path) == {1: {"id": 1, "groups": []}}
    assert len(calls) == 1 and "id=1,2&" in calls[0]
    assert bmo.fetch_meta({1, 2}, tmp_path) == {1: {"id": 1, "groups": []}}
    assert len(calls) == 1


def test_fetch_users_batches_and_caches(tmp_path, monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        return io.StringIO(
            json.dumps({"users": [{"name": "a@example.com", "real_name": "A", "nick": "a"}]})
        )

    monkeypatch.setattr(bmo.urllib.request, "urlopen", fake_urlopen)
    assert bmo.fetch_users({"a@example.com", "b@example.com"}, tmp_path) == {
        "a@example.com": {"real_name": "A", "nick": "a"},
        "b@example.com": {"real_name": None, "nick": None},
    }
    assert len(calls) == 1 and "names=a%40example.com&names=b%40example.com" in calls[0]
    bmo.fetch_users({"a@example.com", "b@example.com"}, tmp_path)
    assert len(calls) == 1


def test_fetch_users_splits_into_chunks(tmp_path, monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        return io.StringIO(json.dumps({"users": []}))

    monkeypatch.setattr(bmo, "USER_CHUNK", 2)
    monkeypatch.setattr(bmo.urllib.request, "urlopen", fake_urlopen)
    bmo.fetch_users({f"{n}@example.com" for n in "abcde"}, tmp_path)
    assert len(calls) == 3
