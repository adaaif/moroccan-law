"""The discussion's API. Views read the request, call a service and answer; refusals come back in the one error
shape (`RefusingView`).

By subject: `reading` (the feeds, a post, an article's posts, the hub, the margin's counts, the questions, a person's
page, the month's numbers), `writing` (writing, editing, votes, reports, follows, the form's checks, voices and
pictures), `mine` (a person's own: their page, notices, appeals, the header's dot, a letter's stop link) and
`reviewing` (the moderators' desk, their acts, the ledger, appointing them)."""
from apps.discussion.api.views.mine import (AppealsView, LettersStopView, MineView, NoticesSeenView,
                                            UnseenView)
from apps.discussion.api.views.reading import (AnsweredView, CitedView, CountsView, FeedView, NumbersView, PersonView,
                                               PlacesView, PostAnswersView, PostView, QuestionsView)
from apps.discussion.api.views.reviewing import (LedgerView, ReviewActView, ReviewAppealView, ReviewerView,
                                                 ReviewersView, ReviewLockView, ReviewPauseView, ReviewPictureView,
                                                 ReviewQueueView)
from apps.discussion.api.views.writing import (AcceptView, CheckView, ContributionsView, ContributionView, FollowView,
                                               PicturesView, PictureView, ReportView, SimilarView, TakedownView,
                                               UsefulView, VoicesView, VoiceView)

__all__ = ['AppealsView', 'LettersStopView', 'MineView', 'NoticesSeenView', 'UnseenView',
           'AnsweredView', 'CitedView', 'CountsView', 'FeedView', 'NumbersView', 'PersonView', 'PlacesView',
           'PostAnswersView', 'PostView', 'QuestionsView',
           'LedgerView', 'ReviewActView', 'ReviewAppealView', 'ReviewerView', 'ReviewersView', 'ReviewLockView',
           'ReviewPauseView', 'ReviewPictureView', 'ReviewQueueView',
           'AcceptView', 'CheckView', 'ContributionsView', 'ContributionView', 'FollowView', 'PicturesView',
           'PictureView', 'ReportView', 'SimilarView', 'TakedownView', 'UsefulView', 'VoicesView', 'VoiceView']
