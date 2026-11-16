"""`archive export` and `archive import`: each issue a phase has done written as one file where the run read it, and
registered here from the same PDF with its pages, readings, contents, texts and doubts."""
import gzip
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError

from apps.corpus.services.archive_run.common import issue_of, workdir
from apps.quality.services.corrections import reapply_pages
from apps.sources.models import Edition, Issue, OcrRun, Page, TextSource
from apps.sources.services import archive
from apps.sources.services import issue as issue_service


class Exchange:
    """The run's issues carried between machines, as files."""

    RUN_FIELDS = ('engine', 'variant', 'prompt_version', 'image_px', 'input_tokens', 'output_tokens', 'batch_id',
                  'stop_reason', 'seconds', 'text')

    def export(self, phase: str, out: str | None, keys: str | None, edition: str = Edition.GENERAL_AR) -> None:
        """Each issue `phase` has done (or `keys`) as one file, written again only when the issue changed since. A French
        issue (`--french`) goes with its pages and readings only: its translations travel as translate_french files."""
        if not out:
            raise CommandError('--out is needed')
        if edition != Edition.GENERAL_AR and not keys:
            raise CommandError('--french needs --keys')
        folder = Path(out)
        folder.mkdir(parents=True, exist_ok=True)
        chosen = keys.split(',') if keys else [k for k in self.keys_for(phase, {'keys': None}) if archive.done(phase, k)]
        written = 0
        for key in chosen:
            issue = issue_of(key, edition)
            if issue is None:
                continue
            target = folder / f'{key}.json.gz'
            done = archive._state(phase) / f'{key}.done'
            if target.exists() and done.exists() and target.stat().st_mtime >= done.stat().st_mtime:
                continue
            doc = issue.document
            work = workdir(key)
            french = edition != Edition.GENERAL_AR
            bundle = {
                'key': key, 'phase': phase, 'edition': edition,
                'issue': {'number': issue.number, 'suffix': issue.suffix, 'date': issue.date.isoformat(),
                          'hijri_date': issue.hijri_date, 'first_page_number': issue.first_page_number},
                'document': {'sha256': doc.sha256, 'url': doc.url, 'archive': doc.meta.get('archive', ''),
                             'page_count': doc.page_count},
                'pages': [{'index': p.index, 'printed_number': p.printed_number, 'text': p.text,
                           'text_source': p.text_source, 'quality': p.quality,
                           'runs': [{**{f: getattr(r, f) for f in self.RUN_FIELDS}, 'cost_usd': str(r.cost_usd),
                                     'created_at': r.created_at.isoformat()} for r in p.ocr_runs.all()]}
                          for p in doc.pages.order_by('index').prefetch_related('ocr_runs')],
                'files': {} if french else {name: json.loads((work / name).read_text())
                                            for name in ('toc.json', 'texts.json') if (work / name).exists()},
                'doubts': (json.loads(d.read_text()) if not french and (d := archive.root() / 'doubts' / f'{key}.json').exists()
                           else None),
            }
            part = target.with_name(target.name + '.part')
            with gzip.open(part, 'wt', encoding='utf-8') as f:
                json.dump(bundle, f, ensure_ascii=False)
            part.rename(target)
            written += 1
        self.log(f'exported {written} issues to {folder}')

    def import_(self, folder: str | None, pdfs: str | None) -> None:
        """The exported issues into this database: the same PDF registered (its pages read as here), each page's
        text and folio, every reading with its price (they count in this ledger's spending), the contents and texts
        files. An issue read here before keeps its pages and files (its new readings join as witnesses); a reading
        already here is not added twice."""

        if not folder or not pdfs:
            raise CommandError('import needs --folder and --pdfs')
        added = runs_added = kept_issues = 0
        for path in sorted(Path(folder).glob('*.json.gz')):
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                b = json.load(f)
            key, info = b['key'], b['issue']
            # A French issue of A (`export --french`): registered under its own edition, its file the French one.
            edition = b.get('edition') or Edition.GENERAL_AR
            french = edition != Edition.GENERAL_AR
            links = Path(settings.CORPUS_DIR) / 'issues' / ('bo_fr' if french else 'bo_ar')
            links.mkdir(parents=True, exist_ok=True)
            issue = issue_of(key, edition)
            if issue and issue.document.sha256 != b['document']['sha256']:
                self.log(f'{key}: already here from another file; left as it is')
                continue
            registered = issue is None
            if issue is None:
                link = links / f'BO_{key}_{"fr" if french else "ar"}.pdf'
                if not link.exists():
                    link.symlink_to(Path(pdfs) / (b['document']['archive'] or link.name))
                issue = issue_service.register(link, edition=edition, number=info['number'],
                                               suffix=info['suffix'], day=date.fromisoformat(info['date']),
                                               url=b['document']['url'])
                doc = issue.document
                doc.meta = {**doc.meta, 'archive': b['document']['archive'], 'archive_read': True}
                doc.save(update_fields=['meta'])
                added += 1
            if issue.document.sha256 != b['document']['sha256']:
                raise CommandError(f'{key}: the PDF here is not the one the archive run read')
            pages = {p.index: p for p in issue.document.pages.prefetch_related('ocr_runs')}
            # An issue read here before (the 2019 run, a topic's texts read against their pages) keeps its pages'
            # text and its files: the archive run's readings join its runs as witnesses only. One an import filled
            # before (`archive_read`) takes the archive run's pages again: they were read again since (Z16, Z17).
            kept = (not registered and not issue.document.meta.get('archive_read')
                    and any(p.text_source == TextSource.OCR for p in pages.values()))
            if not kept:
                Issue.objects.filter(pk=issue.pk).update(first_page_number=info['first_page_number'],
                                                         hijri_date=info['hijri_date'] or issue.hijri_date)
                # Its words are the archive's: the links never put them over an official consolidation (archive 24).
                doc = issue.document
                if 'archive' not in doc.meta or not doc.meta.get('archive_read'):
                    doc.meta = {**doc.meta, 'archive': doc.meta.get('archive') or b['document']['archive'],
                                'archive_read': True}
                    doc.save(update_fields=['meta'])
            changed, new_runs = [], []
            for item in b['pages']:
                page = pages.get(item['index'])
                if page is None:
                    continue
                if not kept:
                    page.printed_number, page.text = item['printed_number'], item['text']
                    page.text_source, page.quality = item['text_source'], item['quality']
                    changed.append(page)
                have = {(r.engine, r.variant, r.batch_id, r.text[:200]) for r in page.ocr_runs.all()}
                for r in item['runs']:
                    if (r['engine'], r['variant'], r['batch_id'], r['text'][:200]) in have:
                        continue
                    new_runs.append(OcrRun(page=page, cost_usd=Decimal(r['cost_usd']),
                                           **{f: r[f] for f in self.RUN_FIELDS}))
            reapply_pages(changed)      # words read against a page's image stay put right (FX2 of the mended-Bulletin review)
            Page.objects.bulk_update(changed, ['printed_number', 'text', 'text_source', 'quality'], batch_size=500)
            OcrRun.objects.bulk_create(new_runs, batch_size=500)
            runs_added += len(new_runs)
            if kept:
                kept_issues += 1
                continue
            if french:
                continue
            work = workdir(key)
            for name, content in b['files'].items():
                (work / name).write_text(json.dumps(content, ensure_ascii=False, indent=1))
            if b['doubts']:
                d = archive.root() / 'doubts' / f'{key}.json'
                d.parent.mkdir(parents=True, exist_ok=True)
                d.write_text(json.dumps(b['doubts'], ensure_ascii=False))
        self.log(f'imported: {added} issues registered, {runs_added} readings added, {kept_issues} issues read here '
                 'before kept as they were')
