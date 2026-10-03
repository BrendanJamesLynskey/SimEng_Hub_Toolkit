"""The evaluator against hand-worked answers on a three-item dataset, one test per documented rule."""

import pytest

from jql import search

H = lambda f, a, b, on, by="alex": {"field": f, "from": a, "to": b, "on": on, "by": by}  # noqa: E731
DATA = {"now": "2026-09-28", "currentUser": "sam",
        "versions": [{"name": "1.5", "releaseDate": "2026-09-14", "released": True},
                     {"name": "1.6", "releaseDate": "2026-10-26", "released": False},
                     {"name": "1.7", "releaseDate": "2026-12-07", "released": False}],
        "sprints": [{"id": 6, "state": "closed"}, {"id": 7, "state": "active"}],
        "issues": [
            {"key": "SIM-1", "type": "Bug", "status": "Done", "assignee": "sam", "priority": "High", "labels": ["perf"],
             "fixVersion": "1.5", "sprint": 6, "created": "2026-08-01", "resolution": "Done", "summary": "ONNX shapes",
             "history": [H("status", "To Do", "In Progress", "2026-08-03"), H("status", "In Progress", "In Review", "2026-08-06"),
                         H("status", "In Review", "In Progress", "2026-08-07"), H("status", "In Progress", "Done", "2026-08-10")]},
            {"key": "SIM-2", "type": "Story", "status": "In Progress", "assignee": None, "priority": "Medium", "labels": [],
             "fixVersion": "1.6", "sprint": 7, "created": "2026-09-20", "resolution": None, "summary": "Decode tracing",
             "history": [H("status", "To Do", "In Progress", "2026-09-22")]},
            {"key": "SIM-3", "type": "Bug", "status": "To Do", "assignee": "jo", "priority": "Highest", "labels": ["regression"],
             "fixVersion": "1.6", "sprint": 7, "created": "2026-09-27", "resolution": None, "summary": "Gate flaky",
             "history": []}]}


def q(text):
    return search(text, DATA)


def test_not_equals_skips_empty_fields_as_documented():
    assert q("assignee != currentUser()") == ["SIM-3"]                    # SIM-2 is unassigned: not returned
    assert q("assignee != currentUser() OR assignee IS EMPTY") == ["SIM-2", "SIM-3"]


def test_and_binds_tighter_than_or():
    assert q("type = Bug AND status = Done OR priority = Medium") == ["SIM-1", "SIM-2"]
    assert q("type = Bug AND (status = Done OR priority = Medium)") == ["SIM-1"]


def test_was_and_changed_use_history():
    assert q('status WAS "In Review"') == ["SIM-1"]
    assert q('status WAS "In Progress" BEFORE "2026/09/01"') == ["SIM-1"]
    assert q('status CHANGED FROM "In Review" TO "In Progress"') == ["SIM-1"]       # sent back from review
    assert q('status CHANGED AFTER "-14d"') == ["SIM-2"]
    assert q('status WAS NOT "Done"') == ["SIM-2", "SIM-3"]
    with pytest.raises(SyntaxError):
        q('labels WAS "perf"')                                               # WAS only on the six documented fields


def test_functions():
    assert q("sprint in openSprints()") == ["SIM-2", "SIM-3"]
    assert q("fixVersion = earliestUnreleasedVersion(SIM)") == ["SIM-2", "SIM-3"]
    assert q("fixVersion in releasedVersions(SIM)") == ["SIM-1"]


def test_dates_text_lists_and_order():
    assert q('created >= "-7d"') == ["SIM-3"]                              # SIM-2 is 8 days old
    assert q('created >= "-8d"') == ["SIM-2", "SIM-3"]
    assert q('summary ~ "onnx"') == ["SIM-1"]
    assert q('summary ~ "shape"') == ["SIM-1"]                             # a simple derivative: "shapes"
    assert q('summary ~ "hapes"') == []                                    # words, not substrings
    assert q("labels in (perf, regression)") == ["SIM-1", "SIM-3"]
    assert q("project = SIM ORDER BY priority DESC") == ["SIM-3", "SIM-1", "SIM-2"]
    assert q("statusCategory = \"In Progress\"") == ["SIM-2"]
    assert q("resolution IS EMPTY AND priority >= High") == ["SIM-3"]
