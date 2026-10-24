"""Parity tests: IdentityMetrics must reproduce the exact values computed by the
manual algorithm used in reddit-diets-communities.ipynb (compute_words / specificity /
volatility / distinctiveness / dynamicity / retention), to 4 decimal places.

The reference functions below are a faithful transcription of the notebook's
code, adapted to read from plain (group, period, author, words) records
instead of live ConvoKit queries, so the fixture does not depend on the large
external Reddit dataset used by the notebook.
"""

import json
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from comid import Comid, __version__
from comid.metrics import IdentityMetrics

# --- Reference implementation (transcribed from reddit-diets-communities.ipynb) ----


def _notebook_compute_words(records, group, period, percentile=95):
    """Port of the notebook's `compute_words(community, period)`."""
    word_map = {}
    speakers = {}
    for rec_group, rec_period, author, words in records:
        if rec_group != group or rec_period != period:
            continue
        words = [w for w in words if (author not in speakers or w not in speakers[author])]
        speakers[author] = set(words)
        for w in words:
            word_map[w] = word_map.get(w, 0) + 1
    if word_map:
        threshold = np.percentile(list(word_map.values()), percentile)
        word_map = {w: c for w, c in word_map.items() if c >= threshold}
    return word_map


def _notebook_tables(records, groups, periods, percentile=95):
    """Port of the notebook's communities_periods/words_periods/communities_words build-up."""
    communities_periods = {g: {} for g in groups}
    words_periods = {}
    communities_words = {g: {} for g in groups}
    for group in groups:
        for period in periods:
            words_dict = _notebook_compute_words(records, group, period, percentile)
            communities_periods[group][period] = words_dict
            for word, count in words_dict.items():
                words_periods.setdefault(word, {})
                words_periods[word][period] = words_periods[word].get(period, 0) + count
                communities_words[group][word] = communities_words[group].get(word, 0) + count
    return communities_periods, words_periods, communities_words


def _notebook_specificity(communities_periods, words_periods, word, group, period, log_base=10):
    """Port of the notebook's `specificity(word, community, period)`."""
    if word not in communities_periods[group][period]:
        return None
    a = communities_periods[group][period][word] / sum(communities_periods[group][period].values())
    b = words_periods[word][period] / sum(w[period] if period in w else 0 for w in words_periods.values())
    return math.log(a / b, log_base)


def _notebook_volatility(communities_periods, communities_words, word, group, period, log_base=10):
    """Port of the notebook's `volatility(word, community, period)`."""
    if word not in communities_periods[group][period]:
        return None
    a = communities_periods[group][period][word] / sum(communities_periods[group][period].values())
    b = communities_words[group][word] / sum(communities_words[group].values())
    return math.log(a / b, log_base)


def _notebook_distinctiveness(communities_periods, words_periods, group, log_base=10):
    """Port of the notebook's `distinctiveness(community)`."""
    arr = [
        _notebook_specificity(communities_periods, words_periods, word, group, period, log_base)
        for period in communities_periods[group]
        for word in communities_periods[group][period]
    ]
    return float(np.mean(arr))


def _notebook_dynamicity(communities_periods, communities_words, group, log_base=10):
    """Port of the notebook's `dynamicity(community)`."""
    arr = [
        _notebook_volatility(communities_periods, communities_words, word, group, period, log_base)
        for period in communities_periods[group]
        for word in communities_periods[group][period]
    ]
    return float(np.mean(arr))


def _notebook_retention(records, group, periods):
    """Port of the notebook's `retention(community)` (activity = lexical authors)."""
    active = {}
    for rec_group, rec_period, author, _words in records:
        if rec_group != group:
            continue
        active.setdefault(rec_period, set()).add(author)
    arr = np.zeros(len(periods) - 1)
    for i in range(len(periods) - 1):
        users_t0 = active.get(periods[i], set())
        if not users_t0:
            continue
        users_t1 = active.get(periods[i + 1], set())
        arr[i] = len(users_t0 & users_t1) / len(users_t0)
    return float(arr.mean())


