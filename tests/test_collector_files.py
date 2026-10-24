"""Tests for comid.collector.RedditCollector's file-handling helpers (no network).

`search_ids_by_datetime` is exercised with PullPushApi.search_submissions monkeypatched to avoid
any real HTTP call, per the "no network" requirement.
"""

import json
from datetime import datetime

from comid.collector import RedditCollector
from comid.pullpush import PullPushApi


def test_write_remaining_ids_then_load_ids_file_roundtrip(tmp_path):
    ids = ["abc123", "def456", "ghi789"]
    file_path = str(tmp_path / "remaining.csv")

    RedditCollector._RedditCollector__write_remaining_ids(file_path, ids)

    collector = RedditCollector()
    collector.load_ids_file(file_path)
    assert collector.ids == ids


def test_append_json_string_twice_produces_valid_json(tmp_path):
    file_path = str(tmp_path / "docs.json")

    RedditCollector.__append_json_string__(file_path, json.dumps({"id": "a"}))
    RedditCollector.__append_json_string__(file_path, json.dumps({"id": "b"}))

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data == [{"id": "a"}, {"id": "b"}]


def test_search_ids_by_datetime_default_filename_pattern(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        PullPushApi,
        "search_submissions",
        lambda self, **kwargs: [{"id": "abc123", "created_utc": 1700000000}],
    )

    collector = RedditCollector()
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 1, 23, 59, 59)
    before = round(datetime.now().timestamp())
    collector.search_ids_by_datetime("testsub", start, end)
    after = round(datetime.now().timestamp())

    matches = list(tmp_path.glob("testsub_ids_*.csv"))
    assert len(matches) == 1
    stamp = int(matches[0].stem.rsplit("_", 1)[-1])
    assert before <= stamp <= after
    assert collector.ids == ["abc123"]
