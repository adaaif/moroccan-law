import { useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { firstRegister, useWeek, type Week, type WeekSeries, type WeekText } from '@/features/explain/explain.api';
import ShareImage from '@/features/explain/ShareImage';
import { topicColour } from '@/features/topics/colour';
import { TopicIcon } from '@/features/topics/TopicIcon';
import '@/shared/locales/pages';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { Stamp } from './article/Stamp';
import { plainBody, shortName } from './article/message';
import { addressLabel } from './addressLabel';
import { AR, hijriFr, issueNo, longDate } from './format';
import { byKind, PAPER, paperOf, spanOf, units, type PaperClass, type Unit } from './newWeek';
import './new.css';
import { LoadError } from './NotFound';

/**
 * /new, «الجديد»: a week of the Bulletin officiel, Monday to Sunday (R13 of the for-everyone review; drawn again on 1 Nov
 * 2026 from the newest issues, as the page had grown out of date). The weeks of October 2026 were a new government:
 * one dahir naming its 31 members, twenty decrees each giving a minister their powers, thirty-five delegations of
 * signature. Listed one by one, the series drowned what stood alone, and the special section, two texts in three, was
 * only counted. So the week is drawn as its paper: each issue a strip of its pages coloured by what they hold, then every
 * text under the kinds the Bulletin prints them by, a series folded into one pile whose count is said large and whose
 * members are named by what differs, a text that makes rules opening on its first article as printed; the special
 * section's texts too, folded the same way. Nothing is ranked: the order is the Bulletin's, people's words come first
 * only where a person wrote them.
 */
export default function NewPage() {
  const { t } = useTranslation();
  usePageTitle([t('pages:new.title')]);   // «الجديد في الجريدة الرسمية»: the newest week is not always this one (RD23)
  const [params, setParams] = useSearchParams();
  const week = useWeek(params.get('day') ?? '');
  const w = week.data;
  const go = (day: string | null) => { if (day) { setParams({ day }); window.scrollTo({ top: 0 }); } };
  // A week that cannot load says so, with a way to try again (PX14: the page was blank).
  if (!w) return <Page width="wide">{week.isError ? <LoadError error={week.error} retry={() => void week.refetch()} /> : <PageSkeleton />}</Page>;
  const told = w.people.filter((x) => firstRegister(x.told ?? {}, '') !== null);
  const kinds = byKind(w.rest, w.series);
  const special = units(w.special_texts ?? [], w.series);
  return (
    <Page width="wide" className="nw">
      <Front w={w} go={go} />
      {w.issues.length ? (
        <div className="nw-grid">
          <Index w={w} kinds={kinds} special={w.special_texts?.length ?? 0} go={go} />
          <div className="nw-main">
            {/* Only once an editor told a text (PX39 of the where-it-trips review): most weeks it was an apology. */}
            {told.length ? (
              <section aria-labelledby="nw-people" className="nw-told">
                <div className="nw-head">
                  <h2 id="nw-people">{t('pages:week.people')}</h2>
                  <p>{t('pages:week2.peopleLead')}</p>
                </div>
                {told.map((x, i) => <Story key={x.path} x={x} lead={i === 0} />)}
              </section>
            ) : null}
            {kinds.map((g) => (
              <section key={g.kind} id={`nw-${g.kind}`} aria-labelledby={`nw-h-${g.kind}`} className="nw-kind">
                <h2 id={`nw-h-${g.kind}`}><span>{t(`pages:week2.groups.${g.kind}`)}</span><span className="n">{g.count}</span></h2>
                <ul className="nw-units">{g.units.map((u) => <UnitRow key={u.kind === 'text' ? u.text.path : u.id} u={u} />)}</ul>
              </section>
            ))}
            {special.length ? (
              <section id="nw-special" aria-labelledby="nw-h-special" className="nw-kind nw-special">
                <h2 id="nw-h-special"><span>{t('pages:new3.special')}</span><span className="n">{w.special_texts.length}</span></h2>
                <p className="nw-lead">{t('pages:new3.specialLead')}</p>
                <ul className="nw-units">{special.map((u) => <UnitRow key={u.kind === 'text' ? u.text.path : u.id} u={u} quiet />)}</ul>
              </section>
            ) : null}
          </div>
        </div>
      ) : <p className="nw-none">{t('pages:week2.empty')}</p>}
      <nav className="nw-foot" aria-label={t('pages:week.nav')}>
        <button type="button" className="nw-step" disabled={!w.prev} onClick={() => go(w.prev)}>‹ {t('pages:week.prev')}</button>
        <Link to="/bo">{t('pages:new.allIssues')}</Link>
        <button type="button" className="nw-step" disabled={!w.next} onClick={() => go(w.next)}>{t('pages:week.next')} ›</button>
      </nav>
    </Page>
  );
}

const lang = (l: string) => (l === 'fr' ? 'fr' : 'ar');
const at = (day: string) => new Date(`${day}T00:00:00Z`);

/** The week's Hijri days, Monday to Sunday («14 – 20 جمادى الأولى 1448»), counted from the day the Bulletin printed on
 *  its first issue; where the week crosses into another month, which the count cannot know, the issues' days alone. */
function hijriSpan(w: Week): string {
  const issues = [...w.issues].sort((a, b) => a.date.localeCompare(b.date)).filter((i) => i.hijri);
  if (!issues.length) return '';
  const [day, ...rest] = issues[0].hijri.split(' ');
  const d = Number(day);
  const from = d - (at(issues[0].date).getTime() - at(w.from).getTime()) / 86_400_000;
  const to = from + 6;
  // The days read left to right in either language, as the page ranges do.
  if (Number.isInteger(d) && from >= 1 && to <= 29) return `\u2066${from}–${to}\u2069 ${rest.join(' ')}`;
  const last = issues[issues.length - 1].hijri;
  return last === issues[0].hijri ? last : `${issues[0].hijri} – ${last}`;
}

/** The week's head: the Bulletin's name, the week's days large, the step to the weeks around it, its paper. */
function Front({ w, go }: { w: Week; go: (day: string | null) => void }) {
  const { t, i18n } = useTranslation();
  const l = lang(i18n.language);
  const locale = l === 'fr' ? 'fr-MA' : 'ar-MA';
  const span = new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).formatRange(at(w.from), at(w.to));
  const hijri = hijriSpan(w);
  const pages = w.issues.reduce((n, i) => n + (i.pages ?? 0), 0);
  return (
    <header className="nw-front">
      <div className="nw-title">
        <h1>
          <span className="of">{t('pages:homeWeek.name')}</span>
          <span className="when">{span}</span>
        </h1>
        <Weeks w={w} go={go} />
      </div>
      {hijri ? <p className="nw-hijri">{l === 'fr' ? hijriFr(hijri) : <bdi lang="ar">{hijri}</bdi>}</p> : null}
      {w.issues.length ? (
        <>
          <p className="nw-facts">
            <span>{t('pages:week.issues', { count: w.issues.length })}</span>
            {pages ? <span>{t('pages:new3.pages', { count: pages })}</span> : null}
            <span>{t('pages:week2.general', { count: w.rest.length + w.people.length })}</span>
            {w.special_texts?.length ? <span>{t('pages:new3.specialCount', { count: w.special_texts.length })}</span> : null}
          </p>
          <Paper w={w} />
        </>
      ) : null}
    </header>
  );
}

