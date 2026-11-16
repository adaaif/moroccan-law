import { useState } from 'react';
import { Button, PageSkeleton } from '@/shared/components/ui';
import { pick, refPath, useKitItem, type InfoPage, type Named } from '../kit/api';
import { KitPage } from '../kit/parts';
import { SourceFold } from '../kit/tool/parts';
import { find } from './rules/illness';
import { articleLabel, useHealthT } from './strings';

type Row = [string, string, string];

/** «واش المرض ديالي فاللائحة؟» (S19 of the health review): order 2518-05's 41 long illnesses, found by the list's
 *  own words in either language or by people's («السكر», «الكلاوي»), read from the topic's page (pages/illnesses) so a
 *  person checks the list like everything else; then the costly treatments and what being on the list gives. */
export default function IllnessPage({ slug }: { slug: string }) {
  const { t, i18n } = useHealthT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const page = useKitItem<InfoPage>(slug, 'pages', 'illnesses').data;
  const [q, setQ] = useState('');
  if (!page) return <KitPage slug={slug} title={t('illness.title')} lead={t('illness.lead')}><PageSkeleton /></KitPage>;
  const sections = (page.sections ?? []) as unknown as { title: Named; table?: { rows: Row[] }; facts?: { text: Named }[] }[];
  const rows = sections.find((x) => x.table)?.table?.rows ?? [];
  const costly = sections.find((x) => x.facts);
  const hits = find(rows, q);
  return (
    <KitPage slug={slug} title={t('illness.title')} lead={t('illness.lead')}>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('illness.search')}</span>
          <input type="search" dir="auto" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('illness.placeholder')}
                 className="h-12 rounded-control border border-field bg-sheet px-3 text-body" />
        </label>
        <p className="m-0 text-meta text-ink-soft" aria-live="polite">{q ? t('illness.found', { count: hits.length }) : null}</p>
        <ol className="m-0 flex list-none flex-col p-0">
          {(q && hits.length ? hits : rows).map(([n, ar, fr]) => (
            <li key={n} className="flex items-baseline gap-3 border-t border-rule py-2.5 first:border-t-0">
              <span className="shrink-0 text-meta text-ink-soft tabular-nums" style={{ width: 28 }}>{n}</span>
              <span className="flex flex-col">
                <span lang="ar" dir="rtl" className="text-body">{ar}</span>
                <span lang="fr" dir="ltr" className="text-meta text-ink-soft">{fr}</span>
              </span>
            </li>
          ))}
        </ol>
        <p className="m-0 text-meta text-ink-soft">{t('illness.printed')}</p>
      </section>
      {costly ? (
        <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-5 sm:px-7">
          <h2 className="m-0 text-lead font-semibold">{t('illness.costly')}</h2>
          {(costly.facts ?? []).map((f, i) => <p key={i} className="m-0 text-body">{pick(f.text, lang)}</p>)}
        </section>
      ) : null}
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-lead font-semibold">{t('illness.what')}</h2>
        <p className="m-0 text-body">{t('illness.gives')}</p>
        <SourceFold paths={['/ma/arrete/2518-05/annex', '/ma/loi/65-00/art_9', '/ma/decret/2-05-733/art_10']} label={articleLabel} />
        <div className="flex flex-wrap gap-2"><Button to={refPath(slug, 'journeys/long-illness')}>{t('illness.toJourney')}</Button></div>
      </section>
    </KitPage>
  );
}
