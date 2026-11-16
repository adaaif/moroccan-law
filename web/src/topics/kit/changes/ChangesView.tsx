import { Suspense, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import { todayIso } from '@/shared/services/today';
import { pick, refPath, useKitItem, useKitT, type ChangeRow, type ChangeSection, type InfoPage as Info, type Reform } from '../api';
import { KitPage, NextLinks } from '../parts';
import { useProfile } from '../profile';
import { reducedMotion } from '../motion';
import { useRefTitles } from '../share';
import { PAGE_WIDGETS } from '../../registry';
import { BillBand } from './BillBand';
import { Amendments, Chamber } from './Chamber';
import { iso } from './figures';
import { Row } from './Ledger';
import { PressPanel } from './Press';
import './words';
import './changes.css';

/** A page of changes (the bill-page review, V1–V16; redrawn on 15 Nov 2026 as one sheet under the pen). The
 *  whole page is a single sheet of paper, as a bill is: «مشروع» stands across it as on every draft, so no screen of it
 *  can be taken for the law. At its head, the line of the bill's stops; then what Parliament did (a chamber's vote as a
 *  door of seats, or the committee's amendments dot by dot); the story; then the reader picks who they are and reads
 *  their lines as a comparative table — today's figure and the bill's in two columns, the deputies' corrections in pen
 *  with a change bar in the margin; the other readers fold to one line each. On a desk the side column holds the
 *  section's calculator and the calendar of effects. */
export default function ChangesView({ slug, p }: { slug: string; p: Info }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const sections = (p.sections ?? []) as unknown as ChangeSection[];
  const titles = useRefTitles(slug);
  const [mine, setMine] = useProfile(slug);
  const [picked, setPicked] = useState<string | null>(null);
  const [lit, setLit] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const [drawing, setDrawing] = useState(false);
  const top = useRef<HTMLDivElement>(null);
  // C1: a reader who has not answered reads the salaried section, the first.
  const own = sections.find((s) => s.key === picked) ?? sections.find((s) => mine && s.for?.includes(mine)) ?? sections[0];
  if (!own) return null;
  const choose = (s: ChangeSection, scroll: boolean) => {
    setPicked(s.key);
    setLit(null);
    if (s.for?.[0]) setMine(s.for[0]);
    setCount((c) => c + 1);
    if (scroll) top.current?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' });
  };
  const widgets = PAGE_WIDGETS[slug] ?? {};
  const Widget = own.widget ? widgets[own.widget] : undefined;
  const Aside = own.aside ? widgets[own.aside] : undefined;
  const calendar = p.calendar ?? [];
  const litEntry = calendar.find((e) => e.date === lit);
  const inLit = (r: ChangeRow) => Boolean(litEntry && r.from && r.from >= litEntry.date && r.from <= (litEntry.to ?? litEntry.date));
  const others = sections.filter((s) => s !== own);
  const counted = (s: ChangeSection) => t(s.rows.every((r) => r.refused) ? 'changes.proposals' : 'changes.rows', { count: s.rows.length });
  const day = (e: (typeof calendar)[number]) => (e.to ? t('changes.years', { from: e.date.slice(0, 4), to: e.to.slice(0, 4) }) : longDate(e.date, lang));
  const story = Boolean(p.story?.length);
  const side = Aside || calendar.length;

  return (
    <KitPage slug={slug} item={p} title={pick(p.title, lang)} wide story>
      <div className="bl" style={{ '--mark': JSON.stringify(t('sheet.mark')) } as React.CSSProperties}>
        <Watermark />
        {p.bill ? <BillBand slug={slug} bill={p.bill} reform={p.reform} /> : null}
        {p.reform ? <Parliament slug={slug} reform={p.reform} chamber={p.chamber} /> : null}
        {(p.story ?? []).map((name) => { const W = widgets[name]; return W ? <Suspense key={name} fallback={null}><W slug={slug} /></Suspense> : null; })}

        <div className={`bl-grid${side ? ' side' : ''}`}>
          <div className="bl-main">
            {/* The page's lead says how to read the table, so it stands at the table's head: the vote comes first. */}
            {p.lead ? <p className="bl-lead" lang={lang}>{pick(p.lead, lang)}</p> : null}
            <div ref={top} className="lg-tabs" role="group" aria-label={t('changes.ask')}>
              <span className="lg-ask">{t('changes.ask')}</span>
              {sections.map((s) => (
                <button key={s.key} type="button" className="lg-tab" aria-pressed={s === own} onClick={() => choose(s, false)}>{pick(s.chip, lang)}</button>
              ))}
            </div>

            <section className="lg-sec" aria-labelledby="lg-own">
              <h2 id="lg-own" className="lg-sec-h">{pick(own.title, lang)} <small>{counted(own)}</small></h2>
              {own.note ? (
                <p className="lg-note">{iso(pick(own.note, lang))}
                  {own.note_more && own.note_link ? <> <Link to={refPath(slug, own.note_more)}>{pick(own.note_link, lang)}</Link></> : null}</p>
              ) : null}
              {/* On a phone the calendar of effects is a strip of its dates; a date lights its lines and says what starts. */}
              {calendar.length ? (
                <div className="lg-strip">
                  <div role="group" aria-label={t('changes.calendar')}>
                    {calendar.map((e) => (
                      <button key={e.date} type="button" className={e.for.includes(own.key) ? 'mine' : ''} aria-pressed={lit === e.date}
                              onClick={() => setLit(lit === e.date ? null : e.date)}>{day(e)}</button>
                    ))}
                  </div>
                  {litEntry ? <p aria-live="polite">{pick(litEntry.text, lang)}</p> : null}
                </div>
              ) : null}
              <ol className="lg-rows">
                {own.rows.map((r, i) => <Row key={`${own.key}-${i}`} r={r} slug={slug} lit={inLit(r)} titles={titles} report={p.report} hero={i === 0} count={count} />)}
              </ol>
              {Aside && !story ? <div className="lg-phone"><Suspense fallback={null}><Aside slug={slug} /></Suspense></div> : null}
              {/* On a phone the picture folds behind one button: the calculator's bars already say the years (V12). */}
              {Widget ? (
                <div className={`lg-widget${drawing ? ' open' : ''}`}>
                  <button type="button" className="lg-more lg-widget-open" aria-expanded={drawing} onClick={() => setDrawing((d) => !d)}>
                    {drawing ? t('changes.hideDrawing') : t('changes.showDrawing')}
                  </button>
                  <div className="lg-widget-body"><Suspense fallback={null}><Widget slug={slug} /></Suspense></div>
                </div>
              ) : null}
              {own.tool && titles[own.tool] ? (
                <p className="ch-foot"><span>{t('changes.toolAsk')}</span><Link to={refPath(slug, own.tool)}>{pick(titles[own.tool], lang)}</Link></p>
              ) : null}
              {own.more && titles[own.more] ? <p className="ch-foot"><span /><Link to={refPath(slug, own.more)}>{pick(titles[own.more], lang)}</Link></p> : null}
            </section>

            {others.length ? (
              <section className="lg-others" aria-labelledby="lg-others">
                <h2 id="lg-others" className="lg-side-h">{t('changes.others')}</h2>
                <ul>
                  {others.map((s) => (
                    <li key={s.key}>
                      <button type="button" onClick={() => choose(s, true)}>
                        <span><b>{pick(s.title, lang)}</b><span>{iso(pick(s.line, lang))}</span></span>
                        <i>{counted(s)}</i>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
          {side ? (
            <aside className="bl-aside">
              {Aside ? <Suspense fallback={null}><Aside slug={slug} /></Suspense> : null}
              {calendar.length ? (
                <section className="lg-side" aria-labelledby="lg-cal">
                  <h2 id="lg-cal" className="lg-side-h">{t('changes.calendar')}</h2>
                  <ol className="lg-cal">
                    {calendar.map((e) => (
                      <li key={e.date} className={e.for.includes(own.key) ? 'mine' : ''}>
                        <button type="button" aria-pressed={lit === e.date} onClick={() => setLit(lit === e.date ? null : e.date)}>
                          <b>{day(e)}</b>
                          <span>{iso(pick(e.text, lang))}</span>
                        </button>
                      </li>
                    ))}
                  </ol>
                </section>
              ) : null}
            </aside>
          ) : null}
        </div>

        {(p.after ?? []).map((name) => { const W = widgets[name]; return W ? <Suspense key={name} fallback={null}><W slug={slug} /></Suspense> : null; })}
        {p.press ? <PressPanel slug={slug} page={p.press} /> : null}
      </div>
      <NextLinks slug={slug} refs={p.next} titles={titles} />
    </KitPage>
  );
}

/** What Parliament did, newest first (Y13): once a chamber has voted, its vote as a door of seats; on the page of
 *  amendments, the committee's count dot by dot; before any vote, the last two things that happened. Each ends on the
 *  day the page was last checked. */
function Parliament({ slug, reform, chamber }: { slug: string; reform: string; chamber?: Info['chamber'] }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const r = useKitItem<Reform>(slug, 'reform', reform).data;
  if (!r) return null;
  const today = todayIso();
  if (chamber === 'vote' && r.votes?.some((v) => v.seats && v.date <= today)) return <Chamber slug={slug} reform={r} />;
  if (chamber === 'amendments' && r.amendments) return <Amendments reform={r} />;
  const past = r.timeline.filter((e) => e.date <= today).sort((a, b) => b.date.localeCompare(a.date)).slice(0, 2);
  return (
    <div className="ch-updated">
      <span>{t('changes.updated', { date: longDate(r.checked_on, lang) })}</span>
      {past.length ? (
        <ol aria-label={t('changes.since')}>
          {past.map((e) => <li key={e.date}><b>{longDate(e.date, lang)}:</b> {pick(e.text, lang)}</li>)}
        </ol>
      ) : null}
    </div>
  );
}

/** «مشروع» across the sheet, as every draft carries it: once for each screen's height of the sheet, so the word is in
 *  view wherever the reader stops and in any picture taken of the page. Behind the words, unseen by a screen reader
 *  (the running head says it in a sentence). */
function Watermark() {
  const ref = useRef<HTMLDivElement>(null);
  const [n, setN] = useState(2);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setN(Math.max(1, Math.floor((el.offsetHeight - 500) / 900)));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div ref={ref} className="bl-wm" aria-hidden="true">
      {Array.from({ length: n }, (_, i) => <span key={i} style={{ top: `${i * 900 + 1000}px` }} />)}
    </div>
  );
}
