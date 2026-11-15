# Metrics Module Documentation

The `comid.metrics` module provides `IdentityMetrics`, which measures how a group (a subreddit, a topic, ...) is characterised by its vocabulary and by its users over time. It computes five metrics from plain records, so it does not depend on ConvoKit or on any particular dataset layout:

| Metric | Level | Question it answers |
|---|---|---|
| Specificity `S(w, c, t)` | word | How much more is word `w` used in group `c` than across all groups at period `t`? |
| Volatility `V(w, c, t)` | word | How much more is `w` used in group `c` at period `t` than in `c` across all periods? |
| Distinctiveness `D(c)` | group | Mean specificity of the group's vocabulary. |
| Dynamicity `Dy(c)` | group | Mean volatility of the group's vocabulary. |
| Retention `R(c, t -> t+1)` | group | Share of the active users of `c` at `t` that are active again at `t+1`. |

---

## Table of Contents
- [Concepts](#concepts)
- [Definitions](#definitions)
- [Initialization](#initialization)
- [Alternative Constructors](#alternative-constructors)
- [Metric Methods](#metric-methods)
- [Tabular Outputs](#tabular-outputs)
- [Saving Results](#saving-results)
- [Usage Example](#usage-example)
- [Building from a ConvoKit Corpus](#building-from-a-convokit-corpus)
- [Notes and Caveats](#notes-and-caveats)
- [Dependencies](#dependencies)

---

## Concepts

- **Group** `c`: the unit being characterised (e.g. a subreddit).
- **Period** `t`: a string key such as `"2024-01"`. Periods are ordered as plain strings, so keys must be zero-padded (the keys produced by `Comid.period_key` are).
- **Lexical record**: `(group, period, author, words)`, one per utterance. Only lexical records contribute to word counts.
- **Activity record**: `(group, period, author)`. Only activity records contribute to retention.
- **Count** `count(w, c, t)`: the number of distinct speakers of `c` who used `w` in `t` (with `speaker_dedup=True`), or the number of lexical records that contain `w` (with `speaker_dedup=False`). A word repeated inside one record counts once.
- **Filtered vocabulary**: for every `(c, t)`, only the words whose count is greater than or equal to the `min_percentile` percentile of that `(c, t)` count distribution. `min_percentile=None` keeps every word.

---

## Definitions

All counts below refer to the filtered vocabulary unless stated otherwise. The logarithm base $B$ is `log_base` (default 2).

**Specificity**

$$S(w,c,t)=\log_B\frac{a}{b},\qquad a=\frac{\mathrm{count}(w,c,t)}{\sum_{w'}\mathrm{count}(w',c,t)},\qquad b=\frac{\mathrm{count}(w,\cdot,t)}{\sum_{w'}\mathrm{count}(w',\cdot,t)}$$

`a` is the share of `w` inside `(c, t)`; `b` is its share across all groups at `t`.

**Volatility**

$$V(w,c,t)=\log_B\frac{a}{b},\qquad a=\frac{\mathrm{count}(w,c,t)}{\sum_{w'}\mathrm{count}(w',c,t)},\qquad b=\frac{\mathrm{count}(w,c,\cdot)}{\sum_{w'}\mathrm{count}(w',c,\cdot)}$$

`b` is the share of `w` inside `c` across all periods.

**Distinctiveness and dynamicity.** `D(c, t)` and `Dy(c, t)` are the means of `S` and `V` over the filtered vocabulary of `(c, t)`. `D(c)` and `Dy(c)` are the means over every `(period, word)` pair of the filtered vocabulary of `c`, so periods with larger vocabularies weigh more.

**Retention.** With `A(c, t)` the set of active authors of `c` at `t`:

$$R(c,t\to t+1)=\frac{|A(c,t)\cap A(c,t+1)|}{|A(c,t)|}$$

`t+1` is the period immediately after `t` in the global, sorted list of periods seen in any group. `R(c)` is the mean of `R(c, t -> t+1)` over every period with a non-empty `A(c, t)` and a next period.

**Background option.** The background term `b` of specificity and volatility is computed by default from the filtered vocabulary (`background="filtered"`). With `background="all"` it is computed from every word's count before the percentile cut. The foreground term `a` always uses the filtered vocabulary. See [Notes and Caveats](#notes-and-caveats).

---

## Initialization

### `IdentityMetrics(lexical, activity=None, *, min_percentile=95, log_base=2, speaker_dedup=True, sample_per_period=None, seed=None, background="filtered")`

The count tables are built once, in the constructor; every metric is afterwards a lookup or an aggregation over them.

**Parameters:**
- `lexical` (`Iterable[(group, period, author, words)]`): one entry per utterance; `words` is any iterable of tokens.
- `activity` (`Iterable[(group, period, author)]`, optional): records used for retention. If `None`, it is derived from `lexical` (every author of a lexical record is active in that group and period). Activity is never subsampled.
- `min_percentile` (`float | None`, default `95`): percentile (0-100) of the per-`(group, period)` count distribution used as the vocabulary cut. `None` disables the cut.
- `log_base` (`float`, default `2`): logarithm base of specificity and volatility.
- `speaker_dedup` (`bool`, default `True`): count a word at most once per speaker within a `(group, period)`.
- `sample_per_period` (`int | None`, default `None`): keep at most this many lexical records per `(group, period)`, chosen uniformly without replacement. Smaller `(group, period)` cells are kept whole.
- `seed` (`int | None`): seed of the `random.Random` instance used for sampling.
- `background` (`"filtered" | "all"`, default `"filtered"`): see [Definitions](#definitions).

**Raises:** `ValueError` if `background` is not `"filtered"` or `"all"`.

---

## Alternative Constructors

### `IdentityMetrics.from_corpus(corpus, *, group_key="subreddit", period_type="m", words_field="parsed", lexical_depths=(0,), activity_depths=None, period_range=None, **kw)`

Builds the metrics from a ConvoKit `Corpus`.

- Lexical records are the utterances whose `meta["depth"]` is in `lexical_depths` and whose `meta[words_field]` is a non-empty token list.
- Activity records are all utterances (`activity_depths=None`) or those whose `meta["depth"]` is in `activity_depths`.
- The group is `meta[group_key]`, the author is `utt.speaker.id` and the period is `Comid.period_key(utt.timestamp, period_type)`.
- `period_range=(start, end)` keeps only periods between the two keys, inclusive, in both the lexical and the activity records.
- `**kw` is forwarded to the constructor.

### `IdentityMetrics.from_topics(comid, *, period_type="m", lexical_depths=None, activity_depths=None, period_range=None, **kw)`

Builds the metrics from `Comid.df_topics`, with the topic as group, `author_id` as author and the tokenised document (looked up in `comid.corpus`) as words. Rows without a topic are skipped. `None` depths mean every row. Raises `ValueError` if `comid.df_topics` or `comid.corpus` has not been built.

---

## Metric Methods

| Method | Returns |
|---|---|
| `specificity(word, group, period)` | `S(w, c, t)`, or `None` if `word` is not in the filtered vocabulary of `(group, period)`. |
| `volatility(word, group, period)` | `V(w, c, t)`, or `None` under the same condition. |
| `distinctiveness(group, period=None)` | `D(c, t)` if `period` is given, else `D(c)`. `NaN` if there is no data. |
| `dynamicity(group, period=None)` | `Dy(c, t)` if `period` is given, else `Dy(c)`. `NaN` if there is no data. |
| `retention(group, period=None)` | `R(c, t -> t+1)` if `period` is given, else `R(c)`. Raises `ValueError` if it is not computable (no next period, no active users, or no valid pair at all). |

---

## Tabular Outputs

### `word_table(group, period)`
The filtered vocabulary of `(group, period)`, sorted by count (descending). Columns: `word`, `count`, `specificity`, `volatility`.

### `series()`
One row per `(group, period)`. Columns:

| Column | Meaning |
|---|---|
| `group`, `period` | Keys. |
| `n_lexical` | Lexical records kept (after sampling). |
| `n_speakers_lexical` | Distinct authors among those records. |
| `n_active` | Active authors (activity records). |
| `vocab_size` | Size of the filtered vocabulary. |
| `distinctiveness`, `dynamicity` | `D(c, t)` and `Dy(c, t)`. |
| `retention_next` | `R(c, t -> t+1)`; `NaN` when not computable. |
| `sampled` | `True` if `sample_per_period` truncated this cell. |
| `ceiling_fraction` | Fraction of the filtered vocabulary that no other group has at this period, i.e. words at the specificity ceiling (see [Notes and Caveats](#notes-and-caveats)). Always computed against the filtered vocabularies, so with `background="all"` it no longer marks a specificity ceiling and only measures vocabulary exclusivity. |

### `summary()`
One row per group. Columns: `group`, `n_lexical`, `n_speakers_lexical`, `n_active` (distinct authors across all periods), `n_periods`, `mean_vocab_size`, `distinctiveness` (`D(c)`), `dynamicity` (`Dy(c)`), `retention_mean`, `retention_sd` (population standard deviation, `ddof=0`).

---

## Saving Results

### `save(folder)`
Creates `folder` if needed and writes:

- `summary.csv` and `series.csv`: the two tables above.
- `params.json`: every parameter of the run (`group_key`, `period_type`, `words_field`, `lexical_depths`, `activity_depths`, `period_range`, `sample_per_period`, `seed`, `min_percentile`, `log_base`, `speaker_dedup`, `background`) and `comid_version`. The adapter parameters are `null` when the instance was built directly from records.

---

## Usage Example

Two groups, two months, `min_percentile=None` so that the whole vocabulary is kept and the numbers can be checked by hand.

```python
from comid.metrics import IdentityMetrics

lexical = [
    ("keto",  "2024-01", "u1", ["keto", "fat", "fat"]),
    ("keto",  "2024-01", "u2", ["keto", "butter"]),
    ("keto",  "2024-02", "u1", ["keto", "fat"]),
    ("vegan", "2024-01", "u3", ["vegan", "tofu"]),
    ("vegan", "2024-01", "u4", ["tofu", "fat"]),
    ("vegan", "2024-02", "u3", ["vegan", "tofu"]),
]
activity = [
    ("keto",  "2024-01", "u1"), ("keto",  "2024-01", "u2"), ("keto",  "2024-02", "u1"),
    ("vegan", "2024-01", "u3"), ("vegan", "2024-01", "u4"), ("vegan", "2024-02", "u3"),
    ("vegan", "2024-02", "u5"),
]

m = IdentityMetrics(lexical, activity, min_percentile=None, log_base=2)

m.specificity("keto", "keto", "2024-01")      # 1.0
m.volatility("fat", "keto", "2024-01")        # -0.4150...
m.distinctiveness("keto", "2024-01")          # 0.6667
m.dynamicity("keto", "2024-01")               # 0.0566
m.retention("vegan", "2024-01")               # 0.5  (u3 stays, u4 leaves)
m.retention("keto")                           # 0.5  (mean over the only valid pair)

m.word_table("keto", "2024-01")
#      word  count  specificity  volatility
# 0    keto      2          1.0    0.000000
# 1     fat      1          0.0   -0.415037
# 2  butter      1          1.0    0.584963

m.summary()
#    group  n_lexical  n_speakers_lexical  n_active  n_periods  mean_vocab_size  distinctiveness  dynamicity  retention_mean  retention_sd
# 0   keto          3                   2         2          2              2.5              0.8    0.150978             0.5           0.0
# 1  vegan          3                   2         3          2              2.5              0.8    0.150978             0.5           0.0

m.save("results/")                            # summary.csv, series.csv, params.json
```

Worked check for `S("keto", "keto", "2024-01")`: in January, `keto` was used by 2 of the 4 counted words of its group (`a = 2/4`) and by 2 of the 8 counted words across both groups (`b = 2/8`), so `S = log2((2/4)/(2/8)) = 1`.

---

## Building from a ConvoKit Corpus

With a `Corpus` whose utterances carry `meta["subreddit"]`, `meta["depth"]` and a tokenised `meta["parsed"]` (for instance after `ConvoTextParser` in `comid.convobridge`):

```python
from comid.metrics import IdentityMetrics

metrics = IdentityMetrics.from_corpus(
    corpus,
    group_key="subreddit",
    period_type="m",
    words_field="parsed",
    lexical_depths=(0,),            # only top-level posts feed the vocabulary
    period_range=("2023-01", "2024-12"),
    min_percentile=95,
    log_base=2,
)

metrics.summary()
metrics.series()
metrics.save("results/")
```

Sensitivity to subsampling can be checked by fixing the number of records per cell:

```python
sampled = IdentityMetrics.from_corpus(corpus, sample_per_period=500, seed=0)
```

---

## Notes and Caveats

- **Specificity ceiling.** A word that no other group has in its filtered vocabulary at `t` has `b = count / period_total`, so `S = log_B(period_total / group_period_total)`, which depends only on the relative size of the group. Groups that are small relative to the period get a high ceiling. `ceiling_fraction` in `series()` reports how much of each cell's vocabulary sits at that ceiling. It is defined against the filtered vocabularies, so a large group scores high simply because its vocabulary rarely coincides with the much smaller vocabularies of small groups; with `background="all"` it is no longer a specificity ceiling.
- **Background choice.** With `background="filtered"`, a word used broadly but below the cut in most groups can look exclusive to the one group where it passed the cut. `background="all"` uses the raw counts for `b` and avoids this; use it as a sensitivity check.
- **Retention and gaps.** `t+1` is defined over the global period list. If a group has no activity at `t+1` but other groups do, `R(c, t -> t+1)` is `0`; it is `NaN` (in `series()`) only for the last global period or when `A(c, t)` is empty.
- **Retention and lexical records.** When `activity` is passed explicitly, authors that never post a lexical record (for example comment-only authors when `lexical_depths=(0,)`) still count as active. Passing `activity=None` derives activity from the lexical records and can give a different value.
- **Sampling.** `sample_per_period` truncates lexical records only, and only for cells with more records than the limit (`sampled=True` in `series()`). Cells with fewer records stay smaller, so sampling does not always equalise group sizes.
- **Order independence.** Results do not depend on the order of the records, except for which records the reservoir keeps when `sample_per_period` is set (fixed by `seed`).
- **Deprecated `Comid` methods.** `Comid.distinctiveness`, `dynamicity`, `specificity` and `volatility` delegate to this module, using `log_base=10`.

---

## Dependencies

- `numpy`, `pandas`, `tqdm`.
- `comid` itself: `comid.metrics` imports `Comid` (for `period_key`) and `__version__`, so the package dependencies (`spacy`, `convokit`, ...) must be installed.
