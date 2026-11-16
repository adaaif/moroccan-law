"""The discussion layer (the decisions of 19 Oct 2026, and those of 29 Oct 2026: discussions live in the topics as
posts and comments, published once a model has checked them, moderated by people from each topic, with karma).

Everything is keyed by address: a topic's place (/talk/family), and for what a post cites the article's path on the
site (/ma/loi/2013/67-12/art_34), never a foreign key to Text or Article, which a reload deletes and recreates. A post
keeps a digest of each article it cites as it read then, so it can say that the article changed after it (D14).

The models by subject: `posts` (a place, its posts and comments, what they cite, their earlier wordings, the limits,
kinds and rules they are written under), `people` (votes, points, follows, notices) and `moderation` (reviewers,
reports, the ledger, pauses, appeals, trust, the model's check)."""
# Imported in the order they were defined: Django registers the models as they are imported.
from apps.discussion.models.posts import (APPEAL_MAX, BODY_MAX, NOTE_MAX, PATH_MAX, PICTURES_MAX, POST_KINDS, QUOTE_MAX,
                                          TITLE_MAX, Cite, Contribution, Discussion, Kind, Revision, Rule)
from apps.discussion.models.people import Follow, Notice, Point, Useful
from apps.discussion.models.moderation import Action, Appeal, Ban, Check, Report, Reviewer, Trust

__all__ = ['APPEAL_MAX', 'BODY_MAX', 'NOTE_MAX', 'PATH_MAX', 'PICTURES_MAX', 'POST_KINDS', 'QUOTE_MAX', 'TITLE_MAX',
           'Cite', 'Contribution', 'Discussion', 'Kind', 'Revision', 'Rule',
           'Follow', 'Notice', 'Point', 'Useful',
           'Action', 'Appeal', 'Ban', 'Check', 'Report', 'Reviewer', 'Trust']
