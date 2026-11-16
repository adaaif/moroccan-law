"""Morocco's constitutions since independence, for reference (25 Oct 2026): each of Adala's six files
(data/constitutions.json, fetched with fetch_adala) loaded with load_adala at its address, then given what the files
do not say: its type, the dahir's date, in force (2011) or replaced, and its title without the footnote's mark. Their
everyday names («دستور المملكة المغربية لسنة 1996») are in apps/search/data/popular_names.json. Run again, each file
replaces its own version; then their revisions (`_revise`), their official French from the French BO (C9,
load_bo_french, `--no-french` to keep it), and the texts' search entries: `index.rebuild(texts)` (done here).

    load_constitutions"""
import json
import re
from datetime import date
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.corpus.models import Status, Text, TextType
from apps.sources.models import Document, Source

DATA = Path(__file__).resolve().parents[2] / 'data' / 'constitutions.json'


class Command(BaseCommand):
    help = "Load Morocco's constitutions since 1962 from Adala."

    def add_arguments(self, parser):
        parser.add_argument('--no-french', action='store_true', help='leave the French as it is (its reading takes minutes)')

    def handle(self, *args, **opts):
        from apps.search.services import index

        texts, before = [], None
        for c in json.loads(DATA.read_text())['constitutions']:
            call_command('load_adala', c['file'], article_word='الفصل', as_of=c['published'], uri=c['uri'],
                         stdout=self.stdout)
            text = Text.objects.get(akn_uri=c['uri'])
            # Each file is the text as first issued (the stamp says so), its BO issue and page from the data where
            # the file's footnote gives none (1992, 1996).
            doc = Document.objects.get(source=Source.ADALA, path=c['file'])
            number = int(c['issue'].split()[0])
            doc.meta = {**doc.meta, 'as_issued': True, 'first_issue': doc.meta.get('first_issue') or number,
                        'first_page': doc.meta.get('first_page') or c['page']}
            doc.save(update_fields=['meta'])
            text.type = TextType.CONSTITUTION
            text.status = Status.IN_FORCE if c['in_force'] else Status.REPEALED
            text.signed_on = date.fromisoformat(c['signed'])
            text.title_ar = re.sub(r'\s+\d{1,2}$', '', text.title_ar)    # the title's footnote mark, «… الدستور 1»
            text.save(update_fields=['type', 'status', 'signed_on', 'title_ar', 'updated_at'])
            texts.append(text)
            if before and c.get('repeals'):
                _repeals(before, c, text)
            before = text
            self.stdout.write(f"{c['year']}: {text.versions.get(consolidation='adala').articles.count()} parts, "
                              f"{text.get_status_display()}, BO {c['issue']} of {c['published']}, p. {c['page']}")
        for c, text in zip(json.loads(DATA.read_text())['constitutions'], texts):
            if c.get('revisions'):
                self.stdout.write(f"{c['year']}: {_revise(text, c['revisions'])}")
            if (fr := c.get('french')) and not opts['no_french']:
                call_command('load_bo_french', fr['file'], url=fr['url'], text=c['uri'], pages=fr['pages'], issue=fr['issue'],
                             issue_date=fr['date'], title=fr['title'], start=fr['start'], align=fr.get('align', False),
                             stdout=self.stdout, stderr=self.stderr)
        index.rebuild(texts, log=self.stdout.write)


def _revise(text: Text, revisions: list[dict]) -> str:
    """A constitution's revisions adopted by referendum (C10 of the constitution review: 1972's of 1980, 1992's of
    1995), each article's paragraph as the BO prints it, written as changes read in the BO and put into a version by the
    links engine on the day each took effect (the as-issued text stays as Adala gives it)."""
    from apps.consolidation.models import Change, Verb
    from apps.consolidation.services import engine
    from apps.corpus.services import works

    mine = {f"/akn/ma/act/dahir/{r['dahir']}" for r in revisions}
    Change.objects.filter(text_uri=text.akn_uri, by_uri__in=mine, source=Change.Source.READING).delete()
    rows = []
    for r in revisions:
        uri, issue = f"/akn/ma/act/dahir/{r['dahir']}", r['issue'].split()
        works.wait(uri, 'dahir', r['dahir'], r['title'])
        published, effective = date.fromisoformat(r['published']), date.fromisoformat(r['effective'])
        for a in r['articles']:
            common = dict(text_uri=text.akn_uri, number=a['number'], source=Change.Source.READING, by_kind='dahir',
                          by_number=r['dahir'], by_uri=uri, issue=int(issue[0]), issue_bis=len(issue) > 1, page=r['page'],
                          published_on=published, effective_on=effective, state=Change.State.READ,
                          effective_rule=Change.Rule.STATED if r['effective_words'] else Change.Rule.PUBLICATION,
                          effective_words=r['effective_words'])
            if 'words' in a:        # «ينتخب اعضاء مجلس النواب لمدة ست سنوات . . . (باقي الفقرة لا تغيير فيه)»
                rows.append(Change(**common, verb=Verb.WORDS, wording=[a['printed']],
                                   detail={'pairs': a['words'], 'referendum': r['referendum']}))
            else:
                rows.append(Change(**common, verb=Verb.MODIFIED, wording=[a['wording']],
                                   detail={'part': ['الفقرة', [a['paragraph']]], 'referendum': r['referendum']}))
    Change.objects.bulk_create(rows)
    changes, doubts, stats = engine.apply_to(text, set())
    Change.objects.bulk_update(changes, ['placed', 'detail', 'witnesses', 'state'])
    placed = sum(1 for c in changes if c.by_uri in mine and c.placed)
    return f"{placed} of {len(rows)} revised paragraphs placed, {stats.get('versions', 0)} versions" + (
        f", doubts: {[d.reason for d in doubts]}" if doubts else '')


def _repeals(old: Text, c: dict, by: Text) -> None:
    """The earlier constitution repealed whole by this one, as read in its text: «يلغى الدستور …» (1970's dahir, 1972's
    art. 103), «ينسخ نص الدستور المراجع …» (2011's art. 180), or a revision the dahir promulgates whole (1992, 1996)."""
    from apps.consolidation.models import Change, Verb

    issue = c['issue'].split()
    published = date.fromisoformat(c['published'])
    Change.objects.filter(text_uri=old.akn_uri, by_uri=by.akn_uri, source=Change.Source.READING, number='').delete()
    Change.objects.create(
        text_uri=old.akn_uri, number='', verb=Verb.REPEALED, source=Change.Source.READING, by_kind='dahir',
        by_number=by.number, by_uri=by.akn_uri, by_article=c['repeals']['article'], issue=int(issue[0]),
        issue_bis=len(issue) > 1, page=c['page'], published_on=published, effective_on=published,
        effective_rule=Change.Rule.PUBLICATION, state=Change.State.READ,
        detail={'clause': c['repeals']['clause'], **({'note': c['repeals']['note']} if c['repeals'].get('note') else {})})