# --- Synthetic fixture (small, deterministic stand-in for the Reddit corpus) ---

GROUPS = ["keto", "vegan"]
PERIODS = ["2024-01", "2024-02", "2024-03"]

RECORDS = [
    ("keto", "2024-01", "k1", ["egg", "bacon"]),
    ("keto", "2024-01", "k1", ["egg", "keto"]),  # k1's 2nd utterance in the same period -> dedup 'egg'
    ("keto", "2024-01", "k2", ["egg", "butter"]),
    ("keto", "2024-02", "k1", ["egg", "cheese"]),
    ("keto", "2024-02", "k3", ["keto", "bacon"]),
    ("keto", "2024-03", "k1", ["egg", "keto"]),
    ("keto", "2024-03", "k2", ["butter", "keto"]),
    ("vegan", "2024-01", "v1", ["tofu", "vegan"]),
    ("vegan", "2024-01", "v2", ["tofu", "beans"]),
    ("vegan", "2024-02", "v1", ["tofu", "vegan"]),
    ("vegan", "2024-02", "v3", ["vegan", "beans"]),
    ("vegan", "2024-03", "v1", ["tofu", "seitan"]),
    ("vegan", "2024-03", "v2", ["vegan", "beans"]),
]


@pytest.fixture
def notebook_reference():
    """The notebook's tables/metrics computed by the transcribed reference algorithm."""
    communities_periods, words_periods, communities_words = _notebook_tables(RECORDS, GROUPS, PERIODS)
    return communities_periods, words_periods, communities_words


@pytest.fixture
def metrics():
    """IdentityMetrics built with the same parameters as the notebook (percentile 95, log10)."""
    return IdentityMetrics(RECORDS, min_percentile=95, log_base=10, speaker_dedup=True)


def test_word_tables_match_notebook_vocabulary(metrics, notebook_reference):
    communities_periods, _, _ = notebook_reference
    for group in GROUPS:
        for period in PERIODS:
            expected_words = communities_periods[group][period]
            table = metrics.word_table(group, period).set_index("word")["count"].to_dict()
            assert table == expected_words


def test_specificity_matches_notebook(metrics, notebook_reference):
    communities_periods, words_periods, _ = notebook_reference
    for group in GROUPS:
        for period in PERIODS:
            for word in communities_periods[group][period]:
                expected = _notebook_specificity(communities_periods, words_periods, word, group, period)
                assert metrics.specificity(word, group, period) == pytest.approx(expected, abs=1e-4)


def test_volatility_matches_notebook(metrics, notebook_reference):
    communities_periods, _, communities_words = notebook_reference
    for group in GROUPS:
        for period in PERIODS:
            for word in communities_periods[group][period]:
                expected = _notebook_volatility(communities_periods, communities_words, word, group, period)
                assert metrics.volatility(word, group, period) == pytest.approx(expected, abs=1e-4)


def test_distinctiveness_dynamicity_retention_match_notebook(metrics, notebook_reference):
    communities_periods, words_periods, communities_words = notebook_reference
    for group in GROUPS:
        expected_distinctiveness = _notebook_distinctiveness(communities_periods, words_periods, group)
        expected_dynamicity = _notebook_dynamicity(communities_periods, communities_words, group)
        expected_retention = _notebook_retention(RECORDS, group, PERIODS)

        assert metrics.distinctiveness(group) == pytest.approx(expected_distinctiveness, abs=1e-4)
        assert metrics.dynamicity(group) == pytest.approx(expected_dynamicity, abs=1e-4)
        assert metrics.retention(group) == pytest.approx(expected_retention, abs=1e-4)


