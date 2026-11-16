"""The database as files: one edition a month (`export_open_data`, deploy/law-edition.timer), written under
OPEN_DATA_DIR/<date>/ and given to anyone or on request (apps/opendata/views.py, services/editions.py).

An edition holds, each as gzip JSON lines:
- texts.jsonl.gz: one line a text, its facts and its newest version's articles, the changes it makes that are
  settled, the texts it cites;
- versions.jsonl.gz: every other version of a text, with its articles;
- french.jsonl.gz: the official French of the texts that have one, article by article;
- changes.jsonl.gz: which text changes which, in every state, as read from the Bulletin or as an official
  consolidation states it;
- issues.jsonl.gz: the Bulletin's issues held;
- aliases.jsonl.gz: a text's older addresses;
and akn.zip (each text's newest version as Akoma Ntoso), the licence, README.md, schema.json, CHANGELOG.md and the
manifest, which counts every file's lines and gives its bytes and SHA-256.

No article's words are written twice across files, and nothing is held whole in memory: every file is written a chunk
at a time, each chunk read in a fixed number of queries whatever the corpus holds (tests/test_loops.py), and each
file's hash is computed while it is written."""
import gzip
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.db.models import Prefetch, Q, prefetch_related_objects
from django.utils import timezone

from apps.consolidation.models import Change
from apps.corpus.models import Alias, Consolidation, Mention, Text, Version, latest_ids
from apps.corpus.services.addresses import article_path, text_path
from apps.corpus.services.citing import citation_ar
from apps.opendata.services import editions
from apps.opendata.services.akn import akn_xml
from apps.sources.models import Issue
from apps.translations.models import FrenchArticle, FrenchText

# The files written as they are, with the site's name, its address and the format's number put in.
SHIPPED = Path(__file__).resolve().parent.parent / 'data'
WORDS = ('README.md', 'schema.json', 'CHANGELOG.md')

# Texts read together: their versions, the chosen versions' articles, the changes they make and the texts they cite come
# in five queries a chunk, whatever the corpus, and a chunk's articles are what the process holds.
CHUNK = 500
# The other versions read together: a code's versions may each hold hundreds of articles.
VERSIONS = 100
AMENDS = ('checked', 'confirmed', 'read')
# The changes an edition gives: read from the Bulletin in every state, stated by an official consolidation, and a
# bill's proposals as proposals. Never a model's list: a witness, never placed alone.
CHANGES = (Q(source__in=(Change.Source.READING, Change.Source.SGG, Change.Source.ADALA, Change.Source.DGI))
           | Q(source=Change.Source.BILL, state=Change.State.PROPOSED))
LICENCE_LINE = 'ODbL 1.0 (the database); official texts free of copyright (law 2-00 art. 8)'


def _address() -> str:
    """The site's address as a reuser writes it in a credit: SITE_URL without its scheme."""
    return urlsplit(settings.SITE_URL).netloc or settings.SITE_NAME


def licence() -> str:
    site, address = settings.SITE_NAME, _address()
    return f"""«قانون» — قاعدة البيانات، برخصة مفتوحة / {site} — the database, under an open licence

النصوص: النصوص الرسمية المنشورة في الجريدة الرسمية لا يحميها حق المؤلف (القانون رقم 2.00، المادة 8)،
ويُعاد استعمالها مع ذكر المصدر وتاريخه (القانون رقم 31.13، المادة 6).
قاعدة البيانات التي بناها «قانون» (التقطيع إلى مواد، العناوين، العناوين الثابتة، الإحالات، التعديلات): رخصة قاعدة
البيانات المفتوحة (ODbL 1.0) — اذكر {address} ومصدر النص (عدد الجريدة الرسمية وتاريخه)، وكل قاعدة بيانات تبنيها
عليها وتنشرها، انشرها بالرخصة نفسها.

The texts: official texts published in the Bulletin officiel carry no copyright (law 2-00, art. 8) and may be
reused with their source and date (law 31-13, art. 6). The database {site} builds (articles, titles, stable
addresses, citations, amendments) is made available under the Open Data Commons Open Database License (ODbL) v1.0 —
credit {address} and each text's source (its BO issue and date), and share any adapted database you publish under the
same licence. https://opendatacommons.org/licenses/odbl/1-0/

Unofficial: only the text published in the Bulletin officiel is authoritative. Each record names the kind of version
it holds (`version.kind`, listed in manifest.json and README.md): `as_published` is the text as the Bulletin printed it;
a consolidation (the SGG's, Adala's, the DGI's, a person's), a bill, a consolidation made by machine (`machine`) and a
translation made by artificial intelligence from the official French (`translation`) are not the official text. The
last two are marked by their kind wherever they appear.

غير رسمي: وحده النص المنشور في الجريدة الرسمية يُعتدّ به. يذكر كل سجل نوع النسخة التي يحملها (version.kind):
as_published هي النص كما نشرته الجريدة الرسمية، أما النسخة المحيَّنة (من الأمانة العامة للحكومة أو بوابة عدالة أو
المديرية العامة للضرائب أو شخص) ومشروع القانون والنسخة المحيَّنة آليا (machine) والترجمة التي أنجزها الذكاء الاصطناعي
عن النص الفرنسي الرسمي (translation) فليست النص الرسمي، ونوع كل واحدة منها مذكور حيثما وردت.

Named people: what the Bulletin prints about named people in individual decisions (appointments, licences,
naturalisations, judgments…) is personal data. Whoever receives this database is alone responsible for what they do
with it under law 09-08 on the protection of individuals with regard to the processing of personal data.

الأشخاص المسمَّون: ما تنشره الجريدة الرسمية عن أشخاص مسمَّين في القرارات الفردية (التعيينات، الرخص، التجنيس،
الأحكام…) معطيات ذات طابع شخصي، ومن يتلقى قاعدة البيانات هذه يتحمل وحده مسؤولية ما يفعله بها وفق القانون رقم 09.08
المتعلق بحماية الأشخاص الذاتيين تجاه معالجة المعطيات ذات الطابع الشخصي.
"""


