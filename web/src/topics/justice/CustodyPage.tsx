import { Button } from '@/shared/components/ui';
import { ZONE } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { ARTICLES, clock, hoursBetween, type Case } from './rules/custody';
import { HourTrack, Sheet } from './parts';
import { articleLabel, useJusticeT } from './strings';

const CASES: Case[] = ['ordinary', 'state', 'terror'];

/** Now as a wall clock in Morocco, «YYYY-MM-DDTHH:MM». */
function nowInMorocco(): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: ZONE, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
    .formatToParts(new Date());
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '00';
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`;
}

/** «فوقاش خاصو يتقدم؟» (the justice review): the hour of the arrest and the kind of case → when the custody ends, when
 *  it ends with the extensions a written, reasoned permission allows, and the lawyer's contact from the first hour, as one
 *  track of hours with now on it (22.01 arts 66, 66-2, 67, 80, as law 03.23 left them). It waits for a person's check.
 *  The inputs live in the address. */
export default function CustodyPage({ slug }: { slug: string }) {
  const { t, i18n } = useJusticeT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const now = nowInMorocco();
  const [s, set] = useToolState({ a: `${now.slice(0, 13)}:00`, c: 'ordinary', m: '' });
  const kind = (CASES.includes(s.c as Case) ? s.c : 'ordinary') as Case;
  const minor = s.m === '1';
  const arrest = /^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(s.a) ? s.a : `${now.slice(0, 13)}:00`;
  const stops = clock(arrest, kind, minor);
  const end = stops.find((x) => x.key === 'end')!;
  const longest = stops[stops.length - 1];
  const left = Math.floor(hoursBetween(now, end.at));
  const leftAll = Math.floor(hoursBetween(now, longest.at));
  const when = (iso: string) => `${new Date(`${iso}:00Z`).toLocaleDateString(lang === 'fr' ? 'fr-MA' : 'ar-MA', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' })} ${t('custody.at')} ${iso.slice(11, 16)}`;
  const value = left >= 0 ? t('custody.left', { count: left }) : leftAll >= 0 ? t('custody.extended', { count: leftAll }) : t('custody.over');
  const extended = stops.some((x) => x.key === 'ext1');
  const message = [t('custody.message'), `${t('custody.arrested')}: ${when(arrest)}`, `${t('custody.endLine')}: ${when(end.at)}`,
    extended ? `${t('custody.longestLine')}: ${when(longest.at)}` : t('custody.minorNoExtension'), here()].join('\n');
  return (
    <KitPage slug={slug} title={t('custody.title')} lead={t('custody.lead')}>
      <AnswerCard over={t('custody.question')} tone={left >= 0 ? 'stamp' : 'warn'} value={value}
                  under={<p className="m-0">{extended ? t('custody.under', { end: when(end.at), longest: when(longest.at) })
                    : t('custody.underMinor', { end: when(end.at) })}</p>} />
      <section className="rounded-card bg-sheet px-3 py-2 sm:px-5">
        <HourTrack stops={stops} now={now} lang={lang} hour={(n) => t('custody.hour', { count: n })}
                   labels={{ arrest: t('custody.stops.arrest'), lawyer: t('custody.stops.lawyer'), end: t('custody.stops.end'),
                             ext1: t('custody.stops.ext1'), ext2: t('custody.stops.ext2') }} />
      </section>
      <Sheet>
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('custody.when')}</span>
          <input type="datetime-local" value={arrest} max={now} dir="ltr" onChange={(e) => e.target.value && set({ a: e.target.value.slice(0, 16) })}
                 className="h-12 w-full max-w-64 rounded-control border border-field bg-sheet px-3 text-body" />
          <span className="text-meta text-ink-soft">{t('custody.whenNote')}</span>
        </label>
        <Chips label={t('custody.minorAsk')} value={minor ? '1' : '0'} onChange={(m) => set({ m: m === '1' ? '1' : '' })}
               options={[{ key: '0', label: t('custody.minorNo') }, { key: '1', label: t('custody.minorYes') }]} />
        <Chips label={t('custody.kind')} value={kind} onChange={(c) => set({ c })}
               options={CASES.map((c) => ({ key: c, label: t(`custody.cases.${c}`) }))} />
      </Sheet>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-h3 font-bold">{t('custody.rightsTitle')}</h2>
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
          {(minor ? ['minorPlace', 'minorFamily', 'minorContact', 'reason', 'silence', 'lawyer', 'doctor', 'record'] as const
            : ['reason', 'silence', 'lawyer', 'family', 'doctor', 'record'] as const).map((k) => <li key={k} className="text-body">• {t(`custody.rights.${k}`)}</li>)}
        </ul>
        <SourceFold paths={Object.values(ARTICLES)} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, 'journeys/custody')}>{t('custody.toJourney')}</Button>
          <Button variant="quiet" to={refPath(slug, 'checklists/custody-rights')}>{t('custody.toList')}</Button>
          <Button variant="quiet" onClick={() => whatsapp(message)}>{t('custody.share')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
