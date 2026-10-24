"""Tests for the depth/is_oc convention in Comid.build_topics and the new_threads/replies counts
in Comid.group_by_period (see docs/Conventions.md)."""

import pandas as pd

from comid import Comid

from conftest import make_post, ts


def _build_cm():
    cm = Comid()
    cm.posts = {
        "op1": make_post("op1", "keto", "a1", ts(2024, 1), replies=["c1", "c2"]),
        "c1": make_post("c1", "keto", "u1", ts(2024, 1), parent_id="op1", depth=0),
        "c2": make_post("c2", "keto", "u2", ts(2024, 1), parent_id="op1", depth=0),
        "op2": make_post("op2", "keto", "a2", ts(2024, 1)),
    }
    cm.df_clusters = pd.DataFrame({"diet_talk": ["op1", "op2"]})
    cm.corpus = {}
    return cm


def test_build_topics_marks_oc_rows_depth_minus_one_and_is_oc_true():
    cm = _build_cm()
    cm.build_topics()

    assert cm.df_topics.loc["op1", "depth"] == -1
    assert bool(cm.df_topics.loc["op1", "is_oc"]) is True
    assert cm.df_topics.loc["op2", "depth"] == -1
    assert bool(cm.df_topics.loc["op2", "is_oc"]) is True

    # top-level comments keep Reddit's raw depth (0) and are never flagged as OC
    assert cm.df_topics.loc["c1", "depth"] == 0
    assert bool(cm.df_topics.loc["c1", "is_oc"]) is False
    assert cm.df_topics.loc["c2", "depth"] == 0
    assert bool(cm.df_topics.loc["c2", "is_oc"]) is False


def test_group_by_period_new_threads_counts_ocs_not_top_level_comments():
    cm = _build_cm()
    cm.build_topics()
    cm.group_by_period(period_type="m")

    row = cm.df_periods.iloc[0]
    assert row["new_threads"] == 2  # op1 and op2, never conflated with their comments
    assert row["replies"] == 2  # c1 and c2 (both depth == 0 top-level comments, still counted)
