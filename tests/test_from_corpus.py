"""Tests for IdentityMetrics.from_corpus against a real (tiny) ConvoCorpus/ConvoTextParser pipeline.

A minimal Comid is built with 2 subreddits, 3 OPs and 6 comments at depths 0 and 1. The spaCy
pipeline is replaced by a fast, deterministic stub (see conftest.stub_comid_factory) so the test
has no model-loading overhead and no dependency on spaCy's actual tagging output.
"""

from comid.convobridge import ConvoCorpus, ConvoTextParser
from comid.metrics import IdentityMetrics

from conftest import make_post, ts


def _build_corpus(cm):
    cm.posts = {
        # keto / 2024-01: OP with 2 top-level comments, one of which has a depth-1 reply
        "op1": make_post("op1", "keto", "opA", ts(2024, 1), replies=["c1", "c2"]),
        "c1": make_post("c1", "keto", "u1", ts(2024, 1), parent_id="op1", depth=0, replies=["c1r"]),
        "c1r": make_post("c1r", "keto", "u2", ts(2024, 1), parent_id="c1", depth=1),
        "c2": make_post("c2", "keto", "u3", ts(2024, 1), parent_id="op1", depth=0),
        # vegan / 2024-02: OP with 2 top-level comments, one of which has a depth-1 reply
        "op2": make_post("op2", "vegan", "opB", ts(2024, 2), replies=["c3", "c4"]),
        "c3": make_post("c3", "vegan", "u4", ts(2024, 2), parent_id="op2", depth=0),
        "c4": make_post("c4", "vegan", "u5", ts(2024, 2), parent_id="op2", depth=0, replies=["c4r"]),
        "c4r": make_post("c4r", "vegan", "u6", ts(2024, 2), parent_id="c4", depth=1),
        # vegan / 2024-03: OP with no comments at all
        "op3": make_post("op3", "vegan", "opC", ts(2024, 3)),
    }
    corpus = ConvoCorpus(cm)
    text_processor = ConvoTextParser(
        cm, input_field=None, output_field="words", include_oc=False, include_comments=True
    )
    return text_processor.transform(corpus)


def test_only_depth_zero_comments_are_lexical_opening_authors_are_active(stub_comid_factory):
    cm = stub_comid_factory()
    corpus = _build_corpus(cm)

    metrics = IdentityMetrics.from_corpus(corpus, words_field="words", min_percentile=0)
    series = metrics.series().set_index(["group", "period"])

    # only the 4 depth-0 comments (c1, c2, c3, c4) become lexical records
    assert series.loc[("keto", "2024-01"), "n_lexical"] == 2
    assert series.loc[("vegan", "2024-02"), "n_lexical"] == 2
    assert series.loc[("vegan", "2024-03"), "n_lexical"] == 0  # op3 has no comments at all

    # every utterance (OPs included, regardless of depth) counts as activity
    assert series.loc[("keto", "2024-01"), "n_active"] == 4  # opA, u1, u2, u3
    assert series.loc[("vegan", "2024-02"), "n_active"] == 4  # opB, u4, u5, u6
    assert series.loc[("vegan", "2024-03"), "n_active"] == 1  # opC only

    # periods come from Comid.period_key(utt.timestamp, period_type)
    assert set(metrics.series()["period"]) == {"2024-01", "2024-02", "2024-03"}
