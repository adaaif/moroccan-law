"""A browser's own day of reading (HM17 of the hard-moment review): the cookie that gives it, set on the answer
that first counted for it (apps/corpus/services/reading.py `give`)."""
from apps.corpus.services import reading


class ReaderCookie:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return reading.give(request, self.get_response(request))