/** The weeks around this one as bars, oldest on the left like any chart read by Moroccans (the chart rule of 1 Nov 2026), each
 *  as tall as the pages it printed; this week in the law's violet; a tap goes to it. The arrows step a week. */
function Weeks({ w, go }: { w: Week; go: (day: string | null) => void }) {
  const { t, i18n } = useTranslation();
  const l = lang(i18n.language);
  const most = Math.max(1, ...(w.weeks ?? []).map((x) => x.pages));
  const fmt = new Intl.DateTimeFormat(l === 'fr' ? 'fr-MA' : 'ar-MA', { day: 'numeric', month: 'short', timeZone: 'UTC' });
  const end = (from: string) => new Date(at(from).getTime() + 6 * 86_400_000);
  return (
    <nav className="nw-weeks" dir="ltr" aria-label={t('pages:week.nav')}>
      <button type="button" className="nw-arrow" disabled={!w.prev} onClick={() => go(w.prev)} aria-label={t('pages:week.prev')} title={t('pages:week.prev')}>
        <Arrow />
      </button>
      <div className="bars">
      <ol>
        {(w.weeks ?? []).map((x) => {
          const here = x.from === w.from;
          const label = `${fmt.formatRange(at(x.from), end(x.from))}: ${t('pages:week.issues', { count: x.issues })}${x.pages ? `، ${t('pages:new3.pages', { count: x.pages })}` : ''}`;
          return (
            <li key={x.from}>
              <button type="button" className={here ? 'here' : ''} aria-current={here ? 'date' : undefined} aria-label={label} title={label}
                      disabled={!x.issues && !here} onClick={() => go(x.from)}>
                <span style={{ height: `${x.pages ? Math.max(8, Math.round((x.pages / most) * 100)) : 4}%` }} />
              </button>
            </li>
          );
        })}
      </ol>
      {w.weeks?.length ? (
        <p className="ends" aria-hidden="true">
          <span>{fmt.format(at(w.weeks[0].from))}</span><span>{fmt.format(at(w.weeks[w.weeks.length - 1].from))}</span>
        </p>
      ) : null}
      </div>
      <button type="button" className="nw-arrow" disabled={!w.next} onClick={() => go(w.next)} aria-label={t('pages:week.next')} title={t('pages:week.next')}>
        <Arrow next />
      </button>
    </nav>
  );
}

