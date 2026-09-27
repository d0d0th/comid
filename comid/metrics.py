import json
import math
import os
from collections import Counter, defaultdict
from typing import (
    Any,
    DefaultDict,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)

import numpy as np
import pandas as pd
from tqdm import tqdm

from . import Comid

__all__ = ["IdentityMetrics"]

#: A lexical record is (group, period, author, words) used to build word counts.
LexicalRecord = Tuple[str, str, str, Iterable[str]]
#: An activity record is (group, period, author) used only for retention.
ActivityRecord = Tuple[str, str, str]


class IdentityMetrics:
    """Compute specificity, volatility, distinctiveness, dynamicity and retention.

    The class stores, per (group, period), the counts of how many distinct
    speakers used each word (or the raw word frequency, depending on
    ``speaker_dedup``), keeping only words at or above the ``min_percentile``
    percentile of that (group, period) distribution -- the "filtered
    vocabulary". All public metrics are simple lookups/aggregations over the
    tables built once in the constructor.
    """

    def __init__(
        self,
        lexical: Iterable[LexicalRecord],
        activity: Optional[Iterable[ActivityRecord]] = None,
        *,
        min_percentile: float = 95,
        log_base: float = 2,
        speaker_dedup: bool = True,
    ) -> None:
        """Build the count tables from simple lexical/activity records.

        Parameters:
            lexical: iterable of ``(group, period, author, words)``, one entry
                per utterance/document. ``words`` is any iterable of tokens.
            activity: iterable of ``(group, period, author)`` used to compute
                retention. If ``None``, activity is derived from ``lexical``
                (every author of a lexical record is considered active in
                that group/period).
            min_percentile: percentile (0-100) used to filter, per (group,
                period), the vocabulary down to its most frequent words. Only
                words whose count is greater than or equal to this percentile
                of the (group, period) count distribution are kept.
            log_base: base of the logarithm used by specificity/volatility.
            speaker_dedup: if ``True`` (default), a word is counted at most
                once per speaker within a given (group, period), matching the
                methodology used in the case study. If ``False``, a word is
                counted once per lexical record (duplicate words within the
                same record are still collapsed to one occurrence).

        The whole table is built with a single pass over ``lexical`` (and, if
        given, a single pass over ``activity``); every public metric is then a
        dictionary lookup or an aggregation over the already-filtered tables.
        """
        self.min_percentile = min_percentile
        self.log_base = log_base
        self.speaker_dedup = speaker_dedup

        raw_counts: DefaultDict[str, DefaultDict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
        n_lexical: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        speakers_lexical: DefaultDict[str, DefaultDict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        seen_words: DefaultDict[Tuple[str, str, str], Set[str]] = defaultdict(set)

        for group, period, author, words in tqdm(lexical, desc="Counting words"):
            n_lexical[group][period] += 1
            speakers_lexical[group][period].add(author)
            word_set = set(words)
            if speaker_dedup:
                key = (group, period, author)
                new_words = word_set - seen_words[key]
                if new_words:
                    seen_words[key].update(new_words)
                    for word in new_words:
                        raw_counts[group][period][word] += 1
            else:
                for word in word_set:
                    raw_counts[group][period][word] += 1

        self._n_lexical: Dict[str, Dict[str, int]] = {g: dict(p) for g, p in n_lexical.items()}
        self._speakers_lexical: Dict[str, Dict[str, Set[str]]] = {
            g: {p: set(s) for p, s in periods.items()} for g, periods in speakers_lexical.items()
        }

        # Filter each (group, period) vocabulary down to its top `min_percentile`.
        self._counts: Dict[str, Dict[str, Dict[str, int]]] = {}
        for group, periods_map in raw_counts.items():
            self._counts[group] = {}
            for period, counter in periods_map.items():
                values = list(counter.values())
                if values:
                    threshold = float(np.percentile(values, min_percentile))
                    filtered = {word: count for word, count in counter.items() if count >= threshold}
                else:
                    filtered = {}
                self._counts[group][period] = filtered

        # Aggregate the (already filtered) tables; these are small compared to the raw utterances.
        word_period_totals: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        group_word_totals: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        period_totals: DefaultDict[str, int] = defaultdict(int)
        group_period_sum: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))

        for group, periods_map in self._counts.items():
            for period, words_map in periods_map.items():
                total = sum(words_map.values())
                group_period_sum[group][period] = total
                period_totals[period] += total
                for word, count in words_map.items():
                    word_period_totals[word][period] += count
                    group_word_totals[group][word] += count

        self._word_period_totals: Dict[str, Dict[str, int]] = {w: dict(p) for w, p in word_period_totals.items()}
        self._group_word_totals: Dict[str, Dict[str, int]] = {g: dict(w) for g, w in group_word_totals.items()}
        self._period_totals: Dict[str, int] = dict(period_totals)
        self._group_period_sum: Dict[str, Dict[str, int]] = {g: dict(p) for g, p in group_period_sum.items()}
        self._group_totals: Dict[str, int] = {
            group: sum(word_map.values()) for group, word_map in self._group_word_totals.items()
        }

        # Active users per (group, period), used only for retention.
        active: DefaultDict[str, DefaultDict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        if activity is None:
            for group, periods_map in self._speakers_lexical.items():
                for period, speakers_set in periods_map.items():
                    active[group][period] = set(speakers_set)
        else:
            for group, period, author in tqdm(activity, desc="Counting activity"):
                active[group][period].add(author)
        self._active: Dict[str, Dict[str, Set[str]]] = {g: dict(p) for g, p in active.items()}

        self._groups: List[str] = sorted(set(self._counts.keys()) | set(self._active.keys()))
        self._periods: List[str] = sorted(
            {period for periods_map in self._counts.values() for period in periods_map}
            | {period for periods_map in self._active.values() for period in periods_map}
        )
        self._period_index: Dict[str, int] = {period: i for i, period in enumerate(self._periods)}

    @classmethod
    def from_corpus(
        cls,
        corpus: Any,
        *,
        group_key: str = "subreddit",
        period_type: str = "m",
        words_field: str = "parsed",
        lexical_depths: Sequence[int] = (0,),
        activity_depths: Optional[Sequence[int]] = None,
        **kw: Any,
    ) -> "IdentityMetrics":
        """Build an :class:`IdentityMetrics` from a ConvoKit ``Corpus``.

        Lexical records are the utterances whose ``meta["depth"]`` is in
        ``lexical_depths`` and that have a truthy ``meta[words_field]``.
        Activity records are all utterances (``activity_depths=None``) or
        only those whose ``meta["depth"]`` is in ``activity_depths``. The
        period comes from ``Comid.period_key(utt.timestamp, period_type)``
        and the author is ``utt.speaker.id``.

        Parameters:
            corpus: a ConvoKit ``Corpus`` exposing ``iter_utterances()``.
            group_key: metadata key that identifies the group (e.g. subreddit).
            period_type: period granularity, forwarded to ``Comid.period_key``.
            words_field: metadata key holding the pre-tokenized word list.
            lexical_depths: utterance depths considered for word counts.
            activity_depths: utterance depths considered for activity/retention;
                ``None`` means every utterance counts as activity.
            **kw: extra keyword arguments forwarded to the constructor
                (``min_percentile``, ``log_base``, ``speaker_dedup``).

        Returns:
            IdentityMetrics: the metrics built from the corpus.
        """
        lexical_depths_set = set(lexical_depths)
        activity_depths_set = set(activity_depths) if activity_depths is not None else None

        def lexical_records() -> Iterable[LexicalRecord]:
            for utt in corpus.iter_utterances():
                if utt.meta.get("depth") not in lexical_depths_set:
                    continue
                words = utt.meta.get(words_field)
                if not words:
                    continue
                group = utt.meta.get(group_key)
                period = Comid.period_key(utt.timestamp, period_type)
                yield group, period, utt.speaker.id, words

        def activity_records() -> Iterable[ActivityRecord]:
            for utt in corpus.iter_utterances():
                if activity_depths_set is not None and utt.meta.get("depth") not in activity_depths_set:
                    continue
                group = utt.meta.get(group_key)
                period = Comid.period_key(utt.timestamp, period_type)
                yield group, period, utt.speaker.id

        return cls(lexical_records(), activity_records(), **kw)

    @classmethod
    def from_topics(
        cls,
        comid: "Comid",
        *,
        period_type: str = "m",
        lexical_depths: Optional[Sequence[int]] = None,
        activity_depths: Optional[Sequence[int]] = None,
        **kw: Any,
    ) -> "IdentityMetrics":
        """Build an :class:`IdentityMetrics` from ``Comid.df_topics``.

        Group is the topic, author is ``author_id`` and words are the tokenized text of the
        document, looked up in ``comid.corpus`` by document id. The period comes from
        ``Comid.period_key(created_utc, period_type)``. Rows without a topic are skipped.
        ``lexical_depths``/``activity_depths`` optionally restrict rows by the ``depth`` column;
        ``None`` (the default for both) means every row, matching ``Comid``'s own
        ``distinctiveness``/``dynamicity``/``specificity``/``volatility``, which do not filter by depth.

        Parameters:
            comid: a ``Comid`` instance with a populated ``df_topics`` and ``corpus``.
            period_type: period granularity, forwarded to ``Comid.period_key``.
            lexical_depths: ``depth`` values considered for word counts, or ``None`` for all.
            activity_depths: ``depth`` values considered for activity/retention, or ``None`` for all.
            **kw: extra keyword arguments forwarded to the constructor
                (``min_percentile``, ``log_base``, ``speaker_dedup``).

        Raises:
            ValueError: if ``comid.df_topics`` or ``comid.corpus`` has not been built yet.

        Returns:
            IdentityMetrics: the metrics built from the topics dataframe.
        """
        if comid.df_topics is None:
            raise ValueError("comid.df_topics is empty; call Comid.build_topics(...) first.")
        if comid.corpus is None:
            raise ValueError("comid.corpus is empty; call Comid.generate_corpus(...) first.")

        corpus = comid.corpus
        lexical_depths_set = set(lexical_depths) if lexical_depths is not None else None
        activity_depths_set = set(activity_depths) if activity_depths is not None else None

        def lexical_records() -> Iterable[LexicalRecord]:
            for doc_id, row in comid.df_topics.iterrows():
                if pd.isnull(row["topic"]):
                    continue
                if lexical_depths_set is not None and row["depth"] not in lexical_depths_set:
                    continue
                words = corpus.get(doc_id)
                if not words:
                    continue
                period = Comid.period_key(row["created_utc"], period_type)
                yield row["topic"], period, row["author_id"], words

        def activity_records() -> Iterable[ActivityRecord]:
            for doc_id, row in comid.df_topics.iterrows():
                if pd.isnull(row["topic"]):
                    continue
                if activity_depths_set is not None and row["depth"] not in activity_depths_set:
                    continue
                period = Comid.period_key(row["created_utc"], period_type)
                yield row["topic"], period, row["author_id"]

        return cls(lexical_records(), activity_records(), **kw)

    def _next_period(self, period: str) -> Optional[str]:
        """Return the period immediately after `period` in the global period order, or None."""
        idx = self._period_index.get(period)
        if idx is None or idx + 1 >= len(self._periods):
            return None
        return self._periods[idx + 1]

    def _retention_value(self, group: str, period: str) -> Optional[float]:
        """Return R(group, period -> next period), or None if not computable."""
        users_t = self._active.get(group, {}).get(period, set())
        if not users_t:
            return None
        next_period = self._next_period(period)
        if next_period is None:
            return None
        users_t1 = self._active.get(group, {}).get(next_period, set())
        return len(users_t & users_t1) / len(users_t)

    def _retention_values(self, group: str) -> List[float]:
        """Return R(group, t -> t+1) for every consecutive pair with non-empty A_{group,t}."""
        periods = self._active.get(group, {}).keys()
        ordered = sorted(periods, key=lambda p: self._period_index.get(p, -1))
        values = []
        for period in ordered:
            value = self._retention_value(group, period)
            if value is not None:
                values.append(value)
        return values

    def specificity(self, word: str, group: str, period: str) -> Optional[float]:
        """Specificity of `word` in `group` during `period`.

        S(w, c, t) = log_b(a / b), where:
            a = count(w, c, t) / sum_w' count(w', c, t)   -- share of w within group c at period t
            b = count(w, ·, t) / sum_w' count(w', ·, t)   -- share of w across all groups at period t

        Returns:
            float: the specificity value, or None if `word` is not part of
            the filtered vocabulary of (`group`, `period`).
        """
        words = self._counts.get(group, {}).get(period)
        if not words or word not in words:
            return None
        a = words[word] / self._group_period_sum[group][period]
        b = self._word_period_totals[word][period] / self._period_totals[period]
        return math.log(a / b, self.log_base)

    def volatility(self, word: str, group: str, period: str) -> Optional[float]:
        """Volatility of `word` in `group` during `period`.

        V(w, c, t) = log_b(a / b), where:
            a = count(w, c, t) / sum_w' count(w', c, t)     -- share of w within group c at period t
            b = count(w, c, ·) / sum_w' count(w', c, ·)     -- share of w within group c across all periods

        Returns:
            float: the volatility value, or None if `word` is not part of
            the filtered vocabulary of (`group`, `period`).
        """
        words = self._counts.get(group, {}).get(period)
        if not words or word not in words:
            return None
        a = words[word] / self._group_period_sum[group][period]
        b = self._group_word_totals[group][word] / self._group_totals[group]
        return math.log(a / b, self.log_base)

    def distinctiveness(self, group: str, period: Optional[str] = None) -> float:
        """Distinctiveness of `group`, optionally restricted to `period`.

        With `period`: D(c, t) = mean of S(w, c, t) over the filtered
        vocabulary of (c, t).
        Without `period`: D(c) = mean of S(w, c, t) over every (period, word)
        pair of the filtered vocabulary of `group` across all periods.

        Returns:
            float: the mean specificity, or NaN if there is no data.
        """
        values: List[float] = []
        if period is not None:
            for word in self._counts.get(group, {}).get(period, {}):
                s = self.specificity(word, group, period)
                if s is not None:
                    values.append(s)
        else:
            for per, words in self._counts.get(group, {}).items():
                for word in words:
                    s = self.specificity(word, group, per)
                    if s is not None:
                        values.append(s)
        return float(np.mean(values)) if values else float("nan")

    def dynamicity(self, group: str, period: Optional[str] = None) -> float:
        """Dynamicity of `group`, optionally restricted to `period`.

        With `period`: Dy(c, t) = mean of V(w, c, t) over the filtered
        vocabulary of (c, t).
        Without `period`: Dy(c) = mean of V(w, c, t) over every (period,
        word) pair of the filtered vocabulary of `group` across all periods.

        Returns:
            float: the mean volatility, or NaN if there is no data.
        """
        values: List[float] = []
        if period is not None:
            for word in self._counts.get(group, {}).get(period, {}):
                v = self.volatility(word, group, period)
                if v is not None:
                    values.append(v)
        else:
            for per, words in self._counts.get(group, {}).items():
                for word in words:
                    v = self.volatility(word, group, per)
                    if v is not None:
                        values.append(v)
        return float(np.mean(values)) if values else float("nan")

    def retention(self, group: str, period: Optional[str] = None) -> float:
        """User retention of `group`, optionally restricted to `period`.

        With `period`: R(c, t -> t+1) = |A_{c,t} ∩ A_{c,t+1}| / |A_{c,t}|,
        where A_{c,t} is the set of active authors of group c in period t
        and t+1 is the period immediately after t in the global period order.
        Without `period`: the mean of R(c, t -> t+1) over every consecutive
        pair with a non-empty A_{c,t}.

        Raises:
            ValueError: if `period` has no computable retention (no next
                period, or A_{c,t} is empty), or -- when `period` is None --
                if no consecutive pair with a non-empty A_{c,t} exists.

        Returns:
            float: the retention rate.
        """
        if period is not None:
            value = self._retention_value(group, period)
            if value is None:
                raise ValueError(f"Retention is not computable for group '{group}' at period '{period}'.")
            return value
        values = self._retention_values(group)
        if not values:
            raise ValueError(f"No consecutive periods with active users found for group '{group}'.")
        return float(np.mean(values))

    def word_table(self, group: str, period: str) -> pd.DataFrame:
        """Filtered vocabulary of `group` at `period` with its metrics.

        Returns:
            pandas.DataFrame: columns ``word``, ``count``, ``specificity``,
            ``volatility``, sorted by ``count`` descending.
        """
        words = self._counts.get(group, {}).get(period, {})
        rows = [
            {
                "word": word,
                "count": count,
                "specificity": self.specificity(word, group, period),
                "volatility": self.volatility(word, group, period),
            }
            for word, count in words.items()
        ]
        df = pd.DataFrame(rows, columns=["word", "count", "specificity", "volatility"])
        return df.sort_values("count", ascending=False, kind="stable").reset_index(drop=True)

    def series(self) -> pd.DataFrame:
        """One row per (group, period) with counts and metrics.

        Returns:
            pandas.DataFrame: columns ``group``, ``period``, ``n_lexical``,
            ``n_speakers_lexical``, ``n_active``, ``vocab_size``,
            ``distinctiveness``, ``dynamicity``, ``retention_next`` (NaN at
            the last period of each group).
        """
        rows = []
        for group in self._groups:
            group_periods = [
                period
                for period in self._periods
                if period in self._counts.get(group, {}) or period in self._active.get(group, {})
            ]
            for period in group_periods:
                words = self._counts.get(group, {}).get(period, {})
                active_users = self._active.get(group, {}).get(period, set())
                lex_speakers = self._speakers_lexical.get(group, {}).get(period, set())
                retention_next = self._retention_value(group, period)
                rows.append(
                    {
                        "group": group,
                        "period": period,
                        "n_lexical": self._n_lexical.get(group, {}).get(period, 0),
                        "n_speakers_lexical": len(lex_speakers),
                        "n_active": len(active_users),
                        "vocab_size": len(words),
                        "distinctiveness": self.distinctiveness(group, period),
                        "dynamicity": self.dynamicity(group, period),
                        "retention_next": retention_next if retention_next is not None else float("nan"),
                    }
                )
        columns = [
            "group",
            "period",
            "n_lexical",
            "n_speakers_lexical",
            "n_active",
            "vocab_size",
            "distinctiveness",
            "dynamicity",
            "retention_next",
        ]
        return pd.DataFrame(rows, columns=columns).sort_values(["group", "period"]).reset_index(drop=True)

    def summary(self) -> pd.DataFrame:
        """One row per group, aggregating counts and metrics across periods.

        Returns:
            pandas.DataFrame: columns ``group``, ``n_lexical``,
            ``n_speakers_lexical``, ``n_active``, ``n_periods``,
            ``mean_vocab_size``, ``distinctiveness``, ``dynamicity``,
            ``retention_mean``, ``retention_sd``.
        """
        rows = []
        for group in self._groups:
            n_lexical = sum(self._n_lexical.get(group, {}).values())

            speaker_sets = self._speakers_lexical.get(group, {}).values()
            n_speakers_lexical = len(set().union(*speaker_sets)) if speaker_sets else 0

            active_sets = self._active.get(group, {}).values()
            n_active = len(set().union(*active_sets)) if active_sets else 0

            n_periods = len(set(self._counts.get(group, {}).keys()) | set(self._active.get(group, {}).keys()))

            vocab_sizes = [len(words) for words in self._counts.get(group, {}).values()]
            mean_vocab_size = float(np.mean(vocab_sizes)) if vocab_sizes else float("nan")

            retention_values = self._retention_values(group)
            retention_mean = float(np.mean(retention_values)) if retention_values else float("nan")
            retention_sd = float(np.std(retention_values, ddof=0)) if retention_values else float("nan")

            rows.append(
                {
                    "group": group,
                    "n_lexical": n_lexical,
                    "n_speakers_lexical": n_speakers_lexical,
                    "n_active": n_active,
                    "n_periods": n_periods,
                    "mean_vocab_size": mean_vocab_size,
                    "distinctiveness": self.distinctiveness(group),
                    "dynamicity": self.dynamicity(group),
                    "retention_mean": retention_mean,
                    "retention_sd": retention_sd,
                }
            )
        columns = [
            "group",
            "n_lexical",
            "n_speakers_lexical",
            "n_active",
            "n_periods",
            "mean_vocab_size",
            "distinctiveness",
            "dynamicity",
            "retention_mean",
            "retention_sd",
        ]
        return pd.DataFrame(rows, columns=columns).sort_values("group").reset_index(drop=True)

    def save(self, folder: str) -> None:
        """Write ``summary.csv``, ``series.csv`` and ``params.json`` to `folder`.

        `params.json` records the constructor parameters (``min_percentile``,
        ``log_base``, ``speaker_dedup``) so that the results folder describes
        itself.
        """
        os.makedirs(folder, exist_ok=True)
        self.summary().to_csv(os.path.join(folder, "summary.csv"), index=False)
        self.series().to_csv(os.path.join(folder, "series.csv"), index=False)
        params = {
            "min_percentile": self.min_percentile,
            "log_base": self.log_base,
            "speaker_dedup": self.speaker_dedup,
        }
        with open(os.path.join(folder, "params.json"), "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2, sort_keys=True)
