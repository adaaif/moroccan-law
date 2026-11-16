"""The discussion as a reader sees it (29 Oct 2026): a topic's feed of posts, a post with its comments, the posts
that cite an article, the places with their latest posts; each contribution as a card.

A feed sorts by «النشيط» (the latest sign of life: the post or its latest comment), «الجديد» (newest), «الأنفع»
(most useful over a week, a month, a year or since the start) or «بلا جواب» (questions nobody else answered). Comments
sit under their post: by «الأنفع» the one its asker marked «أفادني» first, then the most useful; by «الأحدث» or «الأقدم»
by date.

Removed or deleted contributions with answers under them stay as a marker; without, they are gone. A held one is
shown to its author alone, saying it waits, and to the topic's moderators.

By subject: `cards` (a contribution as a card, who sees it, what it cites, an address said in words), `lists` (the
feeds, the hub, a topic's block, the questions waiting and answered, an article's posts and the margin's counts, a
person's page), `comments` (a post's page: its comments as a tree grown on request) and `asked` (the questions asked
before). Callers name it as one module (`thread.post(…)`): this package re-exports its public names, and `_labels`,
which the views read through it."""
from apps.discussion.services.thread.asked import asked_before, similar
from apps.discussion.services.thread.cards import (Context, _labels, author, card, cites_of, label_of, pictures,
                                                   post_card, readable_titles, replied, visible, where)
from apps.discussion.services.thread.comments import (COMMENT_SORTS, CONVERSATIONS, DOOR, REPLY_PREVIEW, may_open,
                                                      post, post_answers, post_around)
from apps.discussion.services.thread.lists import (ALL, FOLLOWING, LIFE, PAGE, PERIODS, SORTS, answered_questions,
                                                   article_payload, cited, counts, feed, moderators, open_questions,
                                                   overview, person, place_payload, topic_talk)

__all__ = ['asked_before', 'similar',
           'Context', '_labels', 'author', 'card', 'cites_of', 'label_of', 'pictures', 'post_card', 'readable_titles',
           'replied', 'visible', 'where',
           'COMMENT_SORTS', 'CONVERSATIONS', 'DOOR', 'REPLY_PREVIEW', 'may_open', 'post', 'post_answers', 'post_around',
           'ALL', 'FOLLOWING', 'LIFE', 'PAGE', 'PERIODS', 'SORTS', 'answered_questions', 'article_payload', 'cited',
           'counts', 'feed', 'moderators', 'open_questions', 'overview', 'person', 'place_payload', 'topic_talk']