class Sink:
    """A file being written, its bytes counted and hashed as they go: no file is read back to be hashed. It cannot
    seek, so a zip archive is written straight through (each entry's sizes after it) and never rewritten in place."""

    def __init__(self, path: Path):
        self.raw = open(path, 'wb')
        self.hash = hashlib.sha256()
        self.bytes = 0

    def write(self, data) -> int:
        self.raw.write(data)
        self.hash.update(data)
        n = memoryview(data).nbytes
        self.bytes += n
        return n

    def tell(self) -> int:
        return self.bytes

    def flush(self):
        self.raw.flush()

    def close(self) -> dict:
        self.raw.close()
        return {'bytes': self.bytes, 'sha256': self.hash.hexdigest()}


class Lines:
    """A gzip file of JSON lines, one record a line, counted and hashed as it is written."""

    def __init__(self, path: Path):
        self.sink = Sink(path)
        # No name and no time in the gzip header: the same records make the same bytes.
        self.gz = gzip.GzipFile(filename='', mode='wb', fileobj=self.sink, compresslevel=6, mtime=0)
        self.lines = 0

    def write(self, record: dict):
        self.gz.write((json.dumps(record, ensure_ascii=False) + '\n').encode())
        self.lines += 1

    def close(self) -> dict:
        self.gz.close()
        return {**self.sink.close(), 'lines': self.lines}


def _day(d):
    return d and d.isoformat()


def version_of(version) -> dict:
    """What a record's words are: the text as the Bulletin printed it (`as_published`), a consolidation (the SGG's,
    Adala's, the DGI's, a person's or the machine's), a bill, or a translation made by AI from the official French;
    the days it stands between; and the file its words were read from, when one is (a machine's consolidation is built
    from the changes, not read). The manifest and the README name every kind."""
    document = version.source_document
    return {'kind': version.consolidation, 'language': version.language,
            'valid_from': version.valid_from.isoformat(), 'valid_to': _day(version.valid_to),
            'translated_from': version.translated_from or None,
            'file': document and {'source': document.source, 'sha256': document.sha256},
            'pages': version.source_pages or None}


def _articles(akn_uri: str, version) -> list[dict]:
    return [{'eid': a.eid, 'label': a.label, 'number': a.number, 'heading_path': a.heading_path,
             'path': article_path(akn_uri, a.eid), 'page': a.printed_page, 'body': a.body}
            for a in version.articles.all()]


def _record(text: Text, version, amends: list, cites: list) -> dict:
    issue = text.first_published_in
    document = issue and issue.document
    return {
        'akn_uri': text.akn_uri, 'path': text_path(text.akn_uri), 'type': text.type, 'number': text.number_as_printed,
        'title': text.title_ar, 'signed_on': _day(text.signed_on),
        'signed_on_hijri': text.signed_on_hijri, 'authority': text.authority, 'status': text.status,
        'source': issue and {'issue': issue.key, 'edition': issue.edition, 'date': issue.date.isoformat(),
                             'page': text.first_published_page, 'sha256': document and document.sha256},
        'version': version_of(version),
        'citation': citation_ar(text),
        'articles': _articles(text.akn_uri, version),
        'amends': [{'target': c.text_uri, 'article': c.number, 'action': c.verb, 'takes_effect': _day(c.effective_on),
                    'state': c.state} for c in amends],
        'cites': sorted(set(cites)),
    }


def _text_ids():
    """The texts with words, by id, CHUNK at a time."""
    ids = list(Text.objects.filter(versions__isnull=False).distinct().order_by('id').values_list('id', flat=True))
    for start in range(0, len(ids), CHUNK):
        yield ids[start:start + CHUNK]


