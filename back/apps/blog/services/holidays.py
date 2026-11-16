"""The lists of public holidays decree by decree, for «أعيادنا بمرسوم، كيف كبرت لائحة العطل» (the blog's seventh post,
B5 of the blog-first-post review, 31 Oct 2026). The lists are the post's meta, read in each text's first article; what is
counted here ties each text to its issue, its page and its address, so every change in the post opens its text. One
query."""
from apps.corpus.models import Text
from apps.corpus.services.addresses import text_path
from apps.sources.models import Edition


def count(meta: dict) -> dict:
    numbers = {x['text'] for x in meta['private'] + meta['administration']} | {meta['once']['text']}
    rows = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, number__in=numbers)
            .values('number', 'title_ar', 'akn_uri', 'first_published_page', 'first_published_in__number',
                    'first_published_in__suffix', 'first_published_in__date'))
    return {'texts': {r['number']: {
        'title': r['title_ar'], 'path': text_path(r['akn_uri']), 'page': r['first_published_page'],
        'issue': f"{r['first_published_in__number']}{'-bis' if r['first_published_in__suffix'] else ''}",
        'published': r['first_published_in__date'].isoformat(),
    } for r in rows}}