const Arrow = ({ next }: { next?: boolean }) => (
  // Left to right like the weeks between them: the week before on the left.
  <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
       strokeLinecap="round" strokeLinejoin="round" style={next ? { transform: 'scaleX(-1)' } : undefined}>
    <path d="m15 6-6 6 6 6" />
  </svg>
);

/** The week's paper: each issue a strip of its pages, the first on the left as a reader of charts expects (the chart
 *  rule of 1 Nov 2026), each run of pages coloured by what starts on it; the issue's number and day above, its pages under. */
function Paper({ w }: { w: Week }) {
  const { t, i18n } = useTranslation();
  const l = lang(i18n.language);
  const all = [...w.people, ...w.rest, ...(w.special_texts ?? [])];
  const issues = [...w.issues].sort((a, b) => a.date.localeCompare(b.date) || a.key.localeCompare(b.key));
  const used = new Set<PaperClass>();
  const strips = issues.map((i) => {
    const runs = paperOf(i, all);
    runs.forEach((r) => used.add(r.cls));
    return { i, runs };
  });
  const weekday = (day: string) => new Intl.DateTimeFormat(l === 'fr' ? 'fr-MA' : 'ar-MA', { weekday: 'long', day: 'numeric', timeZone: 'UTC' }).format(at(day));
  return (
    <figure className="nw-paper-fig">
      <ol className="nw-paper" dir="ltr" aria-label={t('pages:new3.paperLabel')}>
        {strips.map(({ i, runs }) => (
          <li key={i.key} style={{ flexGrow: i.pages ?? 1 } as CSSProperties}>
            <Link to={`/bo/${i.edition}/${i.key}`} className="nw-issue"
                  aria-label={`${t('stamp.issue', { number: issueNo(i, t) })}، ${longDate(i.date, l)}${i.pages ? `، ${t('pages:new3.pages', { count: i.pages })}` : ''}`}>
              <span className="top" dir={l === 'fr' ? 'ltr' : 'rtl'}>
                <b>{issueNo(i, t)}</b>
                <span>{weekday(i.date)}</span>
              </span>
              <span className="bar" aria-hidden="true">
                {runs.map((r) => (
                  <span key={r.from} className={`seg ${r.cls}`} style={{ flexGrow: r.to - r.from + 1 }}
                        title={`${t(`pages:new3.paper.${r.cls}`)}: ${r.from === r.to ? r.from : `${r.from}–${r.to}`}`} />
                ))}
              </span>
              {i.pages ? (
                <span className="pp" dir={l === 'fr' ? 'ltr' : 'rtl'}>
                  {t('pages:new3.pages', { count: i.pages })}
                  {i.first_page ? <span className="range" dir="ltr">{i.first_page}–{i.first_page + i.pages - 1}</span> : null}
                </span>
              ) : null}
            </Link>
          </li>
        ))}
      </ol>
      <figcaption className="nw-legend">
        {PAPER.filter((c) => used.has(c)).map((c) => (
          <span key={c}><i className={`seg ${c}`} aria-hidden="true" />{t(`pages:new3.paper.${c}`)}</span>
        ))}
      </figcaption>
    </figure>
  );
}

/** What the week holds by kind, each a way down the page; the topics its texts touch; the weeks around it. On a desk it
 *  stays beside the texts. */
function Index({ w, kinds, special, go }: { w: Week; kinds: ReturnType<typeof byKind>; special: number; go: (day: string | null) => void }) {
  const { t, i18n } = useTranslation();
  const l = lang(i18n.language);
  const all = [...w.people, ...w.rest];
  const topics = [...new Map(all.filter((x) => x.topic).map((x) => [x.topic!.slug, x.topic!])).values()];
  if (!kinds.length && !special) return null;
  return (
    <aside className="nw-index" aria-labelledby="nw-index-h">
      <h2 id="nw-index-h">{t('pages:new3.index')}</h2>
      <ul>
        {kinds.map((g) => (
          <li key={g.kind}><a href={`#nw-${g.kind}`}><span>{t(`pages:week2.groups.${g.kind}`)}</span><b>{g.count}</b></a></li>
        ))}
        {special ? <li><a href="#nw-special"><span>{t('pages:new3.special')}</span><b>{special}</b></a></li> : null}
      </ul>
      {topics.length ? (
        <div className="nw-topics">
          <p>{t('pages:week2.topics')}</p>
          {topics.map((x) => (
            <Link key={x.slug} to={`/topics/${x.slug}`} className="nw-topic" style={topicColour(x.slug)} lang={l}>
              <TopicIcon slug={x.slug} size={16} />{x.name[l]}
            </Link>
          ))}
        </div>
      ) : null}
      <div className="nw-aside-steps">
        <button type="button" className="nw-step" disabled={!w.prev} onClick={() => go(w.prev)}>‹ {t('pages:week.prev')}</button>
        <Link to="/bo">{t('pages:new.allIssues')}</Link>
      </div>
    </aside>
  );
}

