"""Tests for comid.convobridge.ConvoCorpus / ConvoTextParser / filter_utt."""

from comid.convobridge import ConvoCorpus, ConvoTextParser, filter_utt

from conftest import make_post, ts


def _build_corpus(cm):
    cm.posts = {
        "op1": make_post("op1", "keto", "opA", ts(2024, 1), replies=["c1", "c2"]),
        "c1": make_post("c1", "keto", "u1", ts(2024, 1), parent_id="op1", depth=0, replies=["c1r"]),
        "c1r": make_post("c1r", "keto", "u2", ts(2024, 1), parent_id="c1", depth=1),
        "c2": make_post("c2", "keto", "u3", ts(2024, 1), parent_id="op1", depth=0),
    }
    return ConvoCorpus(cm), cm


def test_one_utterance_per_post(stub_comid_factory):
    corpus, cm = _build_corpus(stub_comid_factory())
    assert len(list(corpus.iter_utterances())) == len(cm.posts)


def test_conversation_id_is_the_op_id_for_every_reply(stub_comid_factory):
    corpus, _ = _build_corpus(stub_comid_factory())
    for utt in corpus.iter_utterances():
        assert utt.conversation_id == "op1"


def test_reply_to_matches_parent_id(stub_comid_factory):
    corpus, _ = _build_corpus(stub_comid_factory())
    expected_parent = {"c1": "op1", "c1r": "c1", "c2": "op1"}
    for utt_id, parent in expected_parent.items():
        assert corpus.get_utterance(utt_id).reply_to == parent
    assert corpus.get_utterance("op1").reply_to is None


def test_op_depth_is_none_and_top_level_comment_depth_is_zero(stub_comid_factory):
    corpus, _ = _build_corpus(stub_comid_factory())
    assert corpus.get_utterance("op1").meta["depth"] is None
    assert corpus.get_utterance("c1").meta["depth"] == 0
    assert corpus.get_utterance("c2").meta["depth"] == 0
    assert corpus.get_utterance("c1r").meta["depth"] == 1


class _FakeUtt:
    def __init__(self, depth):
        self.meta = {"depth": depth}


def test_filter_utt_respects_include_oc_and_include_comments():
    oc = _FakeUtt(None)
    top_level = _FakeUtt(0)
    deep_reply = _FakeUtt(1)

    assert filter_utt(oc, include_oc=True, include_comments=False) is True
    assert filter_utt(oc, include_oc=False, include_comments=True) is False
    assert filter_utt(top_level, include_oc=False, include_comments=True) is True
    assert filter_utt(top_level, include_oc=False, include_comments=False) is False
    assert filter_utt(deep_reply, include_oc=False, include_comments=True) is False
    assert filter_utt(deep_reply, include_oc=True, include_comments=True) is False


def test_output_field_is_written_where_requested(stub_comid_factory):
    cm = stub_comid_factory()
    corpus, cm = _build_corpus(cm)
    parser = ConvoTextParser(cm, input_field=None, output_field="custom_words", include_oc=False, include_comments=True)
    corpus = parser.transform(corpus)

    assert corpus.get_utterance("c1").meta["custom_words"] == ["hello", "world"]
    assert corpus.get_utterance("c2").meta["custom_words"] == ["hello", "world"]
    # only depth==0 comments are processed (include_oc=False, include_comments=True)
    assert "custom_words" not in corpus.get_utterance("op1").meta
    assert "custom_words" not in corpus.get_utterance("c1r").meta
