"""Tests for Comid.clean_data: thread removal rules and keyword filtering."""

from comid import Comid

from conftest import make_post, ts


def test_remove_comment_without_author_removes_its_own_replies_only():
    cm = Comid()
    cm.posts = {
        "op1": make_post("op1", "keto", "a1", ts(2024, 1), replies=["c1", "c2"]),
        "c1": make_post("c1", "keto", None, ts(2024, 1), parent_id="op1", depth=0, replies=["c1r"]),
        "c1r": make_post("c1r", "keto", "a2", ts(2024, 1), parent_id="c1", depth=1),
        "c2": make_post("c2", "keto", "a3", ts(2024, 1), parent_id="op1", depth=0),
    }
    result = cm.clean_data(remove_no_content=False, remove_no_author=True)
    # c1 (no author) and its own reply c1r are removed; the OP and sibling c2 survive
    assert set(cm.posts) == {"op1", "c2"}
    assert result["loaded"] == 4
    assert result["no_author_flagged"] == 1  # only c1 itself matches the criterion
    assert result["no_author_removed"] == 2  # c1 + its reply c1r
    assert result["removed_total"] == 2
    assert result["retained"] == 2
    assert result["no_content_flagged"] == 0
    assert result["keyword_removed"] == 0


def test_remove_op_without_author_removes_the_entire_thread():
    cm = Comid()
    cm.posts = {
        "op1": make_post("op1", "keto", None, ts(2024, 1), replies=["c1"]),
        "c1": make_post("c1", "keto", "a1", ts(2024, 1), parent_id="op1", depth=0),
        "op2": make_post("op2", "keto", "a2", ts(2024, 1)),
    }
    result = cm.clean_data(remove_no_content=False, remove_no_author=True)
    assert set(cm.posts) == {"op2"}
    assert result["no_author_flagged"] == 1  # only op1 itself matches
    assert result["no_author_removed"] == 2  # op1 + its reply c1
    assert result["removed_total"] == 2
    assert result["retained"] == 1


def test_keywords_without_boundary_matches_as_substring():
    cm = Comid()
    cm.posts = {
        "op1": make_post("op1", "pets", "a1", ts(2024, 1), text="I love my cat"),
        "op2": make_post("op2", "pets", "a2", ts(2024, 1), text="category theory is fun"),
        "op3": make_post("op3", "pets", "a3", ts(2024, 1), text="nothing related"),
    }
    result = cm.clean_data(remove_no_content=False, remove_no_author=False, keywords=["cat"], boundary_keywords=False)
    # "category" also matches "cat" as a plain substring when boundary_keywords=False
    assert set(cm.posts) == {"op3"}
    assert result["keyword_removed"] == 2
    assert result["removed_total"] == 2
    assert result["retained"] == 1


def test_keywords_with_boundary_matches_whole_word_only():
    cm = Comid()
    cm.posts = {
        "op1": make_post("op1", "pets", "a1", ts(2024, 1), text="I love my cat"),
        "op2": make_post("op2", "pets", "a2", ts(2024, 1), text="category theory is fun"),
        "op3": make_post("op3", "pets", "a3", ts(2024, 1), text="nothing related"),
    }
    result = cm.clean_data(remove_no_content=False, remove_no_author=False, keywords=["cat"], boundary_keywords=True)
    # with word-boundary matching, "category" no longer counts as containing the word "cat"
    assert set(cm.posts) == {"op2", "op3"}
    assert result["keyword_removed"] == 1
    assert result["removed_total"] == 1
    assert result["retained"] == 2


def test_clean_data_by_subreddit_breakdown_matches_overall_counts():
    cm = Comid()
    cm.posts = {
        "op1": make_post("op1", "keto", None, ts(2024, 1)),  # no author -> removed
        "op2": make_post("op2", "keto", "a1", ts(2024, 1)),
        "op3": make_post("op3", "vegan", "a2", ts(2024, 1)),
        "op4": make_post("op4", "vegan", None, ts(2024, 1)),  # no author -> removed
    }
    result = cm.clean_data(remove_no_content=False, remove_no_author=True)

    assert result["loaded"] == 4
    assert result["no_author_flagged"] == 2
    assert result["no_author_removed"] == 2
    assert result["removed_total"] == 2
    assert result["retained"] == 2

    by_subreddit = result["by_subreddit"]
    assert by_subreddit["keto"]["loaded"] == 2
    assert by_subreddit["keto"]["no_author_removed"] == 1
    assert by_subreddit["keto"]["retained"] == 1
    assert by_subreddit["vegan"]["loaded"] == 2
    assert by_subreddit["vegan"]["no_author_removed"] == 1
    assert by_subreddit["vegan"]["retained"] == 1

    # the per-subreddit breakdown must sum up to the overall counts
    for key in ("loaded", "no_author_flagged", "no_author_removed", "removed_total", "retained"):
        assert sum(stats[key] for stats in by_subreddit.values()) == result[key]