def test_series_and_summary_shapes(metrics):
    series = metrics.series()
    summary = metrics.summary()

    assert len(series) == len(GROUPS) * len(PERIODS)
    assert set(series["group"]) == set(GROUPS)
    assert len(summary) == len(GROUPS)
    assert set(summary["group"]) == set(GROUPS)
    # Last period of each group has no next period to compute retention against.
    last_period_rows = series[series["period"] == PERIODS[-1]]
    assert last_period_rows["retention_next"].isna().all()


def test_save_writes_three_files_and_is_deterministic(metrics, tmp_path):
    folder_a = tmp_path / "run_a"
    folder_b = tmp_path / "run_b"
    metrics.save(str(folder_a))
    IdentityMetrics(RECORDS, min_percentile=95, log_base=10, speaker_dedup=True).save(str(folder_b))

    for name in ("summary.csv", "series.csv", "params.json"):
        assert (folder_a / name).exists()
        assert (folder_a / name).read_bytes() == (folder_b / name).read_bytes()


def test_min_percentile_none_disables_filter(notebook_reference):
    """min_percentile=None must keep every word instead of raising in np.percentile."""
    communities_periods, _, _ = notebook_reference
    unfiltered = IdentityMetrics(RECORDS, min_percentile=None, log_base=10, speaker_dedup=True)

    expected = _notebook_tables(RECORDS, GROUPS, PERIODS, percentile=0)[0]
    for group in GROUPS:
        for period in PERIODS:
            table = unfiltered.word_table(group, period).set_index("word")["count"].to_dict()
            assert table == expected[group][period]
            # sanity check: with percentile=95 some of these words get filtered out
            assert set(table) >= set(communities_periods[group][period])


# --- Minimal ConvoKit stand-ins for from_corpus tests ---


class _FakeSpeaker:
    def __init__(self, id):
        self.id = id


class _FakeUtterance:
    def __init__(self, meta, timestamp, speaker_id):
        self.meta = meta
        self.timestamp = timestamp
        self.speaker = _FakeSpeaker(speaker_id)


class _FakeCorpus:
    def __init__(self, utterances):
        self._utterances = utterances

    def iter_utterances(self):
        return iter(self._utterances)


def _utc_timestamp(year, month, day=1):
    return datetime(year, month, day, tzinfo=timezone.utc).timestamp()


def test_from_corpus_skips_empty_words_and_restricts_activity_depths():
    utterances = [
        _FakeUtterance({"depth": 0, "subreddit": "keto"}, _utc_timestamp(2024, 1), "a1"),
        _FakeUtterance({"depth": 0, "subreddit": "keto"}, _utc_timestamp(2024, 1), "a2"),  # empty words below
        _FakeUtterance({"depth": 1, "subreddit": "keto"}, _utc_timestamp(2024, 1), "a3"),
    ]
    utterances[0].meta["words"] = ["egg"]
    utterances[1].meta["words"] = []  # falsy -> not a lexical record
    utterances[2].meta["words"] = ["egg"]
    corpus = _FakeCorpus(utterances)

    metrics = IdentityMetrics.from_corpus(
        corpus, words_field="words", lexical_depths=(0,), activity_depths=(0,), min_percentile=0
    )
    series = metrics.series()
    row = series.iloc[0]
    assert row["n_lexical"] == 1  # only a1's utterance has non-empty words
    assert row["n_active"] == 2  # a1 and a2 (both depth 0); a3's depth-1 is excluded by activity_depths=(0,)


def test_period_key_is_utc_independent_of_local_timezone():
    """Comid.period_key must use UTC, not the machine's local timezone."""
    # 2024-02-01T00:00:00Z: a naive datetime.fromtimestamp() in a negative-offset
    # local timezone would still read as January 31st.
    assert Comid.period_key(_utc_timestamp(2024, 2), "m") == "2024-02"
    assert Comid.period_key(_utc_timestamp(2024, 2), "d") == "2024-02-01"
    assert Comid.period_key(_utc_timestamp(2024, 1), "y") == "2024"


