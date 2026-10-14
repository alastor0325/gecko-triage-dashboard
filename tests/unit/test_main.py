from datetime import datetime

from triagedash.__main__ import page_clock, read_manifest

from .conftest import make_record


def test_read_manifest():
    text = "# header\nr1\t23aaa262\tcompare-r1\n\ndry1\t-\tartifacts\n"
    assert read_manifest(text) == [("r1", "23aaa262", "compare-r1"), ("dry1", None, "artifacts")]


def test_page_clock():
    now = datetime(2026, 11, 1)
    runs = [
        make_record(started_at="2026-10-14T10:00:00"),
        make_record(started_at="2026-10-13T10:00:00"),
    ]
    assert page_clock(runs, now) == datetime(2026, 10, 14, 10)
    assert page_clock([*runs, make_record(posted=True)], now) == now
