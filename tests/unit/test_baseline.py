from triagedash.baseline import agent_category, baseline_entry, triage_category


def test_triage_category():
    assert triage_category({"resolution": "DUPLICATE"}) == "close-or-move"
    assert triage_category({"component": "Web Audio"}) == "close-or-move"
    assert triage_category({"ni_targets": ["a@example.com"]}) == "needs-info"
    assert triage_category({"ni_targets": ["a@example.com"], "severity": "S3"}) == "analyzed"
    assert triage_category({}) == "analyzed"


def test_agent_category():
    assert agent_category("needs_info") == "needs-info"
    assert agent_category("triaged") == "analyzed"
    assert agent_category("duplicate") == "close-or-move"
    assert agent_category("incomplete") == "close-or-move"
    assert agent_category("stalled") == "close-or-move"
    assert agent_category("skipped") == "skipped"
    assert agent_category("brand_new") == "brand_new"
    assert agent_category(None) is None


def test_baseline_entry_drops_people():
    entry = baseline_entry(
        {"ni_targets": ["a@example.com"], "dupe_of": "9", "assigned_to": "b@example.com"}
    )
    assert entry["needinfo_count"] == 1
    assert entry["dupe_of"] == 9
    assert "example.com" not in str(entry)
