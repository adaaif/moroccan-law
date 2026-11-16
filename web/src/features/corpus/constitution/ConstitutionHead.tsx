import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ArticleItem, OutlineEntry, TextDetail } from '../corpus.api';
import { AR, DIVISION, longDate } from '../format';
import '@/shared/locales/pages';
import { Story } from './Story';

/** A constitution's page (the constitution review, 25 Oct 2026, C2 and C6): its name in the law's face at its largest
 *  with its year, how it was adopted and by which dahir; the preamble's first sentence at reading size; the titles as a
 *  map. Loaded only for a constitution, after the page's own words. */
export function Opening({ d }: { d: TextDetail }) {
  const { t, i18n } = useTranslation();
  const c = d.constitution!;
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const when = (iso: string) => longDate(iso, i18n.language);
  return (
    <div className="flex flex-col gap-3">
      <h1 lang={lang} className="m-0 flex flex-wrap items-baseline gap-x-4 font-law text-display font-bold leading-[1.1] text-ink">
        <span>{c.name[lang]}</span>
        <span className="text-stamp">{c.year}</span>
      </h1>
      <p className="m-0 max-w-[60ch] text-body leading-relaxed text-ink-soft">
        {c.dahir
          ? t('pages:constitution.adopted', { referendum: when(c.referendum), dahir: c.dahir, signed: when(c.signed) })
          : t('pages:constitution.adoptedUnnumbered', { referendum: when(c.referendum), signed: when(c.signed) })}
      </p>
      {c.story?.[lang] ? (
        <p lang={lang} className="m-0 max-w-[64ch] text-body leading-[1.85] text-ink">
          <Story words={c.story[lang]} path={d.path} />{' '}
          <Link to="/constitution/history" className="whitespace-nowrap font-medium">{t('pages:constitution.history')}</Link>
        </p>
      ) : null}
    </div>
  );
}

/** The preamble's first sentence, the constitution's own opening (2011's says it is part of the constitution), with
 *  the way to the whole of it. */
export function PreambleOpening({ d, articles }: { d: TextDetail; articles: ArticleItem[] }) {
  const { t } = useTranslation();
  const preamble = articles.find((a) => a.eid === 'preamble');
  if (!preamble) return null;
  const first = preamble.body.split(/(?<=[.؛])\s+/)[0];
  const words = first.length > 320 ? `${first.slice(0, 320).replace(/\s+\S*$/, '')}…` : first;
  return (
    <div className="flex flex-col gap-2 border-s-[3px] border-stamp-line ps-5">
      <span {...AR} className="font-law text-lead font-semibold text-stamp">{preamble.label}</span>
      <p {...AR} className="m-0 max-w-[60ch] font-law text-[1.45rem] leading-[1.8] text-ink sm:text-[1.6rem]">{words}</p>
      <Link to={`${d.path}/preamble`} className="inline-flex min-h-11 items-center self-start text-body font-medium">
        {t('pages:constitution.readPreamble')}
      </Link>
    </div>
  );
}

/** The titles as a map (C6): each with its number of articles and a bar for its size, opening its first article. */
export function TitlesMap({ d, outline }: { d: TextDetail; outline: OutlineEntry[] }) {
  const { t } = useTranslation();
  const titles: { full: string; eid: string; count: number }[] = [];
  for (const o of outline) {
    if (o.eid === 'preamble') continue;
    const top = o.heading_path.find((h) => DIVISION.test(h.trim()));
    if (!top) continue;
    const last = titles[titles.length - 1];
    if (last && last.full === top) last.count += 1;
    else titles.push({ full: top, eid: o.eid, count: 1 });
  }
  if (titles.length < 2) return null;
  const most = Math.max(...titles.map((x) => x.count));
  return (
    <nav aria-labelledby="titles-map" className="flex flex-col gap-2.5" data-noprint>
      <h2 id="titles-map" className="m-0 text-body font-semibold text-ink-soft">{t('pages:constitution.titles')}</h2>
      <ol className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-3">
        {titles.map((x) => {
          const colon = x.full.search(/[:：]/);
          const word = colon > 0 ? x.full.slice(0, colon).trim() : x.full;
          const name = colon > 0 ? x.full.slice(colon + 1).trim() : '';
          return (
            <li key={x.eid} className="min-w-0">
              <Link to={`${d.path}/${x.eid}`} title={x.full}
                    className="flex h-full min-h-11 flex-col gap-1.5 rounded-card bg-paper px-3.5 py-3 text-ink no-underline hover:bg-wash hover:text-stamp">
                <span className="text-meta text-ink-soft">
                  <bdi {...AR}>{word}</bdi>{t('corpus.listSep')}{t('pages:constitution.articles', { count: x.count })}
                </span>
                {name ? <span {...AR} className="font-law text-lead font-semibold leading-snug">{name}</span> : null}
                <span aria-hidden="true" className="mt-auto h-1 rounded-full bg-stamp-line" style={{ width: `${Math.max(8, Math.round(100 * x.count / most))}%` }} />
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** Under the standing line: the preamble's opening, then the map of titles. */
export function Body({ d, outline, articles }: { d: TextDetail; outline: OutlineEntry[]; articles: ArticleItem[] }) {
  return (
    <>
      <PreambleOpening d={d} articles={articles} />
      <TitlesMap d={d} outline={outline} />
    </>
  );
}
