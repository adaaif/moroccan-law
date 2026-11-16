import { Suspense, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { LoadError } from '@/features/corpus/NotFound';
import { Button, Note, Page, PageSkeleton } from '@/shared/components/ui';
import { STEP_WIDGETS } from '../registry';
import { AR } from '@/features/corpus/format';
import { pick, refPath, useKitItem, useKitT, type Cite, type Delay, type Journey, type Step } from './api';
import { ending } from './dates';
import { HolidayLine } from './HolidayLine';
import { DelayLine, KitPage, NextLinks } from './parts';
import { readDue, readSet, writeDue, writeSet } from './progress';
import { Sign } from './Sign';
import { noteUse } from './use';
import { calendarFile, useRefTitles, whatsapp, origin } from './share';
import { RegistryStamp } from './RegistryStamp';
import { ArticlePeek, DayChips } from './tool/parts';
import { dayWords, daysUntil } from './tool/days';
import { useToolState } from './tool/state';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();

/** A journey (F4 of the family plan; J1–J6 of the road tools review): what happens, as numbered steps. Each step
 *  says itself in one sentence first, the law's words and their articles folded under it; a journey with time limits
 *  asks its day once and every limit counted from it becomes a date with the days left; a step's tool works in place
 *  where the topic has one; the official service a step needs is linked there; the reader ticks the steps done, on the
 *  phone. «أرسل في واتساب» sends the steps as text, for the person one goes with. */
/** A step's tool opened on the journey's own case (PX3 of the where-it-trips review): `tools/deadline?k=crim-appeal`
 *  carries its case, and the journey's day goes where the tool reads it, `{d}` in the ref or `d` (a criminal judgment
 *  opened the civil appeal, three weeks late). */
function toolTo(slug: string, ref: string, day: string): string {
  const [tool, query = ''] = ref.split('?');
  const asked = new URLSearchParams(query.replace('{d}', day));
  if (day && !query.includes('{d}')) asked.set('d', day);
  if (!day) for (const [k, v] of [...asked]) if (v === '') asked.delete(k);
  const qs = asked.toString();
  return `${refPath(slug, tool)}${qs ? `?${qs}` : ''}`;
}

export default function JourneyPage({ slug }: { slug: string }) {
  const { key = '' } = useParams();
  const { t, i18n } = useKitT();
  const q = useKitItem<Journey>(slug, 'journeys', key);
  const titles = useRefTitles(slug);
  const lang = i18n.language;
  // The day the reader gave this journey before, kept on the phone (G8 of the family-papers review).
  const [s, setState] = useToolState({ d: readDue(slug, `journeys/${key}`)?.day ?? today() });
  const [done, setDone] = useState(() => readSet(slug, `journeys/${key}`));
  if (q.isLoading) return <Page width="reading"><PageSkeleton kind="text" /></Page>;
  const j = q.data;
  if (!j) return <Page width="reading"><LoadError error={q.error} retry={() => void q.refetch()} /></Page>;
  const toggle = (i: number) => {
    const id = String(i);
    const next = done.includes(id) ? done.filter((x) => x !== id) : [...done, id];
    setDone(next);
    if (!done.includes(id)) noteUse('tick');
    writeSet(slug, `journeys/${key}`, next, j.steps.length);
  };
  const set = ({ d }: { d: string }) => {
    setState({ d });
    const last = nextLimit(j.steps, d);
    writeDue(slug, `journeys/${key}`, last ? { day: d, last, all: limits(j.steps, d) } : null);
  };
  const dayChips = j.day ? <DayChips label={pick(j.day, lang)} value={s.d} onChange={(d) => set({ d })} ago={[0, 1, 2, 7]} /> : null;
  const ends = j.ends ? <Ends slug={slug} ends={j.ends} /> : null;
  // The message a reader sends (HM5 of the hard-moment review): their moment in the door's own words, the day they
  // gave and the last day it sets, with the year, then the steps, and a link that keeps the day: opened five days later
  // it counted from the relative's today.
  const door = titles[`journeys/${j.key}`];
  const date = (iso: string) => new Date(`${iso}T12:00:00Z`).toLocaleDateString(lang === 'fr' ? 'fr-MA' : 'ar-MA',
    { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
  const due = j.day ? nextLimit(j.steps, s.d) : null;
  const message = [...(door ? [pick(door, lang)] : []), pick(j.title, lang),
    ...(j.day ? [`${pick(j.day, lang)}: ${date(s.d)}`] : []), ...(due ? [t('journey.last', { date: date(due) })] : []), '',
    ...j.steps.map((st, i) => `${i + 1}. ${pick(st.title, lang)}: ${pick(st.answer ?? st.body, lang)}`),
    '', `${origin()}${refPath(slug, `journeys/${j.key}`)}${j.day ? `?d=${s.d}` : ''}`].join('\n');
  // The next limit pressed at the top as the registry stamps it (HM25 of the hard-moment review): the court's last
  // day was a 14 px pill at step 6 of 8, without its year though it fell in the next one.
  const dueStep = due ? j.steps.find((st) => st.delay?.on_day && endOf(st.delay, s.d) === due) : undefined;
  const dueLeft = due ? daysUntil(due) : 0;
  const stamp = due && dueStep ? (
    <section className="flex flex-col gap-1" aria-label={t('journey.last', { date: dayWords(due, lang) })}>
      <p className="sr-only">{t('journey.last', { date: dayWords(due, lang) })} · {pick(dueStep.title, lang)}</p>
      <RegistryStamp day={due} lang={lang} caption={t('journey.stamp', { what: pick(dueStep.title, lang) })}
                     foot={[dueLeft < 0 ? t('journey.passed') : dueLeft === 0 ? t('journey.lastDay') : t('journey.left', { days: t('days', { count: dueLeft }) }),
                            dueStep.cites?.[0]?.label].filter(Boolean).join(' · ')} />
      <div className="flex flex-wrap justify-center gap-x-4">
        <button type="button" className="inline-flex min-h-11 items-center text-body font-medium text-stamp"
                onClick={() => calendarFile([{ date: due, title: `${pick(j.title, lang)}: ${pick(dueStep.title, lang)}`,
                                               detail: `${pick(dueStep.delay!.from, lang)} · ${origin()}${refPath(slug, `journeys/${j.key}`)}?d=${s.d}` }], j.key)}>
          {/* The key lives under `tool`: the button read «remind» in both languages (RD12 of the readers review). */}
          {t('tool.remind')}
        </button>
        <button type="button" className="inline-flex min-h-11 items-center text-body font-medium text-stamp" onClick={() => whatsapp(message)}>{t('share')}</button>
      </div>
    </section>
  ) : null;
  return (
    <KitPage slug={slug} item={j} title={pick(j.title, lang)} lead={pick(j.lead, lang)}
             aside={dayChips || ends ? <>{dayChips ? <section className="rounded-card bg-sheet px-5 py-4">{dayChips}</section> : null}{stamp}{ends}</> : undefined}>
      {/* On a phone the day sits above the steps; a desk holds it in the side column with the paper at the end (G11). */}
      {dayChips ? <section className="rounded-card bg-sheet px-5 py-4 lg:hidden">{dayChips}</section> : null}
      {stamp ? <div className="lg:hidden">{stamp}</div> : null}
      {done.length ? <p className="m-0 text-meta text-ink-soft">{t('journey.done', { done: done.length, total: j.steps.length })}</p> : null}
      {/* The steps down one dashed line (A16 of the road-signposted review), a deadline the stretch of solid line under its
          step: the dates read down the line. Each step's articles open over the page; its details fold under them. */}
      <ol className="m-0 flex list-none flex-col rounded-card bg-sheet px-4 py-5 sm:px-7">
        {j.steps.map((st, i) => {
          const ticked = done.includes(String(i));
          const last = i === j.steps.length - 1;
          const Widget = st.tool ? STEP_WIDGETS[slug]?.[st.tool] : undefined;
          return (
            <li key={i} id={`step-${i + 1}`} className={`flex gap-4 transition-opacity duration-300 motion-reduce:transition-none ${ticked ? 'opacity-60' : ''}`}>
              <div className="flex shrink-0 flex-col items-center">
                <button type="button" onClick={() => toggle(i)} aria-pressed={ticked} aria-label={t(ticked ? 'journey.untick' : 'journey.tick', { n: i + 1 })}
                        className={`flex size-11 shrink-0 items-center justify-center rounded-full text-body font-bold transition-colors duration-200 motion-reduce:transition-none ${ticked ? 'bg-in-force text-sheet' : 'bg-ink text-sheet'}`}>
                  {ticked ? '✓' : i + 1}
                </button>
                {last ? null : st.delay
                  ? <span aria-hidden="true" className="my-1 w-1 flex-1 rounded-full bg-[var(--t)]" />
                  : <span aria-hidden="true" className="my-1 flex-1 border-s-2 border-dashed border-field" />}
              </div>
              <div className={`flex min-w-0 flex-1 flex-col gap-2 ${last ? '' : 'pb-6'}`}>
                <h2 lang={lang} className="m-0 pt-1 text-lead font-semibold leading-snug">
                  <span className="sr-only">{t('step', { n: i + 1 })}: </span>{pick(st.title, lang)}
                </h2>
                {st.answer ? <p lang={lang} className="m-0 text-lead leading-relaxed">{pick(st.answer, lang)}</p> : null}
                {st.delay ? <Deadline delay={st.delay} day={j.day && st.delay.on_day ? s.d : null} /> : null}
                {/* The articles the answer rests on beside it; the others with the law's words, under «التفاصيل» (G7). */}
                {st.answer ? <PeekChips cites={st.cites?.slice(0, 2)} /> : null}
                {Widget ? <Suspense fallback={null}><Widget slug={slug} day={s.d} journey={j.key} /></Suspense> : null}
                {st.answer ? (
                  <details className="group">
                    <summary className="flex min-h-11 cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="inline-flex items-center gap-1 text-meta font-medium text-ink-soft">
                        {t('journey.details')}<span aria-hidden="true" className="transition-transform group-open:rotate-180 motion-reduce:transition-none">⌄</span>
                      </span>
                    </summary>
                    <p lang={lang} className="m-0 pb-2 text-body leading-relaxed">{pick(st.body, lang)}</p>
                    <PeekChips cites={st.cites?.slice(2)} />
                  </details>
                ) : <p lang={lang} className="m-0 text-body leading-relaxed">{pick(st.body, lang)}</p>}
                {st.answer ? null : <PeekChips cites={st.cites} />}
                {st.note ? (
                  <Note tone="people" quiet>
                    <p className="m-0 text-meta font-semibold text-people">{t('note')}</p>
                    <p lang={lang} className="m-0 text-body">{pick(st.note, lang)}</p>
                    <PeekChips cites={st.note.cites} />
                  </Note>
                ) : null}
                {st.papers || st.tool || st.next || st.services?.length ? (
                  <div className="flex flex-wrap gap-x-5 gap-y-1">
                    {st.services?.map((x) => (
                      <a key={x.url} href={x.url} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center text-body font-medium">{pick(x.name, lang)}</a>
                    ))}
                    {st.papers ? <Link to={refPath(slug, st.papers)} className="inline-flex min-h-11 items-center text-body font-medium">{t('papers')}</Link> : null}
                    {st.tool && titles[st.tool.split('?')[0]] ? <Link to={toolTo(slug, st.tool, j.day ? s.d : '')} className="inline-flex min-h-11 items-center text-body font-medium">{pick(titles[st.tool.split('?')[0]], lang)}</Link> : null}
                    {st.next && titles[st.next] ? <Link to={refPath(slug, st.next)} className="inline-flex min-h-11 items-center text-body font-medium">{t('goOn')}: {pick(titles[st.next], lang)}</Link> : null}
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
      {ends ? <div className="lg:hidden">{ends}</div> : null}
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
      </div>
      <NextLinks slug={slug} refs={j.next} titles={titles} />
    </KitPage>
  );
}

/** A step's articles as chips that open the article over the journey (A16), the reader keeping their place. */
function PeekChips({ cites }: { cites?: Cite[] }) {
  const { i18n } = useKitT();
  const [open, setOpen] = useState<string | null>(null);
  if (!cites?.length) return null;
  const many = new Set(cites.map((c) => c.text.ar)).size > 1;
  return (
    <span className="flex flex-wrap gap-1.5">
      {cites.map((c) => (
        <button key={c.path} type="button" onClick={() => setOpen(c.path)}
                className="inline-flex min-h-11 max-w-full flex-wrap items-center gap-1.5 rounded-full bg-wash px-3 text-meta text-stamp hover:bg-stamp hover:text-on-stamp">
          <bdi {...AR} className="font-semibold">{c.label}</bdi>
          {many ? <span lang={i18n.language} className="text-ink-soft">{pick(c.text, i18n.language)}</span> : null}
        </button>
      ))}
      {open ? <ArticlePeek path={open} onClose={() => setOpen(null)} /> : null}
    </span>
  );
}

/** A limit the law sets, as a date once the journey knows its day (J2): «آخر أجل: الخميس 20 نونبر · باقي 26 يوما». */
function Deadline({ delay, day }: { delay: Delay; day: string | null }) {
  const { t, i18n } = useKitT();
  if (!day) return <DelayLine delay={delay} />;
  const { date: last, moved, on } = ending(day, { key: '', path: '', label: '', days: delay.days, months: delay.months, hours: delay.hours, rolls: delay.rolls, complete: delay.complete });
  const left = daysUntil(last);
  return (
    <>
    <p className={`m-0 inline-flex flex-wrap items-center gap-x-2 self-start rounded-full px-3 py-1 text-meta ${left < 0 ? 'bg-[color-mix(in_srgb,var(--color-repealed)_12%,var(--color-sheet))] text-repealed' : 'bg-amended-wash text-amended'}`}>
      <span className="font-semibold">{t('journey.last', { date: dayWords(last, i18n.language, last.slice(0, 4) !== todayIso().slice(0, 4)) })}</span>
      <span>{left < 0 ? t('journey.passed') : left === 0 ? t('journey.lastDay') : t('journey.left', { days: t('days', { count: left }) })}</span>
    </p>
    <HolidayLine moved={moved} on={on} />
    </>
  );
}

/** The end of the journey's next limit counted from the reader's day: the first not yet passed, else the last one. */
/** Every limit the journey's day starts, in order: kept whole, so the next is found when read (PX13 of
 *  the where-it-trips review: only the one next on the day it was set was kept, and a birth's six months showed nowhere after its 30 days). */
function limits(steps: Step[], day: string): string[] {
  return steps.filter((st) => st.delay?.on_day).map((st) => {
    const d = st.delay as Delay;
    return ending(day, { key: '', path: '', label: '', days: d.days, months: d.months, hours: d.hours, rolls: d.rolls, complete: d.complete }).date;
  }).sort();
}

function endOf(d: Delay, day: string): string {
  return ending(day, { key: '', path: '', label: '', days: d.days, months: d.months, hours: d.hours, rolls: d.rolls, complete: d.complete }).date;
}

function nextLimit(steps: Step[], day: string): string | null {
  const ends = limits(steps, day);
  return ends.find((e) => daysUntil(e) >= 0) ?? ends[ends.length - 1] ?? null;
}

/** The paper the reader leaves with (G1 of the family-papers review): its office's mark, its name, its articles; on
 *  a punch card in a topic counted in numbers, with the list of what to keep (E12 of the work-counted review). */
function Ends({ slug, ends }: { slug: string; ends: NonNullable<Journey['ends']> }) {
  const { t, i18n } = useKitT();
  const titles = useRefTitles(slug);
  const lang = i18n.language;
  return (
    <section className="flex flex-col gap-2.5 rounded-card bg-sheet px-5 py-4" aria-labelledby="ends">
      <h2 id="ends" className="m-0 text-meta font-semibold text-ink-soft">{t('journey.ends')}</h2>
      <div className="flex items-start gap-3">
        <Sign kind={ends.office} icon={ends.icon} card={!!ends.icon} size={40} />
        <p lang={lang} className="m-0 text-lead font-semibold leading-snug">{pick(ends.paper, lang)}</p>
      </div>
      <PeekChips cites={ends.cites} />
      {ends.papers && titles[ends.papers] ? (
        <Link to={refPath(slug, ends.papers)} className="inline-flex min-h-11 items-center self-start text-body font-medium">{pick(titles[ends.papers], lang)}</Link>
      ) : null}
    </section>
  );
}
