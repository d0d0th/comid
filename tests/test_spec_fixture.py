"""Specification fixture: nine lexical records and the activity records that the comid
pipeline would produce for two communities (A, B) over two months.

All values are compared to 4 decimal places with ``min_percentile=None`` and ``log_base=2``. They were
derived by hand from the specified deduplication (a word counts once per distinct author per group
and period), not read back from IdentityMetrics.

Records 1 (``["keto", "fat", "fat"]``) and 4 (``["keto"]``) are the essential ones: the historical
(December draft) deduplication counts "fat" twice for record 1 and re-counts "keto" for record 4,
so it fails this fixture, while the specified deduplication implemented by IdentityMetrics passes.
"""

import math
import random
from collections import Counter
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from comid.metrics import IdentityMetrics

GROUPS = ["A", "B"]
PERIODS = ["2024-01", "2024-02"]

# (group, period, author, words) -- the shape IdentityMetrics.from_corpus yields from the notebook.
LEXICAL = [
    ("A", "2024-01", "u1", ["keto", "fat", "fat"]),  # 1: "fat" repeated inside one record
    ("A", "2024-01", "u2", ["fat"]),  # 2
    ("A", "2024-01", "u1", ["egg"]),  # 3: u1 moves on to another word
    ("A", "2024-01", "u1", ["keto"]),  # 4: ...and returns to "keto", already counted for u1
    ("A", "2024-02", "u1", ["keto", "egg"]),  # 5
    ("A", "2024-02", "u3", ["keto"]),  # 6
    ("B", "2024-01", "w1", ["vegan", "tofu", "tofu"]),  # 7: "tofu" repeated inside one record
    ("B", "2024-01", "w2", ["fat", "tofu"]),  # 8
    ("B", "2024-02", "w1", ["tofu"]),  # 9
]

# (group, period, author): every kind of participation, so it includes authors with no lexical
# record (u4, w3) and therefore differs from the activity implied by LEXICAL alone.
ACTIVITY = [
    ("A", "2024-01", "u1"),
    ("A", "2024-01", "u2"),
    ("A", "2024-01", "u4"),
    ("A", "2024-02", "u1"),
    ("A", "2024-02", "u3"),
    ("A", "2024-02", "u4"),
    ("B", "2024-01", "w1"),
    ("B", "2024-01", "w2"),
    ("B", "2024-01", "w3"),
    ("B", "2024-02", "w1"),
]

# (group, period, word) -> (count, specificity, volatility)
EXPECTED_TRIPLES = {
    ("A", "2024-01", "keto"): (1, 1.0000, -0.7776),
    ("A", "2024-01", "fat"): (2, 0.4150, 0.8074),
    ("B", "2024-01", "tofu"): (2, 1.0000, -0.2630),
    ("B", "2024-02", "tofu"): (1, 2.0000, 0.7370),
}

# (group, period or None for aggregated) -> (distinctiveness D, dynamicity N)
EXPECTED_DISTINCTIVENESS_DYNAMICITY = {
    ("A", None): (0.6490, 0.1394),
    ("A", "2024-01"): (0.8050, -0.0543),
    ("A", "2024-02"): (0.4150, 0.4299),
    ("B", None): (0.8538, 0.2794),
    ("B", "2024-01"): (0.4717, 0.1269),
    ("B", "2024-02"): (2.0000, 0.7370),
}

# Retention is the share of period 1's active authors still active in period 2.
EXPECTED_RETENTION = {"A": 0.6667, "B": 0.3333}

TOLERANCE = 5e-5  # 4 decimal places


# --- Counting algorithms, as plain functions of the records -----------------------------------


def _specified_counts(records, group, period):
    """Specified deduplication: a word counts once per distinct author per (group, period)."""
    pairs = {
        (author, word)
        for rec_group, rec_period, author, words in records
        if (rec_group, rec_period) == (group, period)
        for word in words
    }
    return dict(Counter(word for _author, word in pairs))


