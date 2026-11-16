import { useQuery } from '@tanstack/react-query';
import { lazy, Suspense, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { api } from '@/shared/services/api';
import '@/shared/locales/pages';

type Named = { ar: string; fr: string };
/** A topic item that cites an article (HM20 of the hard-moment review): a tool, a journey, a list, a page or a
 *  change, as the server's map of the folders keeps it. `bill`: it speaks of a bill or an announcement, never law. */
export type Citing = {
  topic: string; name: Named; ref: string; kind: 'tools' | 'journeys' | 'checklists' | 'pages' | 'reform'; path: string;
  title: Named; open: boolean; bill: boolean; state: 'draft' | 'stale' | 'checked';
};

/** One request for a whole text: every article's items, from the map built once on the server. */
const useCites = (textPath: string) => useQuery({
  queryKey: ['topic-cites', textPath], staleTime: 600_000, refetchOnWindowFocus: false,
  queryFn: () => api<{ articles: Record<string, Citing[]> }>(`/topics/cites/?text=${encodeURIComponent(textPath)}`),
});

// The articles whose own lines the reader's numbers light (HM29), each with the topic tool whose rules it borrows: shown
// when that tool is (the line lists it), and saying what it says until a person checks it.
const Compute = lazy(() => import('./Compute'));
const COMPUTE: Record<string, { topic: string; ref: string }> = {
  '/ma/loi/65-99/art_53': { topic: 'work', ref: 'tools/end' },
  '/ma/decret/2-04-469/art_1': { topic: 'work', ref: 'tools/end' },
  '/ma/code/cgi/art_73': { topic: 'tax', ref: 'tools/salary' },
};

const SHOWN = 3;
const pick = (n: Named, lang: string) => (lang === 'fr' && n.fr) || n.ar;

/** What answers with an article, in one quiet line of the people's saffron under it: «يجيب عنها: الشغل · شنو كيتسالني؟ ·
 *  الفصل من الشغل…», the topic's name leading its items, the first three and the rest a tap away. A bill's item says it
 *  is a bill, a stale one that it needs a review; a draft says nothing (15 Nov 2026: «عن «قانون»» says once what no
 *  specialist has reviewed). Under the few articles that set a figure, the reader's numbers then light the article's own
 *  lines (HM29). */
export default function Cites({ textPath, eid, path }: { textPath: string; eid: string; path: string }) {
  const { t, i18n } = useTranslation();
  const [all, setAll] = useState(false);
  const items = useCites(textPath).data?.articles[eid] ?? [];
  const compute = COMPUTE[path];
  const tool = compute && items.find((c) => c.topic === compute.topic && c.ref === compute.ref);
  if (!items.length) return null;
  const shown = all ? items : items.slice(0, SHOWN);
  // Grouped by topic, in the order the map gives them (the law's tools first).
  const groups: { topic: string; name: Named; items: Citing[] }[] = [];
  for (const c of shown) {
    const g = groups.find((x) => x.topic === c.topic);
    if (g) g.items.push(c);
    else groups.push({ topic: c.topic, name: c.name, items: [c] });
  }
  const lang = i18n.language;
  const link = 'py-2.5 no-underline hover:underline';
  const dot = <span aria-hidden="true" className="text-muted">{"\u00a0· "}</span>;
  // Words that flow as a sentence: inline links whose padding gives the finger its height, in a line 36 px tall.
  return (
    <>
      <p className="m-0 mt-1 text-meta leading-9" data-noprint>
        <span className="font-semibold text-people">{t('pages:articleUse.cites')}</span>{' '}
        {groups.map((g, gi) => (
          <span key={g.topic}>
            {gi ? dot : null}
            <Link to={`/topics/${g.topic}`} className={`${link} font-medium text-ink-soft`}>{pick(g.name, lang)}</Link>
            {g.items.map((c) => (
              <span key={c.ref}>
                {dot}
                <Link to={c.path} className={`${link} text-people`}>
                  <bdi>{pick(c.title, lang)}</bdi>
                  {c.bill ? <span className="text-ink-soft"> ({t('pages:articleUse.bill')})</span> : null}
                  {c.state === 'stale' ? <span className="text-amended"> ({t('pages:articleUse.stale')})</span> : null}
                </Link>
              </span>
            ))}
          </span>
        ))}
        {items.length > SHOWN ? (
          <>
            {dot}
            <button type="button" onClick={() => setAll(!all)} aria-expanded={all} className="py-2.5 font-medium text-ink-soft hover:text-ink">
              {all ? t('pages:articleUse.fewer') : t('pages:articleUse.more', { count: items.length - SHOWN })}
            </button>
          </>
        ) : null}
      </p>
      {tool ? <Suspense fallback={null}><Compute path={path} eid={eid} tool={tool} /></Suspense> : null}
    </>
  );
}
