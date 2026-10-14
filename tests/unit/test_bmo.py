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