def test_from_corpus_period_range_filters_lexical_and_activity():
    utterances = [
        _FakeUtterance({"depth": 0, "subreddit": "keto"}, _utc_timestamp(2024, 1), "a1"),
        _FakeUtterance({"depth": 0, "subreddit": "keto"}, _utc_timestamp(2024, 2), "a2"),
        _FakeUtterance({"depth": 0, "subreddit": "keto"}, _utc_timestamp(2024, 3), "a3"),
        _FakeUtterance({"depth": 1, "subreddit": "keto"}, _utc_timestamp(2024, 3), "a4"),
    ]
    for utt in utterances:
        utt.meta["words"] = ["egg", "bacon"]
    corpus = _FakeCorpus(utterances)

    metrics = IdentityMetrics.from_corpus(
        corpus,
        words_field="words",
        lexical_depths=(0,),
        activity_depths=None,
        period_range=("2024-01", "2024-02"),
        min_percentile=0,
    )

    series = metrics.series()
    assert set(series["period"]) == {"2024-01", "2024-02"}
    # the march-only depth=1 activity record must be excluded too
    assert series.loc[series["period"] == "2024-02", "n_active"].item() == 1


def test_sample_per_period_caps_lexical_but_not_activity():
    records = [("keto", "2024-01", f"a{i}", ["egg", f"word{i}"]) for i in range(10)]

    sampled = IdentityMetrics(records, min_percentile=0, sample_per_period=3, seed=42)
    series = sampled.series()
    row = series[series["period"] == "2024-01"].iloc[0]

    assert row["n_lexical"] == 3
    assert row["n_active"] == 10  # activity is never subsampled
    assert bool(row["sampled"]) is True

    # deterministic given the same seed
    again = IdentityMetrics(records, min_percentile=0, sample_per_period=3, seed=42)
    assert sampled.word_table("keto", "2024-01").equals(again.word_table("keto", "2024-01"))

    # a (group, period) with fewer records than the cap is kept whole and marked unsampled
    small = IdentityMetrics(records[:2], min_percentile=0, sample_per_period=3, seed=42)
    small_row = small.series()[small.series()["period"] == "2024-01"].iloc[0]
    assert small_row["n_lexical"] == 2
    assert bool(small_row["sampled"]) is False


def test_sample_per_period_same_seed_identical_different_seed_differs():
    records = [("keto", "2024-01", f"a{i}", ["egg", f"word{i}"]) for i in range(10)]

    seed_42_a = IdentityMetrics(records, min_percentile=0, sample_per_period=3, seed=42)
    seed_42_b = IdentityMetrics(records, min_percentile=0, sample_per_period=3, seed=42)
    seed_99 = IdentityMetrics(records, min_percentile=0, sample_per_period=3, seed=99)

    assert seed_42_a.word_table("keto", "2024-01").equals(seed_42_b.word_table("keto", "2024-01"))
    assert not seed_42_a.word_table("keto", "2024-01").equals(seed_99.word_table("keto", "2024-01"))


def test_save_params_json_records_full_configuration(tmp_path):
    utterances = [_FakeUtterance({"depth": 0, "subreddit": "keto"}, _utc_timestamp(2024, 1), "a1")]
    utterances[0].meta["words"] = ["egg"]
    corpus = _FakeCorpus(utterances)

    metrics = IdentityMetrics.from_corpus(
        corpus,
        words_field="words",
        period_range=("2024-01", "2024-01"),
        min_percentile=0,
        sample_per_period=5,
        seed=7,
    )
    metrics.save(str(tmp_path))

    with open(tmp_path / "params.json", encoding="utf-8") as f:
        params = json.load(f)

    assert params == {
        "group_key": "subreddit",
        "period_type": "m",
        "words_field": "words",
        "lexical_depths": [0],
        "activity_depths": None,
        "period_range": ["2024-01", "2024-01"],
        "sample_per_period": 5,
        "seed": 7,
        "min_percentile": 0,
        "log_base": 2,
        "speaker_dedup": True,
        "comid_version": __version__,
    }


