import json
import math
import os
import random
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

from . import Comid, __version__

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
        min_percentile: Optional[float] = 95,
        log_base: float = 2,
        speaker_dedup: bool = True,
        sample_per_period: Optional[int] = None,
        seed: Optional[int] = None,
        background: str = "filtered",
    ) -> None:
        """Build the count tables from simple lexical/activity records.

        Parameters:
            lexical: iterable of ``(group, period, author, words)``, one entry
                per utterance/document. ``words`` is any iterable of tokens.
            activity: iterable of ``(group, period, author)`` used to compute
                retention. If ``None``, activity is derived from ``lexical``
                (every author of a lexical record is considered active in
                that group/period). Activity is never subsampled, even when
                ``sample_per_period`` is set.
            min_percentile: percentile (0-100) used to filter, per (group,
                period), the vocabulary down to its most frequent words. Only
                words whose count is greater than or equal to this percentile
                of the (group, period) count distribution are kept. ``None``
                disables the filter entirely (every word is kept).
            log_base: base of the logarithm used by specificity/volatility.
            background: ``"filtered"`` (default) or ``"all"``. Controls which
                counts the *background* probabilities of specificity/volatility
                (the word's global share across groups at a period, and the
                word's share within a group across all periods) are computed
                from. ``"filtered"`` uses only the top-``min_percentile``
                vocabulary of every (group, period) -- a word used broadly but
                below the cut in most groups can then look artificially
                exclusive to the one group where it passed the cut. ``"all"``
                uses every word's raw count before the percentile cut, so the
                background reflects true cross-group usage. The *foreground*
                share (a word's share within its own (group, period) or
                (group, all periods)) always uses the filtered vocabulary,
                regardless of ``background``.
            speaker_dedup: if ``True`` (default), a word is counted at most
                once per speaker within a given (group, period), matching the
                methodology used in the case study. If ``False``, a word is
                counted once per lexical record (duplicate words within the
                same record are still collapsed to one occurrence).
            sample_per_period: if set, keep at most this many lexical records
                per (group, period), chosen uniformly without replacement
                (reservoir sampling) via ``random.Random(seed)``. A (group,
                period) with fewer records than ``sample_per_period`` is kept
                whole. ``None`` (the default) disables subsampling.
            seed: seed for the ``random.Random`` instance used by
                ``sample_per_period``; ignored otherwise.

        The whole table is built with a single pass over ``lexical`` (and, if
        given, a single pass over ``activity``); every public metric is then a
        dictionary lookup or an aggregation over the already-filtered tables.
        When ``sample_per_period`` is set, a second, much smaller pass over the
        per-(group, period) reservoirs turns the sampled records into counts.
        """
        self.min_percentile = min_percentile
        self.log_base = log_base
        self.speaker_dedup = speaker_dedup
        self.sample_per_period = sample_per_period
        self.seed = seed
        if background not in ("filtered", "all"):
            raise ValueError(f"background must be 'filtered' or 'all', got {background!r}.")
        self.background = background
        self._source_params: Dict[str, Any] = {}

        raw_counts: DefaultDict[str, DefaultDict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
        n_lexical: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        speakers_lexical: DefaultDict[str, DefaultDict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        all_speakers_seen: DefaultDict[str, DefaultDict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        seen_words: DefaultDict[Tuple[str, str, str], Set[str]] = defaultdict(set)
        period_sampled: DefaultDict[str, DefaultDict[str, bool]] = defaultdict(lambda: defaultdict(bool))

        def consume(group: str, period: str, author: str, words: Iterable[str]) -> None:
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

        if sample_per_period is None:
            for group, period, author, words in tqdm(lexical, desc="Counting words"):
                all_speakers_seen[group][period].add(author)
                consume(group, period, author, words)
        else:
            rng = random.Random(seed)
            reservoir: DefaultDict[Tuple[str, str], List[LexicalRecord]] = defaultdict(list)
            seen_count: DefaultDict[Tuple[str, str], int] = defaultdict(int)
            for group, period, author, words in tqdm(lexical, desc="Counting words"):
                all_speakers_seen[group][period].add(author)
                key = (group, period)
                seen_count[key] += 1
                if len(reservoir[key]) < sample_per_period:
                    reservoir[key].append((group, period, author, list(words)))
                else:
                    slot = rng.randint(0, seen_count[key] - 1)
                    if slot < sample_per_period:
                        reservoir[key][slot] = (group, period, author, list(words))
            for (group, period), records in reservoir.items():
                period_sampled[group][period] = seen_count[(group, period)] > sample_per_period
                for rec_group, rec_period, author, words in records:
                    consume(rec_group, rec_period, author, words)

        self._n_lexical: Dict[str, Dict[str, int]] = {g: dict(p) for g, p in n_lexical.items()}
        self._speakers_lexical: Dict[str, Dict[str, Set[str]]] = {
            g: {p: set(s) for p, s in periods.items()} for g, periods in speakers_lexical.items()
        }
        self._period_sampled: Dict[str, Dict[str, bool]] = {g: dict(p) for g, p in period_sampled.items()}

        # Filter each (group, period) vocabulary down to its top `min_percentile`.
        self._counts: Dict[str, Dict[str, Dict[str, int]]] = {}
        for group, periods_map in raw_counts.items():
            self._counts[group] = {}
            for period, counter in periods_map.items():
                values = list(counter.values())
                if min_percentile is None or not values:
                    filtered = dict(counter)
                else:
                    threshold = float(np.percentile(values, min_percentile))
                    filtered = {word: count for word, count in counter.items() if count >= threshold}
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

        # Same aggregates, but over the UNFILTERED vocabulary (`raw_counts`, before the percentile
        # cut) -- used for the "all" background: a word's true cross-group/cross-period usage,
        # unaffected by whether it happened to pass the cut in any particular (group, period).
        word_period_totals_all: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        group_word_totals_all: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        period_totals_all: DefaultDict[str, int] = defaultdict(int)

        for group, periods_map in raw_counts.items():
            for period, counter in periods_map.items():
                total = sum(counter.values())
                period_totals_all[period] += total
                for word, count in counter.items():
                    word_period_totals_all[word][period] += count
                    group_word_totals_all[group][word] += count

        self._word_period_totals_all: Dict[str, Dict[str, int]] = {
            w: dict(p) for w, p in word_period_totals_all.items()
        }
        self._group_word_totals_all: Dict[str, Dict[str, int]] = {
            g: dict(w) for g, w in group_word_totals_all.items()
        }
        self._period_totals_all: Dict[str, int] = dict(period_totals_all)
        self._group_totals_all: Dict[str, int] = {
            group: sum(word_map.values()) for group, word_map in self._group_word_totals_all.items()
        }

        # Active users per (group, period), used only for retention. Derived from every speaker
        # seen in `lexical` (never subsampled), not from the possibly-truncated `speakers_lexical`.
        active: DefaultDict[str, DefaultDict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        if activity is None:
            for group, periods_map in all_speakers_seen.items():
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
        period_range: Optional[Tuple[str, str]] = None,
        **kw: Any,
    ) -> "IdentityMetrics":
        """Build an :class:`IdentityMetrics` from a ConvoKit ``Corpus``.

        Lexical records are the utterances whose ``meta["depth"]`` is in
        ``lexical_depths`` and that have a truthy ``meta[words_field]``; an
        utterance with an empty token list does not count as a lexical record.
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
            period_range: optional ``(start, end)`` inclusive bounds on the
                period key, compared as plain strings -- valid for every
                period type because the keys are zero-padded. Utterances whose
                period falls outside the window are excluded from both the
                lexical and the activity records.
            **kw: extra keyword arguments forwarded to the constructor
                (``min_percentile``, ``log_base``, ``speaker_dedup``,
                ``sample_per_period``, ``seed``).

        Returns:
            IdentityMetrics: the metrics built from the corpus.
        """
        lexical_depths_set = set(lexical_depths)
        activity_depths_set = set(activity_depths) if activity_depths is not None else None

        def in_range(period: str) -> bool:
            return period_range is None or period_range[0] <= period <= period_range[1]

        def lexical_records() -> Iterable[LexicalRecord]:
            for utt in corpus.iter_utterances():
                if utt.meta.get("depth") not in lexical_depths_set:
                    continue
                words = utt.meta.get(words_field)
                if not words:
                    continue
                period = Comid.period_key(utt.timestamp, period_type)
                if not in_range(period):
                    continue
                group = utt.meta.get(group_key)
                yield group, period, utt.speaker.id, words

        def activity_records() -> Iterable[ActivityRecord]:
            for utt in corpus.iter_utterances():
                if activity_depths_set is not None and utt.meta.get("depth") not in activity_depths_set:
                    continue
                period = Comid.period_key(utt.timestamp, period_type)
                if not in_range(period):
                    continue
                group = utt.meta.get(group_key)
                yield group, period, utt.speaker.id

        instance = cls(lexical_records(), activity_records(), **kw)
        instance._source_params = {
            "group_key": group_key,
            "period_type": period_type,
            "words_field": words_field,
            "lexical_depths": list(lexical_depths),
            "activity_depths": list(activity_depths) if activity_depths is not None else None,
            "period_range": list(period_range) if period_range is not None else None,
        }
        return instance

    @classmethod
    def from_topics(
        cls,
        comid: "Comid",
        *,
        period_type: str = "m",
        lexical_depths: Optional[Sequence[int]] = None,
        activity_depths: Optional[Sequence[int]] = None,
        period_range: Optional[Tuple[str, str]] = None,
        **kw: Any,
    ) -> "IdentityMetrics":
        """Build an :class:`IdentityMetrics` from ``Comid.df_topics``.

        Group is the topic, author is ``author_id`` and words are the tokenized text of the
        document, looked up in ``comid.corpus`` by document id; a document with an empty token
        list does not count as a lexical record. The period comes from
        ``Comid.period_key(created_utc, period_type)``. Rows without a topic are skipped.
        ``lexical_depths``/``activity_depths`` optionally restrict rows by the ``depth`` column;
        ``None`` (the default for both) means every row, matching ``Comid``'s own
        ``distinctiveness``/``dynamicity``/``specificity``/``volatility``, which do not filter by depth.

        Parameters:
            comid: a ``Comid`` instance with a populated ``df_topics`` and ``corpus``.
            period_type: period granularity, forwarded to ``Comid.period_key``.
            lexical_depths: ``depth`` values considered for word counts, or ``None`` for all.
            activity_depths: ``depth`` values considered for activity/retention, or ``None`` for all.
            period_range: optional ``(start, end)`` inclusive bounds on the period key, compared
                as plain strings -- valid for every period type because the keys are zero-padded.
                Rows whose period falls outside the window are excluded from both the lexical and
                the activity records.
            **kw: extra keyword arguments forwarded to the constructor
                (``min_percentile``, ``log_base``, ``speaker_dedup``, ``sample_per_period``,
                ``seed``).

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

        def in_range(period: str) -> bool:
            return period_range is None or period_range[0] <= period <= period_range[1]

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
                if not in_range(period):
                    continue
                yield row["topic"], period, row["author_id"], words

        def activity_records() -> Iterable[ActivityRecord]:
            for doc_id, row in comid.df_topics.iterrows():
                if pd.isnull(row["topic"]):
                    continue
                if activity_depths_set is not None and row["depth"] not in activity_depths_set:
                    continue
                period = Comid.period_key(row["created_utc"], period_type)
                if not in_range(period):
                    continue
                yield row["topic"], period, row["author_id"]

        instance = cls(lexical_records(), activity_records(), **kw)
        instance._source_params = {
            "group_key": "topic",
            "period_type": period_type,
            "words_field": None,
            "lexical_depths": list(lexical_depths) if lexical_depths is not None else None,
            "activity_depths": list(activity_depths) if activity_depths is not None else None,
            "period_range": list(period_range) if period_range is not None else None,
        }
        return instance

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

    def _ceiling_fraction(self, group: str, period: str) -> float:
        """Fraction of (group, period)'s filtered vocabulary exclusive to `group` at `period`.

        A word is "exclusive" here when its ``"filtered"``-background cross-group total at
        `period` (``_word_period_totals``) equals exactly its count within `group` -- i.e. no
        other group's filtered vocabulary contains it at this period, so its specificity sits at
        the group-size-determined ceiling (see ``specificity``'s docstring).
        """
        words = self._counts.get(group, {}).get(period, {})
        if not words:
            return float("nan")
        n_ceiling = sum(
            1
            for word, count in words.items()
            if self._word_period_totals.get(word, {}).get(period, 0) == count
        )
        return n_ceiling / len(words)

    def specificity(self, word: str, group: str, period: str) -> Optional[float]:
        """Specificity of `word` in `group` during `period`.

        S(w, c, t) = log_b(a / b), where:
            a = count(w, c, t) / sum_w' count(w', c, t)   -- share of w within group c at period t
            b = count(w, ·, t) / sum_w' count(w', ·, t)   -- share of w across all groups at period t

        `b` is computed over the filtered vocabulary of every group (``background="filtered"``,
        the default) or over every word's raw count before the percentile cut
        (``background="all"``); see the constructor's ``background`` parameter.

        Returns:
            float: the specificity value, or None if `word` is not part of
            the filtered vocabulary of (`group`, `period`).
        """
        words = self._counts.get(group, {}).get(period)
        if not words or word not in words:
            return None
        a = words[word] / self._group_period_sum[group][period]
        if self.background == "all":
            b = self._word_period_totals_all[word][period] / self._period_totals_all[period]
        else:
            b = self._word_period_totals[word][period] / self._period_totals[period]
        return math.log(a / b, self.log_base)

    def volatility(self, word: str, group: str, period: str) -> Optional[float]:
        """Volatility of `word` in `group` during `period`.

        V(w, c, t) = log_b(a / b), where:
            a = count(w, c, t) / sum_w' count(w', c, t)     -- share of w within group c at period t
            b = count(w, c, ·) / sum_w' count(w', c, ·)     -- share of w within group c across all periods

        `b` is computed over the filtered vocabulary of `group` (``background="filtered"``, the
        default) or over every word's raw count before the percentile cut (``background="all"``);
        see the constructor's ``background`` parameter.

        Returns:
            float: the volatility value, or None if `word` is not part of
            the filtered vocabulary of (`group`, `period`).
        """
        words = self._counts.get(group, {}).get(period)
        if not words or word not in words:
            return None
        a = words[word] / self._group_period_sum[group][period]
        if self.background == "all":
            b = self._group_word_totals_all[group][word] / self._group_totals_all[group]
        else:
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
            the last period of each group), ``sampled`` (``True`` if the
            lexical records of that (group, period) were truncated by
            ``sample_per_period``), ``ceiling_fraction`` (fraction of the
            filtered vocabulary of (group, period) exclusive to this group at
            this period under the ``"filtered"`` background -- i.e. words
            whose specificity sits at the group-size-determined ceiling
            described in ``specificity``'s docstring).
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
                        "sampled": self._period_sampled.get(group, {}).get(period, False),
                        "ceiling_fraction": self._ceiling_fraction(group, period),
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
            "sampled",
            "ceiling_fraction",
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

        `params.json` records every parameter of the run -- the adapter parameters recorded by
        ``from_corpus``/``from_topics`` (``group_key``, ``period_type``, ``words_field``,
        ``lexical_depths``, ``activity_depths``, ``period_range``; ``None`` if the instance was
        built directly from records), the constructor parameters (``sample_per_period``, ``seed``,
        ``min_percentile``, ``log_base``, ``speaker_dedup``, ``background``) and the installed
        ``comid`` version -- so that the results folder describes itself.
        """
        os.makedirs(folder, exist_ok=True)
        self.summary().to_csv(os.path.join(folder, "summary.csv"), index=False)
        self.series().to_csv(os.path.join(folder, "series.csv"), index=False)
        source = self._source_params
        params = {
            "group_key": source.get("group_key"),
            "period_type": source.get("period_type"),
            "words_field": source.get("words_field"),
            "lexical_depths": source.get("lexical_depths"),
            "activity_depths": source.get("activity_depths"),
            "period_range": source.get("period_range"),
            "sample_per_period": self.sample_per_period,
            "seed": self.seed,
            "min_percentile": self.min_percentile,
            "log_base": self.log_base,
            "speaker_dedup": self.speaker_dedup,
            "background": self.background,
            "comid_version": __version__,
        }
        with open(os.path.join(folder, "params.json"), "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2, sort_keys=True)
