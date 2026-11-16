"""Corrections read against a document's page images (F1 of the family plan): a YAML file names the text, the file
it was read in, and each word put right with its articles; `headings` lists words put right in the divisions' headings,
wherever they stand. Each becomes a correction «read against the page's image», applied now and again at every reload
of the text, and listed in «ما صححناه» at the first article its heading stands over. A correction recorded before is
already in the text, so running a file again changes nothing (a word put back, «بنص» → «بنص تنظيمي», is put back once).
`title` and `preamble` list words put right in the title and the visas, as they stand (no correction recorded).

    apply_page_reading apps/quality/data/family_code_70_03.yaml

Since the mended-Bulletin review (FX2, 2 Nov 2026) a file may hold several texts, one YAML document each (`---`); a fix
may name its articles by address (`eids: [art_1]`), for articles whose label carries no number; `pages` puts words
right in the page readings of the text's issue, each page by its place in the file (`index`, 0-based), recorded and
applied again whenever the page is read anew; `signed_on` sets the text's date as printed, `title_is` its whole heading as printed; and a document may name an
issue instead of a text (`issue: {edition: general_ar, number: 1}`) for pages no text holds, a cover for one.
"""
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.corpus.models import Text
from apps.corpus.services.addresses import article_path, split_path
from apps.quality.models import Correction
from apps.quality.services.corrections import headings_right, put_right