def test_save_params_json_defaults_source_params_when_built_directly(tmp_path):
    """Instances built from plain records (no from_corpus/from_topics) have no adapter provenance."""
    IdentityMetrics(RECORDS, min_percentile=95, log_base=10).save(str(tmp_path))
    with open(tmp_path / "params.json", encoding="utf-8") as f:
        params = json.load(f)
    for key in ("group_key", "period_type", "words_field", "lexical_depths", "activity_depths", "period_range"):
        assert params[key] is None


# --- Bigger fixture: every metric (S, V, D, N=dynamicity, R), aggregated and per-period,
# percentile threshold, per-author dedup and the "empty intermediate period" rule ---

BIG_GROUPS = ["keto", "vegan"]
BIG_PERIODS = ["2024-01", "2024-02", "2024-03"]

BIG_RECORDS = [
    ("keto", "2024-01", "k1", ["keto", "diet"]),  # 1
    ("keto", "2024-01", "k2", ["keto", "carb"]),  # 2
    ("vegan", "2024-01", "v1", ["tofu", "vegan"]),  # 3
    ("keto", "2024-01", "k1", ["keto", "diet"]),  # 4: pure duplicate of #1 (same author, same words) -> no-op
    ("vegan", "2024-01", "v2", ["tofu", "bean"]),  # 5
    ("keto", "2024-03", "k1", ["keto", "cheese"]),  # 6: keto has no records at all in 2024-02
    ("keto", "2024-03", "k3", ["carb", "diet"]),  # 7
    ("vegan", "2024-02", "v1", ["tofu", "vegan"]),  # 8: vegan DOES have 2024-02 data
    ("vegan", "2024-02", "v3", ["seitan", "vegan"]),  # 9
    ("vegan", "2024-03", "v1", ["tofu", "seitan"]),  # 10
    ("vegan", "2024-03", "v2", ["vegan", "bean"]),  # 11
]


@pytest.fixture
def big_reference():
    """Reference tables for BIG_RECORDS with the percentile filter effectively disabled (percentile=0)."""
    return _notebook_tables(BIG_RECORDS, BIG_GROUPS, BIG_PERIODS, percentile=0)


@pytest.fixture
def big_metrics():
    """IdentityMetrics built from BIG_RECORDS with min_percentile=None, log_base=2 (the formal default)."""
    return IdentityMetrics(BIG_RECORDS, min_percentile=None, log_base=2, speaker_dedup=True)


def test_big_fixture_specificity_volatility_match_and_oov_word_is_none(big_metrics, big_reference):
    communities_periods, words_periods, communities_words = big_reference
    for group in BIG_GROUPS:
        for period in BIG_PERIODS:
            for word in communities_periods[group][period]:
                expected_s = _notebook_specificity(communities_periods, words_periods, word, group, period, log_base=2)
                expected_v = _notebook_volatility(communities_periods, communities_words, word, group, period, log_base=2)
                assert big_metrics.specificity(word, group, period) == pytest.approx(expected_s, abs=1e-9)
                assert big_metrics.volatility(word, group, period) == pytest.approx(expected_v, abs=1e-9)
    # a word outside the (filtered) vocabulary of a (group, period) is None
    assert big_metrics.specificity("does-not-exist", "keto", "2024-01") is None
    assert big_metrics.volatility("does-not-exist", "keto", "2024-01") is None
    # keto has no records at all in 2024-02 -> its vocabulary there is empty
    assert big_metrics.word_table("keto", "2024-02").empty
    assert big_metrics.specificity("keto", "keto", "2024-02") is None


