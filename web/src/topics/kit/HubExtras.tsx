import { Suspense, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import { Sheet } from '@/shared/components/Sheet';
import { INSTRUMENTS, KEEP } from '../registry';
import { pick, refPath, useKitT, type Door, type Module, type ProfileFact, type Urgent } from './api';
import { KitIcon } from './icons';
import { useProfile } from './profile';
import { readDue, readProgress } from './progress';
import { daysUntil } from './tool/days';
import { todayIso } from '@/shared/services/today';
import { Sign } from './Sign';
import { Stops } from './parts';

const SHOWN = 6;
/** Up to nine doors show whole: a fold that hides three doors or fewer saves little and hides a door. */
const FOLD_AFTER = 9;

/** The tools a topic draws as instruments, from its registry; the rest are listed. */
const instrumentKeys = (slug: string) => Object.keys(INSTRUMENTS[slug]?.keys ?? {});

/** What a topic's folder adds to its page (F3 of the family plan; T1–T6 of the road tools review; A4–A13 of
 *  the road-signposted review). The first screen holds the moment the reader came with: the emergency in a red band with its first
 *  acts, one question («شنو وقع ليك؟») with the reader's own answer beside it as a control, the figures that answer
 *  makes theirs, the doors as rows led by their sign; then the instruments (on a phone; a desk holds them in its side
 *  column), the other tools, the learning path drawn as a road, and what changes next by its date. The answer orders
 *  the doors; it hides nothing. Each thing once: a door the band or a journey reaches is not listed again. */
export default function HubExtras({ slug, module }: { slug: string; module: Module }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const [mine, setMine] = useProfile(slug);
  const [all, setAll] = useState(false);
  const profile = module.profile;
  const fits = (d: Door) => !profile || !mine || !d.for || d.for.includes(mine);
  // The reader's answer leads with its own door (its `first`), then the doors that are theirs, then the rest.
  const chosen = profile?.options.find((o) => o.key === mine);
  // A door in the reader's own words when the answer has them (PX38 of the where-it-trips review: a landlord read «مول الدار
  // بغا يخرجني» first).
  const title = (d: Door) => pick((mine && d.title_by?.[mine]) || d.title, lang);
  // A discreet door (protection) keeps its last row whatever the answer (G2 of the family-papers review).
  const rank = (d: Door) => (d.discreet ? -1 : (d.key === chosen?.first ? 2 : 0) + (fits(d) ? 1 : 0));
  const ordered = <T extends Door>(list: T[]) => [...list].sort((a, b) => rank(b) - rank(a));
  // A door of one answer's own (E2 of the work-counted review: the domestic worker's, the employer's) is listed only for it.
  const doors = ordered(module.events.filter((d) => d.listed !== false && (!d.own || (!!mine && !!d.for?.includes(mine)))));
  // A topic counted in numbers draws every door on a punch card (E1), its number the reader's answer's own.
  const cards = doors.some((d) => d.mark);
  const markOf = (d: Door) => (d.mark ? (mine && d.mark.by?.[mine]) || d.mark : null);
  // A fold that would hide two doors or fewer saves no room and hides a door (G2 of the family-papers review: the
  // protection door sat behind «حالتان أخريان»).
  const row = (d: Door, i: number) => {
    // In stages, a door the reader's answer does not concern is one quiet line (the consumer's 21 doors: the reason
    // repeated on each ran the page to 5,800 px); the reason stays for a screen reader.
    if (module.stages?.length && !fits(d)) {
      return (
        <li key={d.key} className={`border-rule ${i ? 'border-t' : ''} ${i === 1 ? 'lg:border-t-0' : ''}`}>
          <Link to={refPath(slug, d.to ?? `tools/${d.key}`)} className="flex min-h-12 items-center gap-3 py-2 text-ink-soft no-underline hover:text-stamp">
            <span lang={lang} className="flex min-w-0 flex-1 flex-col text-body leading-snug">
              <span>{title(d)}{d.not ? null : <span className="sr-only"> ({t('profile.faded')})</span>}</span>
              {/* The law's own reason the door is not the reader's (the land review, M4). */}
              {d.not ? <span className="text-meta">{pick(d.not, lang)}</span> : null}
            </span>
            <span aria-hidden="true" className="text-lead">›</span>
          </Link>
        </li>
      );
    }
    const progress = d.to ? readProgress(slug, d.to) : null;
    // The days left before its next limit, once the reader gave the journey its day (G8).
    const due = d.to ? readDue(slug, d.to) : null;
    const left = due ? daysUntil(due.last) : -1;
    return (
      <li key={d.key} className={`border-rule ${i ? 'border-t' : ''} ${i === 1 ? 'lg:border-t-0' : ''}`}>
        <Link to={refPath(slug, d.to ?? `tools/${d.key}`)}
              className={`flex min-h-16 items-center gap-3 py-2.5 text-ink no-underline hover:text-stamp ${fits(d) ? '' : 'opacity-70'}`}>
          <Sign kind={d.sign} icon={d.icon} size={38} mark={markOf(d)} card={cards} plot={d.plot}
                shape={module.marks === 'tag' ? 'tag' : module.marks === 'plot' ? 'plot' : module.marks === 'stamp' ? 'stamp' : module.marks === 'vignette' ? 'vignette' : module.marks === 'card' ? 'card' : module.marks === 'cachet' ? 'cachet' : module.marks === 'file' ? 'file' : module.marks === 'bubble' ? 'bubble' : module.marks === 'receipt' ? 'receipt' : 'punch'} />
          <span className="flex min-w-0 flex-1 flex-col">
            <span lang={lang} className="text-body font-semibold leading-snug">{title(d)}</span>
            {d.lead ? <span lang={lang} className="text-meta leading-snug text-ink-soft">{pick(d.lead, lang)}</span> : null}
            {progress?.done ? <span className="text-meta font-medium text-in-force">{t('progress', { done: progress.done, total: progress.total })}</span> : null}
            {left >= 0 ? <span className="text-meta font-semibold text-[color:var(--t)]">{left === 0 ? t('journey.lastDay') : t('journey.left', { days: t('days', { count: left }) })}</span> : null}
            {fits(d) ? null : <span lang={lang} className="text-meta text-ink-soft">{d.not ? pick(d.not, lang) : t('profile.faded')}</span>}
          </span>
          <span aria-hidden="true" className="text-lead text-ink-soft">›</span>
        </Link>
      </li>
    );
  };
  const folds = !module.stages?.length && doors.length > FOLD_AFTER;
  const visible = all || !folds ? doors : doors.slice(0, SHOWN);
  const learnt = new Set((module.learn ?? []).map((l) => l.to));
  const instruments = instrumentKeys(slug);
  // What the topic keeps for a reader without a network (A17), once the page is idle.
  useEffect(() => {
    const run = KEEP[slug];
    if (!run) return;
    const idle = window.requestIdleCallback ?? ((f: () => void) => window.setTimeout(f, 1500));
    idle(() => void run(module).catch(() => undefined));
  }, [slug, module]);
  const tools = ordered(module.tools.filter((d) => !d.urgent_only && d.listed !== false && d.place !== 'whole'
    && !learnt.has(`tools/${d.key}`) && !instruments.includes(d.key)));
  return (
    <>
      {module.urgent ? <Band slug={slug} urgent={module.urgent} mine={mine} folded={!!mine && !!module.urgent.for && !module.urgent.for.includes(mine)} /> : null}

      {doors.length ? (
        <section className="flex flex-col gap-3" aria-labelledby="doors">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
            <h2 id="doors" lang={lang} className="m-0 text-h3 font-bold">{module.doors_title ? pick(module.doors_title, lang) : t('doors')}</h2>
            {profile ? <Me profile={profile} mine={mine} setMine={setMine} /> : null}
          </div>
          {chosen?.facts?.length ? <Facts facts={chosen.facts} /> : chosen ? (
            <p lang={lang} className="m-0 text-body text-ink-soft">{pick(chosen.law, lang)}</p>
          ) : null}
          {module.stages?.length ? (
            // The doors in the stages they stand in (the consumer-receipt review: the life of a purchase), all in
            // view; within a stage the reader's answer orders them; another topic's doors as links at the end.
            <div className="flex flex-col gap-5">
              {/* The stage that holds the answer's own door comes first; the others keep the purchase's order. */}
              {[...module.stages].sort((x, y) => Number(y.doors.includes(chosen?.first ?? '')) - Number(x.doors.includes(chosen?.first ?? ''))).map((stage) => {
                const here = doors.filter((d) => stage.doors.includes(d.key));
                if (!here.length) return null;
                return (
                  <section key={stage.key} aria-labelledby={`stage-${stage.key}`} className="flex flex-col gap-2">
                    <h3 id={`stage-${stage.key}`} lang={lang} className="m-0 text-lead font-semibold">{pick(stage.title, lang)}</h3>
                    {stage.links ? (
                      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
                        {here.map((d) => (
                          <li key={d.key}>
                            <Link to={refPath(slug, d.to ?? `tools/${d.key}`)} lang={lang}
                                  className="inline-flex min-h-11 items-center gap-2 rounded-full border border-rule bg-sheet px-4 text-body text-ink no-underline hover:border-stamp hover:text-stamp">
                              {d.icon ? <KitIcon name={d.icon} size={20} /> : null}{title(d)}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    ) : <ul className="m-0 grid list-none gap-x-6 rounded-card bg-sheet px-4 py-1 sm:px-5 lg:grid-cols-2">{here.map(row)}</ul>}
                  </section>
                );
              })}
            </div>
          ) : (
            <ul className="m-0 grid list-none gap-x-6 rounded-card bg-sheet px-4 py-1 sm:px-5 lg:grid-cols-2">
              {visible.map(row)}
            </ul>
          )}
          {folds ? (
            <button type="button" aria-expanded={all} onClick={() => setAll(!all)} className="min-h-11 self-start text-body font-medium text-stamp">
              {all ? t('fewer') : t('moreDoors', { count: doors.length - SHOWN })}
            </button>
          ) : null}
        </section>
      ) : null}

      {/* A phone holds the instruments here; a desk in its side column (A12). */}
      <div className="lg:hidden"><HubInstruments slug={slug} module={module} /></div>

      {/* What people believe, after the instruments that answer their questions (E17 of the work-counted review). */}
      {module.beliefs?.length && !module.reform ? <Beliefs slug={slug} beliefs={module.beliefs} /> : null}

      {tools.length ? (
        <section className="flex flex-col gap-2" aria-labelledby="tools">
          <div className="flex flex-col">
            <h2 id="tools" className="m-0 text-lead font-semibold">{instruments.length ? t('moreTools') : t('tools')}</h2>
            {instruments.length ? null : <p className="m-0 text-meta text-ink-soft">{t('toolsLead')}</p>}
          </div>
          {/* A grid, never a strip that scrolls sideways (A2): every tool in view on a desk. */}
          <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-3">
            {tools.map((d) => (
              // A tool alone in the grid spans its row (UX16 of the phone-test review: the family's one card sat
              // at half the width beside nothing); a style, the stylesheet has no room.
              <li key={d.key} style={tools.length === 1 ? { gridColumn: '1 / -1' } : undefined}>
                <Link to={refPath(slug, d.to ?? `tools/${d.key}`)}
                      className="flex h-full min-h-24 flex-col gap-1.5 rounded-card bg-sheet px-3 py-3 text-ink no-underline hover:text-stamp">
                  <span className="text-[color:var(--t)]"><KitIcon name={d.icon ?? 'numbers'} size={24} /></span>
                  <span lang={lang} className="text-body font-semibold leading-snug">{title(d)}</span>
                  {d.lead ? <span lang={lang} className="line-clamp-3 text-meta leading-snug text-ink-soft">{pick(d.lead, lang)}</span> : null}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {module.learn?.length ? <LearnRoad slug={slug} steps={module.learn} /> : null}

      {module.reform ? <ReformStops slug={slug} reform={module.reform} /> : null}
      {module.beliefs?.length && module.reform ? <Beliefs slug={slug} beliefs={module.beliefs} /> : null}
      <Changes slug={slug} module={module} />
    </>
  );
}

/** The red band (T6; A7 and C1 of the road-signposted review): a sign's red, its triangle, the question, the first acts as
 *  the journey says them, the numbers an official page gives (each with that page), and the way to every step. In ink
 *  navy for a moment where no one is hurt (E5 of the work-counted review: a dismissal's first days), with the days left once
 *  the reader gave its journey the day, and the tool that counts what is owed; one line for a reader whose answer the
 *  band does not concern (C1). */
function Band({ slug, urgent, mine = null, folded = false }: { slug: string; urgent: Urgent; mine?: string | null; folded?: boolean }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  // The land's band is ink too, in the soil's dark (the land review): no triangle, rights that close; the tax's in
  // the ochre's dark (the tax review): nobody hurt, a penalty the day after.
  // The papers' in the deep of their teal (the papers review): a paper missing, nobody hurt.
  // The business's in the umber of its stamp (the business review): a cheque come back, the clock started.
  // Justice's in the night of its indigo (the justice review): someone taken to the station, the hours counting.
  // The digital's in the dark of its slate (the digital review): a threat on a phone, nobody hurt yet.
  // Housing's in the pine of its green (HM19 of the hard-moment review): a notice in hand, the weeks counting.
  const ink = urgent.tone === 'ink' || urgent.tone === 'soil' || urgent.tone === 'ochre' || urgent.tone === 'deep' || urgent.tone === 'umber' || urgent.tone === 'indigo' || urgent.tone === 'slate' || urgent.tone === 'pine';
  const due = readDue(slug, urgent.to);
  const left = due ? daysUntil(due.last) : -1;
  // The band's ink as a style: one colour for one band, not a utility for the whole site.
  const look = ink ? '' : 'bg-sign-red';
  const dark = urgent.tone === 'soil' ? SOIL : urgent.tone === 'ochre' ? OCHRE : urgent.tone === 'deep' ? DEEP : urgent.tone === 'umber' ? UMBER : urgent.tone === 'indigo' ? INDIGO : urgent.tone === 'slate' ? SLATE : urgent.tone === 'pine' ? PINE : 'var(--color-band-ink)';
  const inkBg = ink ? { background: dark } : undefined;
  const dates = urgent.dates?.length ? nextDates(urgent.dates, mine) : null;
  if (folded) {
    return (
      <Link to={refPath(slug, urgent.to)} style={inkBg} className={`flex min-h-12 items-center justify-between gap-3 rounded-card px-4 py-2 text-on-sign no-underline hover:text-on-sign ${look}`}>
        <span lang={lang} className="text-body font-bold">{pick(urgent.title, lang)}</span>
        <span className="text-meta underline underline-offset-4">{t('band.all')}</span>
      </Link>
    );
  }
  return (
    <section aria-labelledby="urgent" style={inkBg} className={`flex flex-col gap-2.5 rounded-card px-4 py-3.5 text-on-sign sm:px-5 ${look}`}>
      <div className="flex flex-wrap items-center gap-3">
        {ink ? null : (
          <svg aria-hidden="true" width="30" height="30" viewBox="0 0 40 40" className="shrink-0">
            <path d="M20 4.5 36.5 34h-33z" fill="#fff" stroke="#fff" strokeWidth="2" strokeLinejoin="round" />
            <path d="M20 14v10M20 29h.01" stroke="var(--color-sign-red)" strokeWidth="4" strokeLinecap="round" />
          </svg>
        )}
        <h2 id="urgent" lang={lang} className="m-0 flex-1 text-lead font-bold">{pick(urgent.title, lang)}</h2>
        {/* The days left, once the reader gave the journey its day; else the way to give it. */}
        {ink && !dates ? (
          <Link to={refPath(slug, urgent.to)} style={{ color: dark, background: '#fff' }} className="inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 text-body font-semibold no-underline">
            {left >= 0 ? (left === 0 ? t('journey.lastDay') : t('journey.left', { days: t('days', { count: left }) })) : <span lang={lang}>{pick(urgent.day ?? urgent.lead, lang)}</span>}
          </Link>
        ) : null}
        {/* The numbers an official page gives, as text one can read and select; a tap may call where the phone allows. */}
        {urgent.numbers?.map((n) => (
          // On the sign's own white by night too (HM43): red on the night sheet read 3.28 : 1, on white 5.3 : 1.
          <a key={n.number} href={`tel:${n.number}`} style={{ background: 'var(--color-on-sign)' }} className="inline-flex min-h-11 items-center gap-2 rounded-full ps-1.5 pe-3 text-body font-semibold text-sign-red no-underline hover:text-sign-red">
            <span dir="ltr" className="grid min-w-9 place-items-center rounded-full bg-sign-red px-1.5 text-lead font-bold leading-8 text-on-sign">{n.number}</span>
            <span lang={lang}>{pick(n.name, lang)}</span>
          </a>
        ))}
      </div>
      {dates ? (
        // The tax year's dates (the tax review, T9): the next two for the reader's answer, each with what is due,
        // its article, its last day and the days left; a tap opens what explains it.
        <ul className="m-0 flex list-none flex-col p-0 lg:grid lg:grid-cols-2 lg:gap-x-6">
          {dates.map((d, i) => (
            <li key={d.key} className={`py-2 ${i ? 'border-t' : ''} ${i === 1 ? 'lg:border-t-0' : ''}`} style={{ borderColor: 'color-mix(in srgb, #fff 18%, transparent)' }}>
              <Link to={refPath(slug, d.to)} className="flex items-baseline justify-between gap-3 text-on-sign no-underline hover:text-on-sign">
                <span className="flex min-w-0 flex-col">
                  <span lang={lang} className="text-body font-semibold leading-snug">{pick(d.what, lang)}</span>
                  <span lang={lang} className="text-meta leading-snug" style={{ opacity: 0.82 }}>{longDate(d.last, lang)} · {pick(d.article, lang)}</span>
                </span>
                <span className="shrink-0 text-lead font-bold tabular-nums">{d.left === 0 ? t('journey.lastDay') : t('journey.left', { days: t('days', { count: d.left }) })}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : urgent.papers?.length ? (
        // The papers that start a clock (the land review, M5): each with its limit, what it is for and its articles;
        // a tap opens the journey that says what follows.
        <ul className="m-0 flex list-none flex-col p-0 lg:grid lg:grid-cols-2 lg:gap-x-6">
          {urgent.papers.map((p, i) => (
            <li key={p.key} className={`py-2 ${i ? 'border-t' : ''} ${i === 1 ? 'lg:border-t-0' : ''}`} style={{ borderColor: 'color-mix(in srgb, #fff 18%, transparent)' }}>
              <Link to={refPath(slug, p.to)} className="flex items-baseline justify-between gap-3 text-on-sign no-underline hover:text-on-sign">
                <span className="flex min-w-0 flex-col">
                  <span lang={lang} className="text-body font-semibold leading-snug">{pick(p.paper, lang)}</span>
                  <span lang={lang} className="text-meta leading-snug" style={{ opacity: 0.82 }}>{pick(p.for, lang)} · {p.article ? pick(p.article, lang) : <bdi lang="ar" dir="rtl">{p.cites.map(articleWord).join('، ')}</bdi>}</span>
                </span>
                <span lang={lang} className="shrink-0 text-lead font-bold tabular-nums">{pick(p.limit, lang)}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : urgent.acts?.length ? (
        <ol className="m-0 flex list-none flex-col gap-1.5 p-0 lg:flex-row lg:flex-wrap lg:gap-x-6">
          {urgent.acts.map((a, i) => (
            <li key={i} className="flex items-start gap-2 text-body leading-snug lg:flex-1">
              <span aria-hidden="true" className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-[color-mix(in_srgb,#fff_24%,transparent)] text-meta font-bold leading-none">{i + 1}</span>
              <span lang={lang}>{pick(a, lang)}</span>
            </li>
          ))}
        </ol>
      ) : urgent.lead ? <p lang={lang} className="m-0 text-body">{pick(urgent.lead, lang)}</p> : null}
      {/* The land's band leads to one tool, from its chip: no second row. */}
      {urgent.tone === 'soil' ? null : <div className="-mb-1.5 -mt-1 flex flex-wrap items-center justify-between gap-x-4">
        <Link to={refPath(slug, urgent.to)} className="inline-flex min-h-11 items-center text-body font-semibold text-on-sign underline underline-offset-4 hover:text-on-sign">
          {t(dates ? 'band.dates' : 'band.all')}
        </Link>
        {urgent.tool ? (
          <Link to={refPath(slug, urgent.tool)} className="inline-flex min-h-11 items-center text-body font-semibold text-on-sign underline underline-offset-4 hover:text-on-sign">
            {urgent.tool_label ? pick(urgent.tool_label, lang) : t('band.owed')}
          </Link>
        ) : null}
        {urgent.numbers?.map((n) => (
          <a key={n.number} href={n.source.url} target="_blank" rel="noreferrer" title={pick(n.source.name, lang)} className="inline-flex min-h-11 items-center text-meta text-on-sign underline underline-offset-2 hover:text-on-sign">
            {t('band.source', { number: n.number, source: new URL(n.source.url).host.replace(/^www\./, '') })}
          </a>
        ))}
      </div>}
    </section>
  );
}

/** The reader's answer to the topic's question as one control beside the doors' question (A4): «أنا: كنسوق طوموبيل ⌄»;
 *  the answers in the one sheet, kept on the phone. */
function Me({ profile, mine, setMine }: { profile: NonNullable<Module['profile']>; mine: string | null; setMine: (v: string | null) => void }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const [open, setOpen] = useState(false);
  const chosen = profile.options.find((o) => o.key === mine);
  return (
    <>
      <button type="button" aria-haspopup="dialog" onClick={() => setOpen(true)}
              className={`inline-flex min-h-11 max-w-full items-center gap-1.5 rounded-full px-4 text-body ${chosen ? 'bg-ink font-medium text-sheet' : 'border border-field bg-sheet text-ink'}`}>
        <span lang={lang} className="truncate">{chosen ? (profile.we ? `${pick(profile.we, lang)}: ${pick(chosen.label, lang)}` : t('profile.me', { who: pick(chosen.label, lang) })) : pick(profile.question, lang)}</span>
        <span aria-hidden="true">⌄</span>
      </button>
      {open ? (
        <Sheet label={pick(profile.question, lang)} onClose={() => setOpen(false)} centered closeButton>
          <div className="flex flex-col gap-3 px-5 pb-6 pt-2">
            <h2 lang={lang} className="m-0 text-h3 font-bold">{pick(profile.question, lang)}</h2>
            <div role="radiogroup" aria-label={pick(profile.question, lang)} className="flex flex-col">
              {profile.options.map((o) => (
                <button key={o.key} type="button" role="radio" aria-checked={o.key === mine}
                        onClick={() => { setMine(o.key); setOpen(false); }}
                        className="flex min-h-13 items-center justify-between gap-3 border-t border-rule py-3 text-start text-lead first:border-t-0">
                  <span lang={lang}>{pick(o.label, lang)}</span>
                  <span aria-hidden="true" className={`grid size-6 shrink-0 place-items-center rounded-full border-2 ${o.key === mine ? 'border-ink bg-ink text-sheet' : 'border-field'}`}>
                    {o.key === mine ? '✓' : ''}
                  </span>
                </button>
              ))}
            </div>
            {mine ? (
              <button type="button" onClick={() => { setMine(null); setOpen(false); }} className="min-h-11 self-start text-body text-stamp">{t('profile.clear')}</button>
            ) : null}
          </div>
        </Sheet>
      ) : null}
    </>
  );
}

/** The figures the reader's answer makes theirs (A4): each a number over its words, its articles one tap away. */
function Facts({ facts }: { facts: ProfileFact[] }) {
  const { i18n } = useKitT();
  const lang = i18n.language;
  return (
    <ul className={`m-0 grid list-none gap-px overflow-hidden rounded-card bg-rule p-0 ${facts.length === 3 ? 'grid-cols-3' : 'grid-cols-2'}`}>
      {facts.map((f, i) => (
        <li key={i} className="flex min-w-0 flex-col gap-0.5 bg-sheet px-3 py-2.5">
          <span lang={lang} className="text-lead font-bold leading-tight tabular-nums">{typeof f.value === 'string' ? f.value : pick(f.value, lang)}</span>
          <span lang={lang} className="text-meta leading-snug text-ink-soft">{pick(f.label, lang)}</span>
          <span className="mt-0.5 flex flex-wrap gap-1">
            {f.cites.map((c) => (
              <Link key={c} to={c} className="inline-flex min-h-7 items-center rounded-full bg-wash px-2 text-meta text-stamp no-underline hover:bg-stamp hover:text-on-stamp">
                <bdi lang="ar" dir="rtl">{articleWord(c)}</bdi>
              </Link>
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The land's band: dark soil, as a style (one colour for one band). */
const SOIL = '#2E3A1C';
/** The tax band's dark ochre, white words on it at 9:1. */
const OCHRE = '#4A3800';
const DEEP = '#0B3A44';
const UMBER = '#4A2414';
const INDIGO = '#1B2150';
const SLATE = '#1E2B32';
const PINE = '#0C3B32';

/** The next two of a topic's yearly dates for the reader's answer (all when none): a date is the day before the one the
 *  law says «before» (`before`, month-day), the last day of the month it names (`in`), or the end of the month after a
 *  quarter (`quarterly`); one passed this year is next year's. */
function nextDates(dates: NonNullable<Urgent['dates']>, mine: string | null) {
  const today = todayIso();
  const year = Number(today.slice(0, 4));
  const iso = (y: number, m: number, d: number) => `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  const monthEnd = (y: number, m: number) => iso(y, m, new Date(Date.UTC(y, m, 0)).getUTCDate());
  const dayBefore = (y: number, md: string) => {
    const [m, d] = md.split('-').map(Number);
    const t = new Date(Date.UTC(y, m - 1, d) - 86_400_000);
    return iso(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate());
  };
  const candidates = (d: NonNullable<Urgent['dates']>[number], y: number) =>
    d.quarterly ? [monthEnd(y, 1), monthEnd(y, 4), monthEnd(y, 7), monthEnd(y, 10)]
      : d.before ? [dayBefore(y, d.before)] : d.in ? [monthEnd(y, Number(d.in))] : [];
  return dates
    .filter((d) => !mine || !d.for || d.for.includes(mine))
    .map((d) => ({ ...d, last: [...candidates(d, year), ...candidates(d, year + 1)].find((c) => c >= today)! }))
    .filter((d) => d.last)
    .sort((a, b) => a.last.localeCompare(b.last))
    .slice(0, 2)
    .map((d) => ({ ...d, left: daysUntil(d.last) }));
}

/** «المادة 23» from an article's address; the text is named once the article opens. */
const articleWord = (path: string) => `المادة ${(path.split('/').pop() ?? '').replace(/^art_/, '').replace(/-bis$/, ' مكرر')}`;

/** The instruments (A8): the tools a topic draws as what they measure, small and live, each opening its tool. A phone
 *  shows them in a row under the doors; a desk in its side column, held in view. */
export function HubInstruments({ slug, module, side = false }: { slug: string; module: Module; side?: boolean }) {
  const { t } = useKitT();
  const entry = INSTRUMENTS[slug];
  const shown = module.tools.filter((d) => entry?.keys[d.key]);
  if (!entry || !shown.length) return null;
  const Drawn = entry.component;
  return (
    // Its words break where they must (HM18): at 200 % text a word of three instruments in a row ran past the phone.
    <section className="flex flex-col gap-2 [overflow-wrap:anywhere]" aria-labelledby={side ? 'instruments-side' : 'instruments'}>
      <div className="flex flex-col">
        <h2 id={side ? 'instruments-side' : 'instruments'} className="m-0 text-lead font-semibold">{t('instruments')}</h2>
        <p className="m-0 text-meta text-ink-soft">{t('toolsLead')}</p>
      </div>
      <Suspense fallback={<div className={`grid gap-2 ${side ? '' : 'grid-cols-3'}`}>{shown.map((d) => <div key={d.key} className="h-28 rounded-card bg-sheet" />)}</div>}>
        <Drawn slug={slug} tools={shown} side={side} />
      </Suspense>
    </section>
  );
}

/** The learning path as a stretch of road (A10): a numbered marker a step, the lane filled as far as the reader got. */
function LearnRoad({ slug, steps }: { slug: string; steps: NonNullable<Module['learn']> }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const marks = steps.map((l) => ({ ...l, p: readProgress(slug, l.to) }));
  const reached = marks.reduce((n, m, i) => (m.p?.done ? i + 1 : n), 0);
  return (
    <section className="flex flex-col gap-3 rounded-card bg-sheet px-4 py-4 sm:px-5" aria-labelledby="learn">
      <h2 id="learn" className="m-0 text-lead font-semibold">{t('learn')}</h2>
      {slug === 'road' ? (
      <ol className="relative m-0 grid list-none gap-2 p-0" style={{ gridTemplateColumns: `repeat(${marks.length}, minmax(0, 1fr))` }}>
        {/* The road under the markers: dashed, filled in the topic's colour as far as the last step begun. */}
        <span aria-hidden="true" className="absolute inset-x-[8%] top-[18px] h-3 rounded-full bg-ink/80">
          <span className="absolute inset-x-2 top-[5px] h-0.5 bg-[repeating-linear-gradient(to_left,var(--color-sheet)_0_10px,transparent_10px_18px)] rtl:bg-[repeating-linear-gradient(to_right,var(--color-sheet)_0_10px,transparent_10px_18px)]" />
          {reached ? <span className="absolute inset-y-0 start-0 rounded-full bg-[var(--t)]" style={{ width: `${(Math.min(reached, marks.length - 1) / Math.max(1, marks.length - 1)) * 100}%` }} /> : null}
        </span>
        {marks.map((m, i) => (
          <li key={m.to} className="relative flex flex-col items-center">
            <Link to={refPath(slug, m.to)} className="flex min-h-11 w-full flex-col items-center gap-1.5 text-center text-ink no-underline hover:text-stamp">
              <Marker n={i + 1} done={!!m.p?.done} />
              <span lang={lang} className="text-meta font-medium leading-snug">{pick(m.title, lang)}</span>
              {m.p?.done ? <span className="text-meta text-ink-soft">{t('progress', { done: m.p.done, total: m.p.total })}</span> : null}
            </Link>
          </li>
        ))}
      </ol>
      ) : (
      // Another topic: a plain line (the road's asphalt is the road's own), down the page on a phone, where a step's
      // title is a sentence beside its number (five columns could not hold «contractuelle»), across from a tablet up.
      <ol className="relative m-0 flex list-none flex-col gap-2 p-0 sm:grid" style={{ gridTemplateColumns: `repeat(${marks.length}, minmax(0, 1fr))` }}>
        <span aria-hidden="true" className="absolute w-0.5 bg-rule sm:hidden" style={{ insetInlineStart: 23, top: 24, bottom: 24 }} />
        <span aria-hidden="true" className="absolute inset-x-[8%] top-[23px] hidden h-0.5 bg-rule sm:block">
          {reached ? <span className="absolute inset-y-0 start-0 bg-[var(--t)]" style={{ width: `${(Math.min(reached, marks.length - 1) / Math.max(1, marks.length - 1)) * 100}%` }} /> : null}
        </span>
        {marks.map((m, i) => (
          <li key={m.to} className="relative">
            <Link to={refPath(slug, m.to)} className="flex min-h-11 w-full items-center gap-3 text-ink no-underline hover:text-stamp sm:flex-col sm:gap-1.5 sm:text-center">
              <Marker n={i + 1} done={!!m.p?.done} />
              <span className="flex min-w-0 flex-col">
                <span lang={lang} className="text-meta font-medium leading-snug">{pick(m.title, lang)}</span>
                {m.p?.done ? <span className="text-meta text-ink-soft">{t('progress', { done: m.p.done, total: m.p.total })}</span> : null}
              </span>
            </Link>
          </li>
        ))}
      </ol>
      )}
    </section>
  );
}

function Marker({ n, done }: { n: number; done: boolean }) {
  return <span className={`grid size-12 shrink-0 place-items-center rounded-control border-2 bg-sheet text-lead font-bold ${done ? 'border-[var(--t)]' : 'border-field'}`}>{n}</span>;
}

/** What changes (A11): the next dated change in words, then the one after; never a count of stages that reads «0». */
function Changes({ slug, module }: { slug: string; module: Module }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const changes = module.changes ?? [];
  const next = module.next ?? [];
  if (!changes.length) return null;
  const counts = (['in_force', 'coming', 'bill', 'announced'] as const)
    .map((stage) => ({ stage, n: changes.filter((c) => c.stage === stage).length })).filter((c) => c.n);
  return (
    <Link to={`/topics/${slug}/changes`} className="flex flex-col gap-1 rounded-card bg-sheet px-5 py-4 text-ink no-underline hover:text-stamp">
      {next.length ? (
        <>
          <span className="text-lead font-bold">{t('next.first', { date: longDate(next[0].date, lang) })}</span>
          <span lang={lang} className="text-body">{pick(next[0].text, lang)}</span>
          {next[1] ? <span lang={lang} className="text-meta text-ink-soft">{t('next.then', { date: longDate(next[1].date, lang) })} {pick(next[1].text, lang)}</span> : null}
        </>
      ) : module.last ? (
        <>
          <span className="text-lead font-bold">{t('next.last', { date: longDate(module.last.date, lang) })}</span>
          <span lang={lang} className="text-body">{pick(module.last.text, lang)}</span>
        </>
      ) : (
        <>
          <span className="text-lead font-semibold">{t('changes.card')}</span>
          <span className="text-meta text-ink-soft">{counts.map((c) => t(`next.count.${c.stage}`, { count: c.n })).join(t('next.sep'))}</span>
        </>
      )}
      <span className="text-meta font-medium text-stamp">{t('next.all')}</span>
    </Link>
  );
}


/** What people say, and what the law says (D3 of the consumer plan; G6 of the family-papers review: under the reform,
 *  each claim answered by the article in force). */
function Beliefs({ slug, beliefs }: { slug: string; beliefs: NonNullable<Module['beliefs']> }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  return (
    <section className="flex flex-col gap-2" aria-labelledby="beliefs">
      <h2 id="beliefs" className="m-0 text-lead font-semibold">{t('beliefs')}</h2>
      <ul className="m-0 grid list-none gap-2 p-0 sm:grid-cols-2 lg:grid-cols-3">
        {beliefs.map((b, i) => (
          <li key={i}>
            <Link to={refPath(slug, b.to)} className="flex h-full flex-col gap-2 rounded-card bg-sheet px-4 py-3 text-ink no-underline hover:text-stamp">
              <span lang={lang} className="text-body font-semibold leading-snug text-amended">«{pick(b.claim, lang)}»</span>
              <span lang={lang} className="text-body leading-snug">{pick(b.truth, lang)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The reform as four stops on one line (G6): announced, a bill, adopted, published; the one reached lit, its line and
 *  the day it was last checked. Never written as law. */
export function ReformStops({ slug, reform }: { slug: string; reform: NonNullable<Module['reform']> }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const stages = ['announced', 'bill', 'adopted', 'law'] as const;
  const reached = stages.indexOf(reform.stage as (typeof stages)[number]);
  return (
    <Link to={refPath(slug, 'reform/reform')} className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-4 text-ink no-underline hover:text-stamp">
      <span className="text-meta font-semibold text-amended">{t('reformTitle')} · {t('reform.notLaw')}</span>
      <Stops stages={stages.map((k) => t(`reform.stage.${k}`))} reached={reached} />
      <span lang={lang} className="text-body">{pick(reform.line, lang)}</span>
      <span className="text-meta text-ink-soft">{t('reform.lastCheck', { date: longDate(reform.checked_on, lang) })}</span>
    </Link>
  );
}
