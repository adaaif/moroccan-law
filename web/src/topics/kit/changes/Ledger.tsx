import { Suspense, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import { pick, refPath, useKitT, type ChangeRow, type InfoPage as Info, type Named } from '../api';
import { reducedMotion } from '../motion';
import { sharePicture } from '../tool/picture';
import { PAGE_WIDGETS } from '../../registry';
import { Dots } from './Chamber';
import { iso, local, words } from './figures';

/** A figure as a number to count (V16): «60.000», «45%», «1.700»; null for words. */
function numeric(v: string): { n: number; suffix: string } | null {
  const m = v.match(/^(\d{1,3}(?:\.\d{3})*|\d+)(%?)$/);
  return m ? { n: Number(m[1].replace(/\./g, '')), suffix: m[2] } : null;
}
const show = (n: number, suffix: string, lang: string) => local(`${n >= 1000 ? n.toLocaleString('de-DE') : n}${suffix}`, lang);

/** The first line's figure counts once from today's to the bill's when the reader picks who they are (V16); nothing
 *  moves under reduced motion. */
function useCounted(row: ChangeRow, count: number, lang: string): string {
  const then = words(row.then, lang);
  const [shown, setShown] = useState(then);
  useEffect(() => {
    const a = numeric(words(row.now, 'ar')), b = numeric(words(row.then, 'ar'));
    if (!count || !a || !b || a.suffix !== b.suffix || reducedMotion()) { setShown(then); return; }
    const t0 = performance.now(), ms = 700;
    let raf = 0;
    const step = (tm: number) => {
      const f = Math.min(1, (tm - t0) / ms), e = 1 - Math.pow(1 - f, 3);
      setShown(show(Math.round(a.n + (b.n - a.n) * e), b.suffix, lang));
      if (f < 1) raf = requestAnimationFrame(step); else setShown(then);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [count, then, lang, row.now, row.then]);
  return shown;
}

/** One line of the comparative table a bill is read by (the bill-rows rewrite, 27 Oct 2026; the ledger, 15 Nov):
 *  what the thing is in words, then two figures that stand in the same two columns down the whole section — today's in
 *  grey as the law stands, the bill's in the topic's colour under a bill's dashes — so the eye runs down the bill's
 *  column. Where the deputies wrote over the line, the figure the government filed is struck in the pen's red above the
 *  voted one and a change bar stands in the margin, as in any amended text; an amendment the committee refused is a
 *  proposal, quiet and dotted. Then the reader's own figure (`you`), its date and articles; the detail folded on a
 *  phone. The section's first line is set larger (`hero`) and counts once to its figure (`count`). */
export function Row({ r, slug, lit, titles, report, hero, count = 0 }: {
  r: ChangeRow; slug: string; lit: boolean; titles: Record<string, Named | undefined>; report?: Info['report']; hero?: boolean; count?: number;
}) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const [open, setOpen] = useState(false);
  const You = r.you ? PAGE_WIDGETS[slug]?.[r.you] : undefined;
  const then = words(r.then, lang);
  const shown = useCounted(r, hero ? count : 0, lang);
  const unit = r.unit ? <span className="lg-unit">{pick(r.unit, lang)}</span> : null;
  const label = r.refused ? t('changes.proposed') : r.announced ? t('changes.announced') : r.same ? t('changes.both')
    : r.amended ? t('changes.voted') : t('changes.withBill');
  // A budget line of the year to come has no «today»: the figure as filed, then the voted one.
  const today = !r.same && (r.now || r.new || !r.filed);
  // Words too long to stand side by side on a phone go one above the other.
  const long = [r.now, r.then, r.filed].some((v) => words(v, lang).length > 16);
  const cls = ['lg-row', hero ? 'hero' : '', r.amended ? 'pen' : '', r.refused ? 'no' : '', lit ? 'lit' : '', open ? 'open' : '', long ? 'long' : '', today ? '' : 'one'];
  return (
    <li className={cls.filter(Boolean).join(' ')}>
      <div className="lg-head">
        <h3 className="lg-h">{pick(r.headline, lang)}</h3>
        {r.plain ? <p className="lg-plain">{iso(pick(r.plain, lang))}</p> : null}
      </div>
      {today ? (
        <div className="lg-today">
          <span className="lg-l">{t('changes.today')}</span>
          <span className="lg-v">{r.new || !r.now ? t('changes.nothing') : <>{iso(words(r.now, lang))}{unit}</>}</span>
          {r.now_note ? <span className="lg-n">{iso(pick(r.now_note, lang))}</span> : null}
        </div>
      ) : null}
      <div className="lg-bill">
        {today ? (
          <svg className="lg-arrow" aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 12h15M13 6l6 6-6 6" />
          </svg>
        ) : null}
        <span className="lg-l">{label}</span>
        {/* Struck through where the deputies changed it; left standing where they refused to (the bill's figure holds). */}
        {r.filed ? (
          <span className="lg-filed">
            {r.refused ? <span>{iso(words(r.filed, lang))}</span> : <s>{iso(words(r.filed, lang))}</s>}
            <small>{t(r.refused ? 'changes.inBill' : 'changes.filed')}</small>
          </span>
        ) : null}
        <span className="lg-v">
          <span className={`ch-fig${r.announced || r.same || r.refused ? ' quiet' : ''}`} aria-hidden={hero && shown !== then ? true : undefined}>{hero && shown !== then ? shown : iso(then)}</span>
          {hero && shown !== then ? <span className="ch-sr">{then}</span> : null}
          {unit}
        </span>
        {r.filed_note ? <span className="lg-n">{iso(pick(r.filed_note, lang))}</span> : null}
        {r.then_note ? <span className="lg-n">{iso(pick(r.then_note, lang))}</span> : null}
      </div>
      <Amended r={r} report={report} />
      {You ? <Suspense fallback={null}><You slug={slug} /></Suspense> : null}
      <p className="lg-meta"><When r={r} /><Sources r={r} /><Share r={r} slug={slug} /></p>
      {r.detail ? (
        <>
          <p className="lg-d">{iso(pick(r.detail, lang))}
            {r.more && titles[r.more] ? <> <Link to={refPath(slug, r.more)}>{pick(titles[r.more], lang)}</Link></> : null}</p>
          <button type="button" className="lg-more" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {open ? t('changes.less') : t('changes.details')}
          </button>
        </>
      ) : null}
    </li>
  );
}

/** Who changed the line in Parliament, how the committee voted on it — said by its parts and drawn as its voices — and
 *  its page in the committee's report: written beside the line in the pen that changed it, as a consolidated code's
 *  footnote says which law amended an article. */
function Amended({ r, report }: { r: ChangeRow; report?: Info['report'] }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const a = r.amended ?? r.refused;
  if (!a) return null;
  const by = t(`changes.by.${a.by}`);
  const own = a.by === 'committee' && !r.refused ? 'Committee' : '';
  const said = t(r.refused ? (a.withdrawn ? 'changes.withdrawnBy' : 'changes.refusedBy') : `changes.${r.filed ? 'amendedBy' : 'addedBy'}${own}`, { by });
  // A count is said by its parts: «39 مع، ممتنع واحد», never «0 ضد».
  const vote = a.vote === 'unanimous' ? t('changes.unanimous') : a.vote ? t('changes.counted', {
    parts: [t('changes.votesFor', { count: a.vote[0] }), a.vote[1] ? t('changes.votesAgainst', { count: a.vote[1] }) : '', a.vote[2] ? t('changes.abstained', { count: a.vote[2] }) : '']
      .filter(Boolean).join(lang === 'fr' ? ', ' : '، '),
  }) : '';
  return (
    <p className={`lg-am${r.refused ? ' no' : ''}`}>
      {/* A pen: the line was written over in Parliament. */}
      <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 20h4L19 9l-4-4L4 16z" /><path d="M13.5 6.5l4 4" />
      </svg>
      <span>{said}{vote ? <>{lang === 'fr' ? ' : ' : ': '}{iso(vote)}</> : null}</span>
      {Array.isArray(a.vote) ? <Dots parts={a.vote} /> : null}
      {report && a.page ? <a href={`${report.url}#page=${a.page}`} target="_blank" rel="noreferrer">{t('changes.reportPage', { page: a.page })}</a> : null}
    </p>
  );
}

/** When it would apply: the bill's date, its words, a date a person must confirm, or that it is announced only. */
function When({ r }: { r: ChangeRow }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  if (r.refused) return <span className="lg-when not">{t(r.refused.withdrawn ? 'changes.withdrawn' : 'changes.refused')}</span>;
  if (r.announced) return <span className="lg-when not">{t('changes.announced')}</span>;
  if (r.same) return <span className="lg-when same">{t('changes.same')}</span>;
  const words_ = r.when ? pick(r.when, lang) : r.from ? t('changes.from', { date: longDate(r.from, lang) }) : '';
  return words_ ? <span className={`lg-when${r.check ? ' check' : ''}`}>{words_}</span> : null;
}

/** The code's articles, small, each opening its page (V5: the bill's article is said once, in the lead). */
function Sources({ r }: { r: ChangeRow }) {
  if (!r.cites?.length) return null;
  return (
    <span className="lg-cites">
      {r.cites.map((c) => <Link key={c.path} to={c.path} dir="rtl" lang="ar">{c.label}</Link>)}
    </span>
  );
}

/** One change as a picture to forward (V15): its figure, «عوض» today's, its date, «مشروع، ماشي قانون». */
function Share({ r, slug }: { r: ChangeRow; slug: string }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const now = words(r.now, lang);
  const when = r.announced ? t('changes.announced') : r.when ? pick(r.when, lang) : r.from ? t('changes.from', { date: longDate(r.from, lang) }) : '';
  const go = () => sharePicture({
    dir: lang === 'fr' ? 'ltr' : 'rtl',
    colour: getComputedStyle(document.documentElement).getPropertyValue(`--color-t-${slug}`).trim() || '#8d6e00',
    over: pick(r.headline, lang), value: [words(r.then, lang), r.unit ? pick(r.unit, lang) : ''].filter(Boolean).join(' '),
    lines: [now && !r.same ? t('changes.instead', { now }) : r.new ? t('changes.new') : '', when, t('bill.mark')].filter(Boolean),
    source: (r.cites ?? []).map((c) => c.label).join(' · '), site: t('changes.site'),
  }, `${slug}-change`);
  return (
    <button type="button" className="lg-share" onClick={() => void go()} aria-label={t('changes.share', { what: pick(r.headline, lang) })} title={t('changes.share', { what: pick(r.headline, lang) })}>
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3v12M7 8l5-5 5 5M5 14v6h14v-6" />
      </svg>
    </button>
  );
}
