"""The minimum wage decree by decree, for «الحد الأدنى للأجر، مرسوما بعد مرسوم» (the blog's sixth post, B10 of
the blog-first-post review, 31 Oct 2026). The amounts are the post's meta, read in each decree's articles; what is counted here ties
each decree to its issue, its page and its first article, so every step of the post opens its text. One query."""
from django.db.models import Q

from apps.corpus.models import Text
from apps.corpus.services.addresses import text_path
from apps.sources.models import Edition


def count(meta: dict) -> dict:
    numbers = {s['decree'] for s in meta['steps'] if s['decree']}
    issues = {s['issue'] for s in meta['steps'] if not s['decree']}
    rows = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR)
            .filter(Q(number__in=numbers) | Q(first_published_in__number__in=issues, title_ar__contains='الاجرة الدنيا'))
            .values('number', 'title_ar', 'akn_uri', 'first_published_page', 'first_published_in__number',
                    'first_published_in__suffix', 'first_published_in__date'))
    decrees = {}
    for r in rows:
        key = r['number'] or str(r['first_published_in__number'])
        decrees[key] = {
            'title': r['title_ar'], 'path': text_path(r['akn_uri']), 'page': r['first_published_page'],
            'issue': f"{r['first_published_in__number']}{'-bis' if r['first_published_in__suffix'] else ''}",
            'published': r['first_published_in__date'].isoformat(),
        }
    return {'decrees': decrees}