def test_big_fixture_distinctiveness_dynamicity_aggregated_and_per_period(big_metrics, big_reference):
    communities_periods, words_periods, communities_words = big_reference
    for group in BIG_GROUPS:
        expected_d = _notebook_distinctiveness(communities_periods, words_periods, group, log_base=2)
        expected_n = _notebook_dynamicity(communities_periods, communities_words, group, log_base=2)
        assert big_metrics.distinctiveness(group) == pytest.approx(expected_d, abs=1e-9)
        assert big_metrics.dynamicity(group) == pytest.approx(expected_n, abs=1e-9)
        for period in BIG_PERIODS:
            vocab = communities_periods[group][period]
            if not vocab:
                continue
            expected_d_period = float(np.mean(
                [_notebook_specificity(communities_periods, words_periods, w, group, period, log_base=2) for w in vocab]
            ))
            expected_n_period = float(np.mean(
                [_notebook_volatility(communities_periods, communities_words, w, group, period, log_base=2) for w in vocab]
            ))
            assert big_metrics.distinctiveness(group, period) == pytest.approx(expected_d_period, abs=1e-9)
            assert big_metrics.dynamicity(group, period) == pytest.approx(expected_n_period, abs=1e-9)


def test_big_fixture_retention_aggregated_and_per_period(big_metrics):
    expected_keto = _notebook_retention(BIG_RECORDS, "keto", BIG_PERIODS)
    expected_vegan = _notebook_retention(BIG_RECORDS, "vegan", BIG_PERIODS)
    assert big_metrics.retention("keto") == pytest.approx(expected_keto, abs=1e-9)
    assert big_metrics.retention("vegan") == pytest.approx(expected_vegan, abs=1e-9)
    # keto -> 2024-02 is a real, computed zero (keto has activity in Jan but none in Feb), not skipped
    assert big_metrics.retention("keto", "2024-01") == pytest.approx(0.0, abs=1e-9)
    # the global last period has no next period: an explicit call must raise
    with pytest.raises(ValueError):
        big_metrics.retention("keto", "2024-03")


def test_big_fixture_fourth_record_is_a_pure_duplicate_and_changes_nothing():
    """Record #4 repeats author k1's exact words from record #1 in the same (group, period); per-author
    dedup must make it a no-op on every count."""
    without_fourth = BIG_RECORDS[:3] + BIG_RECORDS[4:]
    with_fourth = IdentityMetrics(BIG_RECORDS, min_percentile=None)
    without = IdentityMetrics(without_fourth, min_percentile=None)
    for group in BIG_GROUPS:
        for period in BIG_PERIODS:
            assert with_fourth.word_table(group, period).equals(without.word_table(group, period))


def test_big_fixture_empty_intermediate_month_is_ignored_not_counted_as_zero(big_metrics):
    """keto has zero records in 2024-02 (unlike vegan): it must be absent from series(), and the
    aggregated distinctiveness/dynamicity for keto must average only over 2024-01/2024-03 instead of
    treating the missing month as a zero-vocabulary period."""
    series = big_metrics.series()
    keto_periods = set(series.loc[series["group"] == "keto", "period"])
    assert keto_periods == {"2024-01", "2024-03"}

    keto_specificities = [
        big_metrics.specificity(word, "keto", period)
        for period in ("2024-01", "2024-03")
        for word in big_metrics.word_table("keto", period)["word"]
    ]
    assert big_metrics.distinctiveness("keto") == pytest.approx(float(np.mean(keto_specificities)), abs=1e-9)

    # vegan DOES have (real, non-skipped) data in 2024-02, so it stays in its series
    vegan_periods = set(series.loc[series["group"] == "vegan", "period"])
    assert vegan_periods == {"2024-01", "2024-02", "2024-03"}