function UnitRow({ u, quiet }: { u: Unit; quiet?: boolean }) {
  return u.kind === 'text' ? <TextRow x={u.text} quiet={quiet} /> : <Pile series={u.series} texts={u.texts} />;
}

/** Where the words were printed, as a source mark: an issue and a page, or a run of pages. */
function Source({ texts }: { texts: WeekText[] }) {
  const { t } = useTranslation();
  const s = spanOf(texts);
  const issues = s.issues.map((k) => issueNo(texts.find((x) => x.issue.key === k)!.issue, t)).join(t('corpus.listSep'));
  if (s.from == null) return <Stamp issue={issues} />;
  return s.from === s.to ? <Stamp issue={issues} page={s.from} /> : (
    <span data-stamp className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-wash px-2.5 py-1 text-meta font-medium leading-tight text-stamp">
      {t('stamp.issue', { number: issues })} · {t('pages:new3.pageRange', { range: `\u2066${s.from}–${s.to}\u2069` })}
    </span>
  );
}

/** A text alone: its title as printed (said short), its first article's opening when it makes rules, what it changes
 *  and applies, where it was printed. */
function TextRow({ x, quiet }: { x: WeekText; quiet?: boolean }) {
  const { t, i18n } = useTranslation();
  const l = lang(i18n.language);
  const fr = l === 'fr' && x.title_fr;
  return (
    <li className={`nw-text ${quiet ? 'quiet' : ''}`} style={x.topic ? topicColour(x.topic.slug) : undefined}>
      <Link to={x.path} className="t" dir={fr ? 'ltr' : 'rtl'} lang={fr ? 'fr' : 'ar'}>{shortName(fr ? x.title_fr : x.title, quiet ? 160 : 220)}</Link>
      {x.first ? <FirstWords first={x.first} path={x.path} /> : null}
      <div className="sub">
        <Stamp issue={issueNo(x.issue, t)} page={x.page} />
        {x.changes.length ? <Related label={t('pages:week.changes')} list={x.changes} /> : null}
        {x.applies.length ? <Related label={t('pages:new3.applies')} list={x.applies} /> : null}
        {x.topic ? <Link to={`/topics/${x.topic.slug}`} className="nw-topic" lang={l}><TopicIcon slug={x.topic.slug} size={14} />{x.topic.name[l]}</Link> : null}
      </div>
    </li>
  );
}

function Related({ label, list }: { label: string; list: WeekText['changes'] }) {
  const { t, i18n } = useTranslation();
  const l = lang(i18n.language);
  return (
    // A text the site holds without a title yet («/ma/arrete/1617-22») is said by its kind and number, never an empty link.
    <span className="rel">{label} {list.map((c, k) => (
      <span key={c.path}>{k ? t('corpus.listSep') : ''}<Link to={c.path} lang={l}>{shortName(c.name[l] || c.name.ar || addressLabel(c.path, l), 70)}</Link></span>
    ))}</span>
  );
}

/** The law said by itself: the first article's label and opening words as printed; a table the page prints (a dahir's
 *  members and their offices) as its rows, each name led by dots to its office, the first few. */
function FirstWords({ first, path }: { first: { label: string; body: string }; path: string }) {
  const { t } = useTranslation();
  const lines = first.body.split('\n');
  const rows = lines.filter((s) => /^\|.*\|\s*$/.test(s.trim())).map((s) => s.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim()));
  const lead = plainBody(lines.filter((s) => !s.trim().startsWith('|')).join('\n'));
  const shown = rows.slice(0, 4);
  return (
    <blockquote className="nw-first" {...AR}>
      <span className="lbl">{first.label}</span>
      {lead ? <span className={`body ${rows.length ? 'short' : ''}`}>{lead}</span> : null}
      {shown.length ? (
        <span className="rows">
          {shown.map((r, i) => <span key={i} className="row"><span>{r[0]}</span><span className="dots" aria-hidden="true" /><span>{r.slice(1).join(' ')}</span></span>)}
          <Link to={path} className="more">{t('pages:new3.readAll')}</Link>
        </span>
      ) : null}
    </blockquote>
  );
}

