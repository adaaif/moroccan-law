"""The people's words beside the law (R8 of the for-everyone review).

- One shared explanation an address and a register: anyone who may write in the discussion can improve it (the same
  gates: the discussion open, a proven email, no pause, a newcomer's five a day, the agreement to the check); every
  state is kept as a revision.
- Every state passes the discussion's own guards before anyone reads it: its fixed patterns (holds.py) on the
  headline, the words and the note, then, when they hold nothing, its check (check.py). What they find goes with the
  state to the reviewers, as the discussion's hold codes.
- Readers see an explanation once a reviewer of its text (or staff) has checked it. An edit by anyone else waits
  (`Explanation.pending`) and readers keep the last checked words meanwhile; the waiting edit and every state nobody
  checked are for their author and the reviewers. A reviewer who writes checks at once, unless a guard held it: then
  another reviewer decides, since nobody decides about their own words.
- A reader with an account reports a state readers see; a reviewer of the text keeps it or removes it under one of
  the seven rules, its author told which. (Until 29 Oct 2026 an article thread's most useful «شرح» stood in; the
  discussion now lives in the topics, and nothing stands in.)
- An article's explanation is tied to the words it explained: when the article changes, it says so.
- It rests on the article it explains, and on the other addresses it names (`sources`), each one the site holds.

By subject: `reading` (what an explanation may be of, what readers see and their «مفيد»), `writing` (a state
written, through the guards) and `reviewing` (checking, removing, keeping, reports, what waits). Callers name it as
one module (`explanations.save(…)`): this package re-exports its public names."""
from apps.explain.services.explanations.reading import (NEW_DAYS, bundle, bundle_word, checked, detail, helpful,
                                                        kind_of, new_items, short, text_of, word_meanings)
from apps.explain.services.explanations.reviewing import check, keep, remove, report, waiting, waiting_count
from apps.explain.services.explanations.writing import save

__all__ = ['NEW_DAYS', 'bundle', 'bundle_word', 'checked', 'detail', 'helpful', 'kind_of', 'new_items', 'short',
           'text_of', 'word_meanings',
           'check', 'keep', 'remove', 'report', 'waiting', 'waiting_count',
           'save']