def test_percentile_95_keeps_only_the_dominant_word():
    """{a:5, b:1, c:1, d:1, e:1} with min_percentile=95 keeps only 'a' (np.percentile(...) == 4.2)."""
    records = [
        ("g", "p", "s1", ["a", "b"]),
        ("g", "p", "s2", ["a", "c"]),
        ("g", "p", "s3", ["a", "d"]),
        ("g", "p", "s4", ["a", "e"]),
        ("g", "p", "s5", ["a"]),
    ]
    assert np.percentile([5, 1, 1, 1, 1], 95) == pytest.approx(4.2)
    metrics = IdentityMetrics(records, min_percentile=95)
    table = metrics.word_table("g", "p").set_index("word")["count"].to_dict()
    assert table == {"a": 5}


def test_log_base_10_reproduces_notebook_scale_via_log10_2():
    """S(log_base=10) == S(log_base=2) * log10(2), the base-change used to match the notebook's scale."""
    metrics_base2 = IdentityMetrics(BIG_RECORDS, min_percentile=None, log_base=2)
    metrics_base10 = IdentityMetrics(BIG_RECORDS, min_percentile=None, log_base=10)
    scale = math.log10(2)
    for group in BIG_GROUPS:
        for period in BIG_PERIODS:
            for word in metrics_base2.word_table(group, period)["word"]:
                s2 = metrics_base2.specificity(word, group, period)
                s10 = metrics_base10.specificity(word, group, period)
                assert s10 == pytest.approx(s2 * scale, abs=1e-9)
                v2 = metrics_base2.volatility(word, group, period)
                v10 = metrics_base10.volatility(word, group, period)
                assert v10 == pytest.approx(v2 * scale, abs=1e-9)


def test_retention_raises_when_no_consecutive_pair_exists():
    records = [
        ("lonely", "2024-03", "x1", ["word"]),  # only data point, at the GLOBAL last period
        ("other", "2024-01", "y1", ["word"]),
        ("other", "2024-02", "y1", ["word"]),
        ("other", "2024-03", "y1", ["word"]),
    ]
    metrics = IdentityMetrics(records, min_percentile=0)
    with pytest.raises(ValueError):
        metrics.retention("lonely")
    with pytest.raises(ValueError):
        metrics.retention("lonely", "2024-03")


def test_retention_raises_when_period_has_no_active_users():
    lexical = [("g", "2024-01", "a1", ["x"]), ("g", "2024-02", "a1", ["x"])]
    metrics = IdentityMetrics(lexical, activity=[], min_percentile=0)
    with pytest.raises(ValueError):
        metrics.retention("g", "2024-01")


def test_speaker_dedup_false_counts_once_per_lexical_record():
    """With speaker_dedup=False, a word repeated by the same author across two records in the
    same (group, period) is counted twice, unlike the speaker_dedup=True (default) behavior."""
    records = [
        ("g", "p", "a1", ["x"]),
        ("g", "p", "a1", ["x"]),  # same author, same word, a second record
    ]
    deduped = IdentityMetrics(records, min_percentile=0, speaker_dedup=True)
    raw = IdentityMetrics(records, min_percentile=0, speaker_dedup=False)
    assert deduped.word_table("g", "p").set_index("word")["count"].to_dict() == {"x": 1}
    assert raw.word_table("g", "p").set_index("word")["count"].to_dict() == {"x": 2}


def test_word_table_empty_for_missing_group_period():
    metrics = IdentityMetrics(RECORDS, min_percentile=95, log_base=10)
    df = metrics.word_table("nonexistent-group", "2024-01")
    assert df.empty
    assert list(df.columns) == ["word", "count", "specificity", "volatility"]


def test_summary_nan_for_group_with_no_vocabulary():
    lexical = [("has_words", "2024-01", "a1", ["x"])]
    activity = [("has_words", "2024-01", "a1"), ("silent", "2024-01", "z1")]
    metrics = IdentityMetrics(lexical, activity, min_percentile=0)
    summary = metrics.summary()
    silent_row = summary[summary["group"] == "silent"].iloc[0]
    assert silent_row["n_lexical"] == 0
    assert silent_row["n_active"] == 1
    assert math.isnan(silent_row["mean_vocab_size"])
    assert math.isnan(silent_row["distinctiveness"])
    assert math.isnan(silent_row["dynamicity"])
    assert math.isnan(silent_row["retention_mean"])
    assert math.isnan(silent_row["retention_sd"])