const FOLDED = 5;

/** A series: one pile, its count large, its shared words once, each member named by what differs and kept as a link;
 *  folded after the first five. Signed by several hands («بتفويض الإمضاء»), it says who and how many first. */
function Pile({ series, texts }: { series: WeekSeries; texts: WeekText[] }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const fold = texts.length > FOLDED + 1;
  const shown = fold && !open ? texts.slice(0, FOLDED) : texts;
  // Members whose titles differ only by their number are named by it; where some share their words (two «جامعة خاصة»,
  // four «كلية خاصة»), each stands on its line with its number, as a table of contents sets a page.
  const kinds = new Set(texts.map((x) => x.part)).size;
  const sameWords = kinds === 1;
  const long = sameWords ? false : kinds < texts.length || texts.reduce((n, x) => n + x.part.length, 0) / texts.length > 34;
  const id = `pile-${texts[0].path.replace(/\W+/g, '-')}`;
  return (
    <li className={`nw-pile ${texts.length >= 5 ? 'deep' : ''}`}>
      <div className="count" aria-hidden="true">
        <b>{texts.length}</b>
        <span>{t('pages:new3.texts', { count: texts.length })}</span>
      </div>
      <div className="body">
        <h3 className="h" {...AR}><span className="sr-only">{t('pages:new3.texts', { count: texts.length })}: </span>{series.head}{texts.some((x) => x.part && !series.issuers.some((s) => s.name === x.part)) ? ' …' : ''}</h3>
        {series.issuers.length > 1 ? (
          <p className="who">
            {series.issuers.map((s) => (
              <span key={s.name} {...AR}>{s.name || t('pages:new3.noIssuer')} <b>{s.count}</b></span>
            ))}
          </p>
        ) : null}
        <ol id={id} className={`members ${long || series.issuers.length > 1 ? 'list' : 'run'}`} {...AR}>
          {shown.map((x, i) => (
            <li key={x.path} style={{ '--i': Math.max(0, i - FOLDED) } as CSSProperties} className={i >= FOLDED ? 'late' : undefined}>
              <Link to={x.path}>{sameWords || !x.part ? t('pages:new3.numbered', { number: x.number }) : x.part}</Link>
              {/* «138/ق/2026», a decision of the Competition Council, reads as the Arabic prints it. */}
              {!sameWords && x.part && x.number ? <span className="no" dir={/[\u0600-\u06FF]/.test(x.number) ? 'rtl' : 'ltr'}>{x.number}</span> : null}
            </li>
          ))}
        </ol>
        <div className="foot">
          {fold ? (
            <button type="button" className="unfold" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
              {open ? t('pages:new3.fold') : t('pages:new3.unfold', { count: texts.length - FOLDED })}
            </button>
          ) : null}
          <Source texts={texts} />
        </div>
      </div>
    </li>
  );
}

/** A text an editor told: its topic, their headline, their plain words, where the law was printed, the way to it. */
function Story({ x, lead }: { x: WeekText; lead: boolean }) {
  const { t, i18n } = useTranslation();
  const l = lang(i18n.language);
  const register = firstRegister(x.told ?? {}, i18n.language);
  const e = register ? x.told?.[register] : null;
  if (!e) return null;
  return (
    <article id={`told${x.path.replace(/\//g, '-')}`} className={`nw-story ${lead ? 'lead' : ''}`} style={x.topic ? topicColour(x.topic.slug) : undefined}>
      {x.topic ? (
        <Link to={`/topics/${x.topic.slug}`} lang={l} className="nw-topic self-start"><TopicIcon slug={x.topic.slug} size={16} />{x.topic.name[l]}</Link>
      ) : null}
      <h3 className="h" dir="auto"><Link to={x.path}>{e.headline}</Link></h3>
      <p className="body" dir={register === 'fr' ? 'ltr' : 'rtl'}>{e.body}</p>
      <div className="nw-acts">
        <Stamp issue={issueNo(x.issue, t)} page={x.page} />
        <Link to={x.path} className="read">{t('pages:week.read')}</Link>
        <Link to={`/explain${x.path}`} className="more">{t('pages:explain.more')}</Link>
        <span className="share"><ShareImage path={x.path} register={register ?? undefined} /></span>
      </div>
      <p className="nw-note">{t('pages:explain.notLaw')}</p>
    </article>
  );
}
