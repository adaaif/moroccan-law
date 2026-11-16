"""Gzip for the public answers (row 17 of the reader-experience review: a law's articles were 1.1 MB uncompressed; S16 of the
performance audit). BREACH needs a secret in the compressed answer beside words the attacker chooses:

- the public views (corpus, search, budget, open data) read no account, so their answer is the same for everyone and
  holds nothing of the reader's: compressed whoever asks, a signed-in reader too (320 KB of a long law's window
  instead of 59 KB until 24 Oct 2026);
- the topics, the explanations, the discussion's reads and follows' news may answer a signed-in reader with their
  own (what they voted or wrote): compressed only when no one is signed in.

Never the files and page pictures (/api/sources/: already compressed) nor anything else."""
from django.middleware.gzip import GZipMiddleware

ANYONE = ('/api/corpus/', '/api/search/', '/api/budget/', '/api/open/')
ANONYMOUS = ('/api/topics/', '/api/explain/', '/api/discussion/', '/api/follows/news/')


class PublicGZipMiddleware(GZipMiddleware):
    def process_response(self, request, response):
        if request.path.startswith(ANYONE) or (request.path.startswith(ANONYMOUS)
                                               and 'HTTP_AUTHORIZATION' not in request.META):
            return super().process_response(request, response)
        return response