def _historical_counts(records, group, period):
    """Historical (December draft) `compute_words`, without the percentile step, WITH its errors:
    the author's word set is replaced instead of accumulated, and a word repeated inside one record
    is counted once per repetition."""
    word_map = {}
    speakers = {}
    for rec_group, rec_period, author, words in records:
        if (rec_group, rec_period) != (group, period):
            continue
        words = [w for w in words if (author not in speakers or w not in speakers[author])]
        speakers[author] = set(words)
        for w in words:
            word_map[w] = word_map.get(w, 0) + 1
    return word_map


def _tables(records, counter):
    return {(g, p): counter(records, g, p) for g in GROUPS for p in PERIODS}


# --- S, V, D, N from a counts table (log base 2, no percentile filter) ------------------------


def _specificity(tables, word, group, period):
    a = tables[(group, period)][word] / sum(tables[(group, period)].values())
    word_total = sum(tables[(g, period)].get(word, 0) for g in GROUPS)
    period_total = sum(sum(tables[(g, period)].values()) for g in GROUPS)
    return math.log2(a / (word_total / period_total))


def _volatility(tables, word, group, period):
    a = tables[(group, period)][word] / sum(tables[(group, period)].values())
    word_total = sum(tables[(group, p)].get(word, 0) for p in PERIODS)
    group_total = sum(sum(tables[(group, p)].values()) for p in PERIODS)
    return math.log2(a / (word_total / group_total))


def _mean_over(tables, group, periods, metric):
    values = [metric(tables, word, group, p) for p in periods for word in tables[(group, p)]]
    return sum(values) / len(values)


def _values_from_tables(tables):
    """Every non-retention expected value, keyed like the EXPECTED_* dictionaries."""
    values = {}
    for (group, period, word) in EXPECTED_TRIPLES:
        values[("triple", group, period, word)] = (
            tables[(group, period)].get(word, 0),
            _specificity(tables, word, group, period),
            _volatility(tables, word, group, period),
        )
    for (group, period) in EXPECTED_DISTINCTIVENESS_DYNAMICITY:
        periods = PERIODS if period is None else [period]
        values[("D/N", group, period)] = (
            _mean_over(tables, group, periods, _specificity),
            _mean_over(tables, group, periods, _volatility),
        )
    return values


def _expected_values():
    values = {("triple", *key): value for key, value in EXPECTED_TRIPLES.items()}
    values.update({("D/N", *key): value for key, value in EXPECTED_DISTINCTIVENESS_DYNAMICITY.items()})
    return values


def _mismatches(actual_values):
    """Keys whose actual value differs from the expected one beyond 4 decimal places."""
    expected = _expected_values()
    return {
        key
        for key, expected_value in expected.items()
        if any(a != pytest.approx(e, abs=TOLERANCE) for a, e in zip(actual_values[key], expected_value))
    }


# --- Tests ------------------------------------------------------------------------------------


def test_fixture_has_nine_lexical_records_and_26_expected_values():
    assert len(LEXICAL) == 9
    assert LEXICAL[0][3] == ["keto", "fat", "fat"]
    assert LEXICAL[3][3] == ["keto"]
    assert 3 * len(EXPECTED_TRIPLES) + 2 * len(EXPECTED_DISTINCTIVENESS_DYNAMICITY) + len(EXPECTED_RETENTION) == 26


@pytest.fixture(scope="module")
def metrics():
    return IdentityMetrics(LEXICAL, ACTIVITY, min_percentile=None, log_base=2)


def _assert_counts_specificity_volatility(metrics):
    for (group, period, word), (count, specificity, volatility) in EXPECTED_TRIPLES.items():
        table = metrics.word_table(group, period).set_index("word")
        assert table.loc[word, "count"] == count
        assert metrics.specificity(word, group, period) == pytest.approx(specificity, abs=TOLERANCE)
        assert metrics.volatility(word, group, period) == pytest.approx(volatility, abs=TOLERANCE)


def _assert_distinctiveness_dynamicity(metrics):
    for (group, period), (distinctiveness, dynamicity) in EXPECTED_DISTINCTIVENESS_DYNAMICITY.items():
        assert metrics.distinctiveness(group, period) == pytest.approx(distinctiveness, abs=TOLERANCE)
        assert metrics.dynamicity(group, period) == pytest.approx(dynamicity, abs=TOLERANCE)


