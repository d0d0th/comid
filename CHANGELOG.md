# Changelog

## [0.1.0] - 2026-11-15

### Added
- `IdentityMetrics(..., background="filtered" | "all")`: the background term of specificity and volatility can use the filtered vocabulary (default) or every word's raw count before the percentile cut. Invalid values raise `ValueError`.
- `IdentityMetrics.series()` column `ceiling_fraction`: fraction of a `(group, period)` vocabulary that no other group has at that period. It is always computed against the filtered vocabularies, so it is not a specificity ceiling when `background="all"`.
- `background` is recorded in `params.json` by `IdentityMetrics.save`.
- `docs/Metrics.md`: specification of `comid.metrics` with a usage example.
- `docs/Conventions.md`: thread depth and `Comid.clean_data` cascade conventions.
- `Comid.df_topics` column `is_oc`, marking the original post of each thread.
- `comid.__version__`.
- `requests` in `install_requires` (it is imported directly by `comid.pullpush`).
- Tests: `tests/test_spec_fixture.py` (hand-derived values for the metrics specification), `tests/test_build_topics.py`, and more cases in `tests/test_clean_data.py`.

### Changed
- **Depth convention (breaking).** In `Comid.df_topics` the original post now has `depth = -1` and `is_oc = True`; comments keep Reddit's raw depth (`0` for top-level). `group_by_period` counts threads and replies with `is_oc` instead of `depth == 0`. See `docs/Conventions.md`.
- **`Comid.clean_data` (breaking).** It now returns a dict with the counts flagged and removed for each criterion (`no_content`, `no_author`, `keyword`), the total removed, the posts retained, and the same breakdown per subreddit.
- The version is defined only in `comid/__init__.py`; `setup.py` reads it from there without importing the package.
- The README links `docs/Metrics.md` and lists the conventions document in its own section.

### Fixed
- `Comid.text2dict` no longer aborts on a post that makes `contractions.fix` raise `IndexError`; the text is lower-cased without expanding contractions.

## [0.0.5] - 2026-10-24

### Added
- `comid.metrics.IdentityMetrics`: specificity, volatility, distinctiveness, dynamicity and user retention computed from plain `(group, period, author, words)` records. Builders `from_corpus` (ConvoKit `Corpus`) and `from_topics` (`Comid.df_topics`); outputs `word_table`, `series` and `summary`; `save` writes `summary.csv`, `series.csv` and `params.json`.
- `IdentityMetrics` options `min_percentile` (`None` disables the cut), `log_base`, `speaker_dedup`, `sample_per_period` with `seed`, and `period_range` in the builders. Activity used for retention is never subsampled.
- `series()` column `sampled`, true when `sample_per_period` truncated that `(group, period)`.
- Test suite under `tests/` (pytest): metrics, `from_corpus`, `clean_data`, ConvoBridge, collector files and `period_key`.

### Changed
- **`Comid.distinctiveness`, `dynamicity`, `specificity`, `volatility` and their `*_by_index` helpers are deprecated** and delegate to `IdentityMetrics` (`log_base=10`) with a `DeprecationWarning`. The results differ from the previous array-based implementation: words are counted once per author within each `(topic, period)`, the vocabulary is cut at the 95th percentile, and only the original posts' corpus is used.
- `Comid.period_key` builds period keys from UTC timestamps instead of local time.
- The cached `IdentityMetrics` of a `Comid` is invalidated by `generate_corpus` and `build_topics`.

### Fixed
- `RedditCollector` writes the ids CSV without blank lines on Windows (`newline=""`).
- `Comid.core_peripheral_orientation` checked `b2` twice for zero and never `a2`.
- Docstrings of `reduce_corpus` (which of `min_op_length` and `min_num_interactions` applies to each mode) and of `ConvoTextParser` (default `output_field` is `"parsed"`).

## [0.0.4] - 2025-04-27

Tagged as `v0.0.4-thesis-draft`.

### Added
- `comid.convobridge` (ConvoKit integration): `ConvoCorpus` and `ConvoTextParser`, with `docs/ConvoBridge.md`.
- `Comid.text2dict`, `Comid.text_tokenizer` and `Comid.spacy_load`: spaCy-based tokenisation by POS tag with scored bigram phrases; `Comid.g_squared` and `Comid.npmi` bigram association scores.
- `Comid.generate_corpus(model="en_core_web_sm")`.
- `Comid.period_key` is public (formerly `_retrieve_period`) and accepts `"f"` (fortnight) and `"q"` (quarter) besides `"d"`, `"w"`, `"m"` and `"y"`.
- `convokit>=3.1.0` in `install_requires`.
- `comid.collector`: waits one hour and retries when Reddit answers `429 Too Many Requests`.
- `comid.pullpush`: retries every 60 seconds when PullPush answers with an HTTP error.
- Documentation of the ConvoKit integration in `docs/Comid.md` and `docs/ConvoBridge.md`.

### Changed
- **Python 3.10 or later is required** (3.9 dropped); 3.11 and 3.12 are listed as supported.
- `Comid.generate_corpus` with `use_lemmas=True` tokenises with spaCy instead of the NLTK stopword list; title, text and comments are joined with a newline instead of a space.
- `Comid.period_key` raises an exception for an invalid `period_type` instead of returning `None`.
- The default `output_field` of `ConvoTextParser` is `"parsed"` (was `"words"`).

### Fixed
- `Comid.load_json_files(folder=...)` builds the full path of each file and ignores subdirectories.
- `Explorer` skips post ids that are not in the dataset and creates `thread_replies` entries for threads without replies.
- Documentation of `reduce_corpus`.