def _by_pk(queryset):
    """A table's rows CHUNK at a time, in the order of their keys: one query a chunk."""
    last = None
    while True:
        rows = queryset if last is None else queryset.filter(pk__gt=last)
        chunk = list(rows.order_by('pk')[:CHUNK])
        if chunk:
            yield chunk
        if len(chunk) < CHUNK:
            return
        last = chunk[-1].pk


def _chunks():
    """The texts with words, in order, a chunk at a time, each with its newest version (`Text.latest_version()`'s),
    that version's articles, the changes it reads into other texts and the texts it cites."""
    versions_read = Prefetch('versions', queryset=Version.objects.select_related('source_document'))
    for ids in _text_ids():
        chunk = list(Text.objects.filter(id__in=ids).select_related('first_published_in__document')
                     .prefetch_related(versions_read).order_by('id'))
        versions = {t.pk: t.latest_version() for t in chunk}
        prefetch_related_objects(list(versions.values()), 'articles')
        uris = [t.akn_uri for t in chunk]
        amends, cites = {}, {}
        for c in Change.objects.filter(by_uri__in=uris, source=Change.Source.READING, state__in=AMENDS).order_by('pk'):
            amends.setdefault(c.by_uri, []).append(c)
        for uri, to in Mention.objects.filter(from_uri__in=uris, kind=Mention.Kind.CITES,
                                              state=Mention.State.RESOLVED).values_list('from_uri', 'to_uri'):
            cites.setdefault(uri, []).append(to)
        for text in chunk:
            yield text, versions[text.pk], amends.get(text.akn_uri, []), cites.get(text.akn_uri, [])


def _versions():
    """Every version but the one texts.jsonl.gz carries (each text's newest, as `Text.latest_version()` picks it), with
    its articles: the versions' days and kinds a chunk of texts at a time, then their words VERSIONS at a time. A text's
    versions come together, the oldest first."""
    for ids in _text_ids():
        rows = list(Version.objects.filter(text_id__in=ids)
                    .values_list('pk', 'text_id', 'valid_from', 'consolidation', 'language'))
        newest = set(latest_ids((pk, text, start, kind) for pk, text, start, kind, _ in rows).values())
        others = [r[0] for r in sorted(rows, key=lambda r: (r[1], r[4], r[2], r[0])) if r[0] not in newest]
        for start in range(0, len(others), VERSIONS):
            batch = (Version.objects.filter(pk__in=others[start:start + VERSIONS])
                     .select_related('text', 'source_document').prefetch_related('articles')
                     .order_by('text_id', 'language', 'valid_from', 'pk'))
            for version in batch:
                uri = version.text.akn_uri
                yield {'akn_uri': uri, 'path': text_path(uri), 'version': version_of(version),
                       'articles': _articles(uri, version)}


def _french():
    """The official French of the texts that have one, article by article, with the issue of the Bulletin's translation
    edition that printed it: a chunk of texts, then their articles in one query."""
    for chunk in _by_pk(FrenchText.objects.all()):
        articles = {}
        for a in FrenchArticle.objects.filter(text_uri__in=[t.text_uri for t in chunk]).order_by('text_uri', 'order'):
            articles.setdefault(a.text_uri, []).append(a)
        for t in chunk:
            yield {
                'akn_uri': t.text_uri, 'path': text_path(t.text_uri), 'type': t.type, 'number': t.number or None,
                'title': t.title, 'signed_on': _day(t.signed_on),
                'source': {'edition': 'translation_fr',
                           'issue': f'{t.issue_number}-{t.issue_suffix}' if t.issue_suffix else str(t.issue_number),
                           'date': t.issue_date.isoformat(), 'pages': t.pages or None, 'sha256': t.document_sha or None},
                'consolidated_to': _day(t.consolidated_to),
                'articles': [{'label': a.label, 'number': a.number, 'page': a.printed_page, 'body': a.body}
                             for a in articles.get(t.text_uri, [])],
            }


def _changes():
    """Which text changes which article of which: every link read from the Bulletin, the unclear and conflicting ones
    included and said so, those an official consolidation states, and a bill's proposals as proposals."""
    for chunk in _by_pk(Change.objects.filter(CHANGES)):
        for c in chunk:
            yield {
                'target': c.text_uri, 'target_path': text_path(c.text_uri), 'article': c.number or None,
                'action': c.verb,
                'by': {'akn_uri': c.by_uri or None, 'path': c.by_uri and text_path(c.by_uri), 'kind': c.by_kind,
                       'number': c.by_number, 'article': c.by_article or None},
                'issue': c.issue and (f'{c.issue}-bis' if c.issue_bis else str(c.issue)), 'page': c.page,
                'published_on': _day(c.published_on), 'takes_effect': _day(c.effective_on),
                'effective_rule': c.effective_rule or None,
                'source': c.source, 'state': c.state or None,
            }


