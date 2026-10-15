from datetime import datetime

from triagedash.__main__ import day_folders, page_clock, read_manifest, rounds_to_ingest

from .conftest import make_record


def test_read_manifest():
    text = "# header\nr1\tcompare-r1\n\ndry1\tartifacts\n"
    assert read_manifest(text) == [("r1", "compare-r1"), ("dry1", "artifacts")]


def test_page_clock():
    now = datetime(2026, 11, 1)
    runs = [
        make_record(started_at="2026-10-14T10:00:00"),
        make_record(started_at="2026-10-13T10:00:00"),
    ]
    assert page_clock(runs, now) == datetime(2026, 10, 14, 10)
    assert page_clock([*runs, make_record(posted=True)], now) == now
    assert page_clock([*runs, make_record(source="daily")], now) == now


def test_day_folders_and_rounds_to_ingest(tmp_path):
    pilot = tmp_path / "pilot"
    for name in ("2026-10-16", "2026-10-15", "notes"):
        (pilot / name).mkdir(parents=True)
    (pilot / "log.jsonl").write_text("")
    assert day_folders(pilot) == ["2026-10-15", "2026-10-16"]
    assert day_folders(tmp_path / "missing") == []
    rounds = rounds_to_ingest(tmp_path, "r1\tcompare-r1\n")
    assert rounds == [
        ("2026-10-15", pilot / "2026-10-15", "daily"),
        ("2026-10-16", pilot / "2026-10-16", "daily"),
        ("r1", tmp_path / "compare-r1", "test"),
    ]