def _assert_retention(metrics):
    for group, retention in EXPECTED_RETENTION.items():
        assert metrics.retention(group) == pytest.approx(retention, abs=TOLERANCE)
        assert metrics.retention(group, "2024-01") == pytest.approx(retention, abs=TOLERANCE)


def _assert_all_values(metrics):
    _assert_counts_specificity_volatility(metrics)
    _assert_distinctiveness_dynamicity(metrics)
    _assert_retention(metrics)


def test_identity_metrics_counts_specificity_and_volatility(metrics):
    _assert_counts_specificity_volatility(metrics)


def test_identity_metrics_distinctiveness_and_dynamicity(metrics):
    _assert_distinctiveness_dynamicity(metrics)


def test_identity_metrics_retention(metrics):
    _assert_retention(metrics)


def test_expected_values_follow_from_the_specified_deduplication():
    """The literals above are the formulas applied to the specified counts: no value is circular."""
    values = _values_from_tables(_tables(LEXICAL, _specified_counts))
    assert _mismatches(values) == set()


def test_historical_deduplication_fails_the_fixture():
    tables = _tables(LEXICAL, _historical_counts)
    # the two essential records: "fat" counted twice (record 1), "keto" re-counted (record 4)
    assert tables[("A", "2024-01")] == {"keto": 2, "fat": 3, "egg": 1}
    assert tables[("B", "2024-01")]["tofu"] == 3  # record 7 repeats "tofu"
    mismatched = _mismatches(_values_from_tables(tables))
    assert ("triple", "A", "2024-01", "keto") in mismatched
    assert ("triple", "A", "2024-01", "fat") in mismatched
    assert ("triple", "B", "2024-01", "tofu") in mismatched
    assert ("D/N", "A", "2024-01") in mismatched


@pytest.mark.parametrize(
    "records, group, period, word, specified, historical",
    [
        # without record 4 only the repeat inside record 1 is left: "fat" is counted twice for u1
        ([r for i, r in enumerate(LEXICAL, 1) if i != 4], "A", "2024-01", "fat", 2, 3),
        # with record 1 reduced to ["keto", "fat"] only record 4 is left: "keto" is re-counted for u1
        (
            [("A", "2024-01", "u1", ["keto", "fat"]) if i == 1 else r for i, r in enumerate(LEXICAL, 1)],
            "A", "2024-01", "keto", 1, 2,
        ),
    ],
    ids=["record-1-repeated-fat", "record-4-returns-to-keto"],
)
def test_each_essential_record_breaks_the_historical_deduplication_on_its_own(
    records, group, period, word, specified, historical
):
    metrics = IdentityMetrics(records, ACTIVITY, min_percentile=None, log_base=2)
    assert metrics.word_table(group, period).set_index("word").loc[word, "count"] == specified
    assert _specified_counts(records, group, period)[word] == specified
    assert _historical_counts(records, group, period)[word] == historical


# --- Full word tables ---------------------------------------------------------------------------

EXPECTED_WORD_COUNTS = {
    ("A", "2024-01"): {"keto": 1, "fat": 2, "egg": 1},
    ("A", "2024-02"): {"keto": 2, "egg": 1},
    ("B", "2024-01"): {"vegan": 1, "tofu": 2, "fat": 1},
    ("B", "2024-02"): {"tofu": 1},
}


def test_identity_metrics_full_word_tables(metrics):
    for (group, period), counts in EXPECTED_WORD_COUNTS.items():
        assert metrics.word_table(group, period).set_index("word")["count"].to_dict() == counts
        assert _specified_counts(LEXICAL, group, period) == counts


# --- The specified deduplication does not depend on the order of the records --------------------


@pytest.mark.parametrize("seed", range(20))
def test_results_do_not_depend_on_record_order(seed):
    shuffled = list(LEXICAL)
    random.Random(seed).shuffle(shuffled)
    _assert_all_values(IdentityMetrics(shuffled, ACTIVITY, min_percentile=None, log_base=2))


def test_historical_deduplication_depends_on_record_order():
    """Swapping records 3 and 4 (u1 says "egg", then "keto") changes the historical count of "keto"."""
    swapped = list(LEXICAL)
    swapped[2], swapped[3] = swapped[3], swapped[2]
    assert _specified_counts(swapped, "A", "2024-01") == _specified_counts(LEXICAL, "A", "2024-01")
    assert _historical_counts(LEXICAL, "A", "2024-01")["keto"] == 2
    assert _historical_counts(swapped, "A", "2024-01")["keto"] == 1


