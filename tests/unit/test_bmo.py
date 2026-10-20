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


def test_fetch_state_keeps_two_booleans_and_hides_an_unseen_bug(monkeypatch):
    found = [
        {"id": 1, "is_open": True, "assigned_to": "nobody@mozilla.org", "severity": "S2"},
        {"id": 2, "is_open": True, "assigned_to": "dev@example.com", "severity": "--"},
    ]
    monkeypatch.setattr(bmo, "get_bugs", lambda ids, fields: found)
    out = bmo.fetch_state({1, 2, 3})
    assert out == {
        1: {"open": True, "assigned": False, "severity": "S2"},
        2: {"open": True, "assigned": True, "severity": "--"},
        3: {"open": False, "assigned": False, "severity": None},
    }
    assert "example.com" not in str(out)
