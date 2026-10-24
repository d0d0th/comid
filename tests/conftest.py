"""Shared fixtures/helpers for the comid test suite."""

from datetime import datetime, timezone

import pytest


def ts(year, month, day=1, hour=0, minute=0):
    """UTC epoch timestamp for the given date, for deterministic period_key-based tests."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp()


def make_post(id, subreddit, author_id, created, parent_id=None, depth=None, text="hello world", replies=None):
    """Build a minimal post dict compatible with Comid/Explorer/ConvoCorpus.

    OPs (no `parent_id`) get `depth=None` downstream (no `depth` key is set here); comments need
    `parent_id` and `depth` explicitly. `replies` always gets a (possibly empty) list: Explorer's
    `_proc_thread` only registers a post in `thread_replies` when the `replies` key is present.
    """
    post = {
        "id": id,
        "subreddit": subreddit,
        "author_id": author_id,
        "author": author_id,
        "author_flair_text": None,
        "created": created,
        "full_text": text,
        "selftext": text,
        "replies": replies if replies is not None else [],
    }
    if parent_id is not None:
        post["parent_id"] = parent_id
        post["depth"] = depth
    return post


@pytest.fixture
def stub_comid_factory():
    """Factory for a Comid instance whose spaCy pipeline is replaced by a fast, deterministic stub."""

    def _factory():
        from comid import Comid

        cm = Comid()
        cm.spacy_load = lambda model: None
        cm.text_tokenizer = lambda text, tags, min_size: text.lower().split()
        return cm

    return _factory