def _issues():
    """Every issue of the Bulletin held, with its file's hash and pages where the file is held."""
    for chunk in _by_pk(Issue.objects.select_related('document', 'copy_of')):
        for i in chunk:
            doc = i.document
            yield {
                'edition': i.edition, 'number': i.number, 'suffix': i.suffix or None, 'key': i.key,
                'date': i.date.isoformat(), 'hijri_date': i.hijri_date or None, 'path': f'/bo/{i.edition}/{i.key}',
                'first_page': i.first_page_number, 'copy_of': i.copy_of and i.copy_of.key,
                'file': doc and {'sha256': doc.sha256, 'pages': doc.page_count, 'bytes': doc.bytes,
                                 'url': doc.url or None},
            }


def _aliases():
    """A text's older addresses, and the address each leads to."""
    for chunk in _by_pk(Alias.objects.all()):
        for a in chunk:
            yield {'alias': a.alias, 'alias_path': text_path(a.alias), 'akn_uri': a.uri, 'path': text_path(a.uri),
                   'reason': a.reason}


def _words(name: str) -> bytes:
    return ((SHIPPED / name).read_text(encoding='utf-8').replace('@SITE@', settings.SITE_NAME)
            .replace('@SITE_URL@', settings.SITE_URL.rstrip('/')).replace('@ADDRESS@', _address()).replace('@FORMAT@', str(editions.FORMAT)).encode())


def _small(path: Path, data: bytes) -> dict:
    path.write_bytes(data)
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write_dump(log=print) -> Path:
    """Write today's edition (Morocco's day) beside the folder it will become, then put it in place, record its
    manifest's hash, point `latest` at it and let go of the editions past the newest three."""
    base = editions.root()
    base.mkdir(parents=True, exist_ok=True)
    day = timezone.localdate().isoformat()
    final = base / day
    if final.exists() and editions.read(final) is None:
        raise FileExistsError(f'{final} was not written by this export in format {editions.FORMAT}: move it first')
    for stale in (*base.glob('.*.part'), *base.glob('.*.old')):     # what a stopped export left
        shutil.rmtree(stale)
    work = base / f'.{day}.part'
    work.mkdir()
    files = {}

    texts, sink, articles = Lines(work / 'texts.jsonl.gz'), Sink(work / 'akn.zip'), 0
    with zipfile.ZipFile(sink, 'w', zipfile.ZIP_DEFLATED) as zf:
        for text, version, amends, cites in _chunks():
            record = _record(text, version, amends, cites)
            texts.write(record)
            zf.writestr(text.akn_uri.strip('/').replace('/', '_') + '.xml', akn_xml(text, version))
            articles += len(record['articles'])
    files['texts.jsonl.gz'] = texts.close()
    files['akn.zip'] = {**sink.close(), 'entries': texts.lines}
    for name, records in (('versions.jsonl.gz', _versions()), ('french.jsonl.gz', _french()),
                          ('changes.jsonl.gz', _changes()), ('issues.jsonl.gz', _issues()),
                          ('aliases.jsonl.gz', _aliases())):
        lines = Lines(work / name)
        for record in records:
            lines.write(record)
        files[name] = lines.close()
    files['LICENCE.txt'] = _small(work / 'LICENCE.txt', licence().encode())
    for name in WORDS:
        files[name] = _small(work / name, _words(name))

    counts = {'texts': files['texts.jsonl.gz']['lines'], 'articles': articles,
              'versions': files['texts.jsonl.gz']['lines'] + files['versions.jsonl.gz']['lines']}
    manifest = {'format': editions.FORMAT, 'date': day, **counts, 'files': files, 'licence': LICENCE_LINE,
                'version_kinds': {kind: str(label) for kind, label in Consolidation.choices}}
    (work / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    # nginx sends the files (OPEN_DATA_ACCEL): readable by its account whatever this one's umask.
    os.chmod(work, 0o755)  # noqa: S103 — nginx's account reads it; nothing in it is secret
    for path in work.iterdir():
        os.chmod(path, 0o644)

    if final.exists():                       # an edition of the same day, written again
        final.rename(base / f'.{day}.old')
        work.rename(final)
        shutil.rmtree(base / f'.{day}.old')
    else:
        work.rename(final)
    latest = base / 'latest'
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(final.name)
    edition = editions.read(final)
    editions.record(edition, counts)
    gone = editions.prune()
    log(f'open data: {counts["texts"]} texts, {articles} articles, {counts["versions"]} versions → {final} '
        f'(manifest {edition.sha256[:12]}…){"; let go of " + ", ".join(gone) if gone else ""}')
    return final