class Command(BaseCommand):
    help = "Record and apply the corrections a YAML file lists, read against the document's page images."

    def add_arguments(self, parser):
        parser.add_argument('file')

    def handle(self, *args, file, **opts):
        path = Path(file)
        if not path.is_file():
            if path.name.startswith('pages_reread_'):
                raise CommandError(f'{file}: no such file. The pages of the Bulletin read again on their images '
                                   '(pages_reread_*) are not in the code repository: they come with the data release.')
            raise CommandError(f'{file}: no such file.')
        for spec in yaml.safe_load_all(path.read_text()):
            if not spec:
                continue
            if 'text' in spec:
                self.text_spec(spec)
            else:
                self.issue_spec(spec)

    def issue_spec(self, spec):
        from apps.sources.models import Issue
        key = spec['issue']
        issue = Issue.objects.filter(edition=key['edition'], number=key['number'], suffix=key.get('suffix', '')).first()
        if issue is None:
            raise CommandError(f'{key}: no such issue')
        made, changed, missing = self.pages(issue, spec)
        self.stdout.write(f'BO {issue.key} ({issue.edition}): {made} page corrections recorded, {changed} pages changed')
        for m in missing:
            self.stdout.write(f'  not applied: {m}')

    def pages(self, issue, spec) -> tuple[int, int, list[str]]:
        """The words put right in the issue's page readings, each recorded against its page."""
        from apps.quality.services.corrections import page_path
        from apps.sources.models import Page
        made = changed = 0
        missing = []
        for fix in spec.get('pages') or []:
            page = Page.objects.filter(document=issue.document_id, index=fix['index']).first()
            if page is None:
                missing.append(f'page {fix["index"]}: no such page')
                continue
            c, created = Correction.objects.get_or_create(
                path=page_path(issue, page.index), wrong=fix['wrong'], right=fix['right'], before='', after='',
                defaults={'source': Correction.Source.PAGE, 'status': Correction.Status.APPLIED,
                          'decided_at': timezone.now(),
                          'evidence': {'document': spec.get('document', ''), 'read_on': spec['read_on']}})
            made += created
            text = put_right(page.text, c)
            if text != page.text:
                page.text = text
                page.save(update_fields=['text'])
                changed += 1
            elif fix['right'] not in page.text:
                missing.append(f'page {fix["index"]}: «{fix["wrong"]}» not found')
        return made, changed, missing

    def text_spec(self, spec):
        uri, _ = split_path(spec['text'].strip('/'))
        text = Text.objects.filter(akn_uri=uri).first()
        if text is None:
            raise CommandError(f'{spec["text"]}: no such text')
        versions = list(text.versions.filter(language='ar'))
        made = changed = 0
        missing = []
        for fix in spec.get('fixes') or []:
            for n in [*fix.get('arts', []), *(('eid', e) for e in fix.get('eids', []))]:
                if isinstance(n, tuple):
                    rows = [a for v in versions for a in v.articles.filter(eid=n[1])]
                    n = n[1]
                else:
                    rows = [a for v in versions for a in v.articles.filter(number=str(n))]
                if not rows:
                    missing.append(f'art. {n}')
                    continue
                path = article_path(uri, rows[0].eid)
                probe = Correction(wrong=fix['wrong'], right=fix['right'])
                if not Correction.objects.filter(path=path, wrong=fix['wrong'], right=fix['right']).exists() \
                        and not any(put_right(a.body, probe) != a.body for a in rows):
                    continue        # not in this article (a fix naming two addresses, before and after a renumbering)
                c, created = Correction.objects.get_or_create(
                    path=path, wrong=fix['wrong'], right=fix['right'], before='', after='',
                    defaults={'source': Correction.Source.PAGE, 'status': Correction.Status.APPLIED,
                              'decided_at': timezone.now(),
                              'evidence': {'document': spec.get('document', ''), 'read_on': spec['read_on']}})
                made += created
                if not created:
                    continue      # recorded before: already in the text (applied then, and again at each reload)
                hit = False
                for a in rows:
                    body = put_right(a.body, c)
                    if body != a.body:
                        a.body = body
                        a.save(update_fields=['body'])
                        hit = True
                changed += hit
                if not hit and created:
                    missing.append(f'art. {n}: «{fix["wrong"]}» not found')
        evidence = {'document': spec.get('document', ''), 'read_on': spec['read_on']}
        rows = [a for v in versions for a in v.articles.order_by('order')]
        for fix in spec.get('headings') or []:
            probe = Correction(wrong=fix['wrong'], right=fix['right'])
            first = next((a for a in rows if headings_right(a.heading_path or [], [probe]) != a.heading_path), None)
            c = Correction.objects.filter(path__startswith=article_path(uri, ''), wrong=fix['wrong'], right=fix['right'],
                                          evidence__headings=True).first()
            if c is not None:
                continue          # recorded before: already in the headings
            if first is None:
                missing.append(f'heading «{fix["wrong"]}» not found')
                continue
            c = Correction.objects.create(
                path=article_path(uri, first.eid), wrong=fix['wrong'], right=fix['right'],
                source=Correction.Source.PAGE, status=Correction.Status.APPLIED, decided_at=timezone.now(),
                evidence={**evidence, 'headings': True})
            made += 1
            for a in rows:
                heading = headings_right(a.heading_path or [], [c])
                if heading != a.heading_path:
                    a.heading_path = heading
                    a.save(update_fields=['heading_path'])
                    changed += 1
        # The title and the preamble (BO 7554, 1 Nov 2026: a minister's name misread in a dahir's title, a visa cut short
        # by the columns): put right as they stand, once; a reload of the text needs the file run again.
        for fix in spec.get('title') or []:
            if fix['wrong'] in text.title_ar:
                text.title_ar = text.title_ar.replace(fix['wrong'], fix['right'])
                Text.objects.filter(pk=text.pk).update(title_ar=text.title_ar)
                changed += 1
            elif fix['right'] not in text.title_ar:
                missing.append(f'title: «{fix["wrong"]}» not found')
        for fix in spec.get('preamble') or []:
            hit = [v for v in versions if fix['wrong'] in v.preamble]
            for v in hit:
                v.preamble = v.preamble.replace(fix['wrong'], fix['right'])
                v.save(update_fields=['preamble'])
            changed += len(hit)
            if not hit and not any(fix['right'] in v.preamble for v in versions):
                missing.append(f'preamble: «{fix["wrong"]}» not found')
        if spec.get('title_is') and text.title_ar != spec['title_is']:
            Text.objects.filter(pk=text.pk).update(title_ar=spec['title_is'])      # a heading as printed, whole
            changed += 1
        if spec.get('signed_on') and str(text.signed_on) != str(spec['signed_on']):
            Text.objects.filter(pk=text.pk).update(signed_on=spec['signed_on'])
            changed += 1
        if spec.get('pages') and text.first_published_in_id:
            pmade, pchanged, pmissing = self.pages(text.first_published_in, spec)
            made, changed = made + pmade, changed + pchanged
            missing.extend(pmissing)
        Text.objects.filter(pk=text.pk).update(updated_at=timezone.now())
        self.stdout.write(f'{spec["text"]}: {made} corrections recorded, {changed} articles changed')
        for m in missing:
            self.stdout.write(f'  not applied: {m}')
