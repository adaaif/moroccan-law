"""What the corpus's public views share: a view with no session at the public rate, and a text's and an issue's
reference as every answer names them."""
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.corpus.models import Text
from apps.corpus.services.addresses import text_path
from apps.corpus.services.codes import display_name
from apps.opendata.throttles import PublicRate
from apps.sources.models import Issue


class PublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicRate]


def text_ref(text: Text) -> dict:
    return {'id': text.pk, 'akn_uri': text.akn_uri, 'path': text_path(text.akn_uri), 'type': text.type,
            'type_label': text.get_type_display(),
            'number': text.number, 'number_as_printed': text.number_as_printed, 'title': text.title_ar,
            'name': display_name(text), 'in_corpus': text.in_corpus}


def issue_ref(issue: Issue, last_number: int | None = None) -> dict:
    """`last_number`: the last of the numbers the issue's cover bears, for a cover that bears several (FX3)."""
    return {'edition': issue.edition, 'edition_label': issue.get_edition_display(), 'number': issue.number,
            'suffix': issue.suffix, 'key': issue.key,
            'date': issue.date, 'hijri_date': issue.hijri_date, 'document_id': issue.document_id,
            'page_count': issue.document.page_count if issue.document_id else None,
            'first_page_number': issue.first_page_number, 'last_number': last_number}
