"""A BO reading set beside a second copy of the same text (A7 of the consumer plan; services/witness.py): Adala's or
the SGG's, article by article. Prints the share of articles the two copies agree on and the articles they do not,
with the words each side alone holds, and keeps the whole report in CORPUS_DIR/reports/witness/.

    witness /akn/ma/act/loi/31-08                     # the BO of 2011 against Adala's copy
    witness /akn/ma/act/loi/31-08 --witness sgg --min 0.95   # fails below 95 % (the consumer plan's K10)
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.corpus.models import Text
from apps.quality.services.witness import compare


class Command(BaseCommand):
    help = "Set a text's BO reading beside Adala's or the SGG's copy, article by article."

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='+', help='texts, e.g. /akn/ma/act/loi/31-08')
        parser.add_argument('--witness', default='adala', choices=['adala', 'sgg'])
        parser.add_argument('--base', default='as_published', choices=['as_published', 'sgg', 'adala'],
                            help='the copy read against the witness: the BO by default')
        parser.add_argument('--min', type=float, default=0.0, help='fail when a text agrees on fewer articles')
        parser.add_argument('--show', type=int, default=8, help='how many differing articles to print')
        parser.add_argument('--file', help="Adala's PDF under CORPUS_DIR, when the BO's version took its place")

    def handle(self, *args, uris, witness, base, min, show, file=None, **opts):
        out = Path(settings.CORPUS_DIR) / 'reports' / 'witness'
        out.mkdir(parents=True, exist_ok=True)
        low = []
        for uri in uris:
            text = Text.objects.filter(akn_uri=uri).first()
            if text is None:
                raise CommandError(f'{uri}: not in the corpus')
            r = compare(text, witness, base, str(Path(settings.CORPUS_DIR) / file) if file else None)
            (out / f'{uri.strip("/").replace("/", "_")}.{base}-{witness}.json').write_text(
                json.dumps(r, ensure_ascii=False, indent=1))
            if r.get('error'):
                self.stdout.write(f'{uri}: {r["error"]}')
                continue
            self.stdout.write(f'{uri}: {r["agree"]}/{r["compared"]} articles agree ({100 * (r["share"] or 0):.1f} %), '
                              f'{r["changed"]} changed since, {r["only_bo"]} only in the BO, '
                              f'{r["only_witness"]} only in {witness}')
            for row in [x for x in r['rows'] if x['status'] == 'differ'][:show]:
                self.stdout.write(f'   {row["label"]}: F1 {row["f1"]}, CER {row["cer"]} · {base} alone «{" | ".join(row["bo_only"][:3])}»'
                                  f' · {witness} alone «{" | ".join(row["witness_only"][:3])}»')
            if r['share'] is not None and r['share'] < min:
                low.append(uri)
        if low:
            raise CommandError(f'below {min:.0%}: {", ".join(low)}')
