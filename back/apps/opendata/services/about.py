"""What «عن «قانون»» counts (P18 of the polish review): the texts and articles (each text's newest version), the BO issues
and pages read, the corrections applied, the explanations a reader may see (checked, and not by the development's
people: the page said 13 while the public site showed none, 31 Oct 2026), the address to write to and the public
repository of the site's code. Counted once for every worker, until the corpus or the explanations move."""
from django.conf import settings
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.corpus.models import Article, Text, Version
from apps.corpus.services import generation
from apps.explain.services.explanations import checked
from apps.quality.models import Correction
from apps.sources.models import Issue, Page


def figures() -> dict:
    # Kept for every worker until the corpus or the explanations move (RD15 of the readers review, 9 Nov 2026): each
    # worker kept its own copy for an hour, workers are replaced often, and the three counts are heavy queries;
    # /library, /about, /data and /privacy ask on every visit.
    def build():
        newest = Version.objects.filter(text=OuterRef('text')).order_by('-valid_from').values('pk')[:1]
        return {
            'texts': Text.objects.filter(versions__isnull=False).distinct().count(),
            'articles': Article.objects.filter(version__in=Version.objects.filter(pk=Subquery(newest))).count(),
            'issues': Issue.objects.count(),
            'pages': Page.objects.exclude(text='').count(),
            'corrections': Correction.objects.filter(status=Correction.Status.APPLIED).count(),
            'explanations': checked().count(),
            'on': timezone.localdate().isoformat(),
        }

    found = generation.kept(['about', 'figures', timezone.localdate().isoformat()], build, scopes=('corpus', 'explain'))
    return {**found, 'contact': settings.CONTACT_EMAIL, 'source': settings.SOURCE_URL}