# --- from_topics coverage: df_topics/corpus validation, lexical/activity extraction, period_range ---


class _FakeComid:
    def __init__(self, df_topics=None, corpus=None):
        self.df_topics = df_topics
        self.corpus = corpus


def _topics_dataframe(rows):
    return pd.DataFrame(rows).set_index("id")


def test_from_topics_raises_without_df_topics_or_corpus():
    with pytest.raises(ValueError):
        IdentityMetrics.from_topics(_FakeComid(df_topics=None, corpus={}))

    df = _topics_dataframe(
        [{"id": "d1", "topic": "t", "author_id": "a", "depth": 0, "created_utc": _utc_timestamp(2024, 1)}]
    )
    with pytest.raises(ValueError):
        IdentityMetrics.from_topics(_FakeComid(df_topics=df, corpus=None))


def test_from_topics_builds_lexical_and_activity_records():
    df = _topics_dataframe(
        [
            {"id": "d1", "topic": "keto", "author_id": "a1", "depth": 0, "created_utc": _utc_timestamp(2024, 1)},
            {"id": "d2", "topic": "keto", "author_id": "a2", "depth": 1, "created_utc": _utc_timestamp(2024, 1)},
            {"id": "d3", "topic": float("nan"), "author_id": "a3", "depth": 0, "created_utc": _utc_timestamp(2024, 1)},
            {"id": "d4", "topic": "keto", "author_id": "a4", "depth": 0, "created_utc": _utc_timestamp(2024, 2)},
        ]
    )
    corpus = {"d1": ["egg"], "d2": ["egg"], "d4": []}  # d3 has no topic (skipped); d4's words are empty
    metrics = IdentityMetrics.from_topics(_FakeComid(df_topics=df, corpus=corpus), min_percentile=0)

    series = metrics.series()
    assert set(series["period"]) == {"2024-01", "2024-02"}
    row_jan = series[series["period"] == "2024-01"].iloc[0]
    assert row_jan["n_lexical"] == 2  # d1 and d2 both have non-empty words (no depth filter by default)
    assert row_jan["n_active"] == 2  # d1 and d2 both count as activity (no depth filter by default)
    row_feb = series[series["period"] == "2024-02"].iloc[0]
    assert row_feb["n_lexical"] == 0  # d4's words are empty -> not a lexical record
    assert row_feb["n_active"] == 1


def test_from_topics_period_range_and_depth_filters():
    df = _topics_dataframe(
        [
            {"id": "d1", "topic": "keto", "author_id": "a1", "depth": 0, "created_utc": _utc_timestamp(2024, 1)},
            {"id": "d2", "topic": "keto", "author_id": "a2", "depth": 0, "created_utc": _utc_timestamp(2024, 2)},
            {"id": "d3", "topic": "keto", "author_id": "a3", "depth": 1, "created_utc": _utc_timestamp(2024, 1)},
        ]
    )
    corpus = {"d1": ["egg"], "d2": ["egg"], "d3": ["egg"]}
    metrics = IdentityMetrics.from_topics(
        _FakeComid(df_topics=df, corpus=corpus),
        lexical_depths=(0,),
        activity_depths=(0,),
        period_range=("2024-01", "2024-01"),
        min_percentile=0,
    )
    series = metrics.series()
    assert set(series["period"]) == {"2024-01"}
    row = series.iloc[0]
    assert row["n_lexical"] == 1  # only d1 (depth 0, within range)
    assert row["n_active"] == 1  # d3 excluded (depth 1), d2 excluded (out of range)
