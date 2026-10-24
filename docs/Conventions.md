# Conventions

This document fixes, in one place, two conventions that are applied consistently across `comid`:
how thread **depth**/"is this the original post?" is represented in each pipeline, and how
`Comid.clean_data` cascades removals through a thread. Every module that touches depth or deletes
posts follows the rules below; if you add new code that does either, follow them too.

## Depth

Depth is **Reddit's raw comment depth, exactly as collected**: a top-level comment (a direct reply
to the submission) is depth `0`; a reply to that comment is depth `1`; and so on. The raw post dict
for the original post (OC/submission) has **no `depth` key at all** -- it never had one, from
collection onward.

Downstream pipelines must represent "this is the OC" explicitly, and **never by overloading
`depth == 0`** (which already means "top-level comment"). Each pipeline picks the representation
that fits its data structure best; both are equally valid, as long as the rule above is respected:

| Pipeline | OC representation | Comment representation |
|---|---|---|
| `comid.convobridge.ConvoCorpus` (ConvoKit utterances) | `utt.meta['depth'] is None` | raw depth (`0`, `1`, ...) |
| `Comid.build_topics` / `df_topics` (pandas) | `depth == -1` and `is_oc == True` | raw depth (`0`, `1`, ...) and `is_oc == False` |

Consequences of getting this right:
- `Comid.group_by_period`'s `new_threads` count is `is_oc`-based (number of OCs started in the
  period), and `replies` is `~is_oc`-based (every comment, any depth >= 0). Filtering on
  `depth == 0` for `new_threads` would silently count top-level comments as new threads, and
  `depth > 0` for `replies` would silently drop top-level comments from the reply count.
- `comid.metrics.IdentityMetrics.from_corpus`/`from_topics`'s `lexical_depths`/`activity_depths`
  filters (e.g. `lexical_depths=(0,)` to mean "top-level comments only") behave correctly precisely
  *because* the OC is never `depth == 0` in either pipeline.

## Cleaning cascade (`Comid.clean_data`)

`clean_data` removes a post by calling `_retrieve_thread_ids(post_id)`, which walks **only
downward**: it returns `post_id` itself plus every descendant reply beneath it (recursively, via
each post's `replies` list). It never looks at ancestors or siblings.

- If a **non-OC reply** fails a criterion (no author, no content, a matched keyword), only that
  reply and its own sub-thread are removed; the OC and sibling replies survive.
- If the **OC itself** fails a criterion, the whole thread (OC + every reply beneath it) is
  removed.
- Every post dict needs a `replies` key -- even an empty list `[]` -- for this to work correctly:
  `_retrieve_thread_ids` (and `Explorer._proc_thread`) only recurse into / register a post when
  `'replies' in post`. A leaf post without that key is otherwise silently skipped when walking the
  thread.