# --- Retention uses the activity records, not the authors of the lexical records ----------------


def test_retention_uses_explicit_activity_records():
    derived = IdentityMetrics(LEXICAL, min_percentile=None, log_base=2)  # activity=None
    # lexical authors only: A has {u1, u2} -> {u1, u3}, B has {w1, w2} -> {w1}
    assert derived.retention("A") == pytest.approx(0.5, abs=TOLERANCE)
    assert derived.retention("B") == pytest.approx(0.5, abs=TOLERANCE)
    explicit = IdentityMetrics(LEXICAL, ACTIVITY, min_percentile=None, log_base=2)
    assert explicit.retention("A") != pytest.approx(derived.retention("A"), abs=TOLERANCE)
    assert explicit.retention("B") != pytest.approx(derived.retention("B"), abs=TOLERANCE)


# --- Other counting modes share the same fixture ------------------------------------------------


def test_speaker_dedup_false_counts_once_per_record():
    """Without per-author deduplication a word counts once per record, never once per occurrence."""
    raw = IdentityMetrics(LEXICAL, ACTIVITY, min_percentile=None, log_base=2, speaker_dedup=False)
    expected = {
        ("A", "2024-01"): {"keto": 2, "fat": 2, "egg": 1},  # keto in records 1 and 4, fat in 1 and 2
        ("A", "2024-02"): {"keto": 2, "egg": 1},
        ("B", "2024-01"): {"vegan": 1, "tofu": 2, "fat": 1},  # tofu in records 7 and 8
        ("B", "2024-02"): {"tofu": 1},
    }
    for (group, period), counts in expected.items():
        assert raw.word_table(group, period).set_index("word")["count"].to_dict() == counts


def test_sample_per_period_above_the_record_count_changes_nothing():
    sampled = IdentityMetrics(LEXICAL, ACTIVITY, min_percentile=None, log_base=2, sample_per_period=100, seed=0)
    _assert_all_values(sampled)
    assert not sampled.series()["sampled"].any()


# --- The same values through IdentityMetrics.from_corpus ----------------------------------------


class _Utterance:
    """Minimal stand-in for a ConvoKit Utterance, as read by IdentityMetrics.from_corpus."""

    def __init__(self, author, period, meta):
        year, month = map(int, period.split("-"))
        self.timestamp = datetime(year, month, 15, 12, tzinfo=timezone.utc).timestamp()
        self.speaker = SimpleNamespace(id=author)
        self.meta = meta


class _Corpus:
    def __init__(self, utterances):
        self._utterances = utterances

    def iter_utterances(self):
        return iter(self._utterances)


def _pipeline_corpus():
    utterances = [
        _Utterance(author, period, {"depth": 0, "subreddit": group, "parsed": words})
        for group, period, author, words in LEXICAL
    ]
    lexical_authors = {(group, period, author) for group, period, author, _ in LEXICAL}
    # participation without a processed top-level comment (replies): it only counts as activity
    utterances += [
        _Utterance(author, period, {"depth": 1, "subreddit": group})
        for group, period, author in ACTIVITY
        if (group, period, author) not in lexical_authors
    ]
    # a reply with words carries no lexical weight, and a month outside the window is ignored entirely
    utterances.append(_Utterance("u2", "2024-01", {"depth": 1, "subreddit": "A", "parsed": ["bacon"]}))
    utterances.append(_Utterance("u9", "2023-12", {"depth": 0, "subreddit": "A", "parsed": ["decoy"]}))
    return _Corpus(utterances)


def test_from_corpus_reproduces_the_fixture_values():
    metrics = IdentityMetrics.from_corpus(
        _pipeline_corpus(),
        group_key="subreddit",
        period_type="m",
        words_field="parsed",
        lexical_depths=(0,),
        activity_depths=None,
        period_range=("2024-01", "2024-02"),
        min_percentile=None,
        log_base=2,
    )
    _assert_all_values(metrics)
