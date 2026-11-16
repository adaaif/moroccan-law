import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { useProfile } from '../kit/profile';
import { AnswerCard, Chips, Listen, SourceFold } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { RoadIcon } from '../kit/icons';
import { LicenceCard } from './LicenceCard';
import { OFFENCES } from './rules/fines';
import { atOnce, balanceAfter, START, type Licence, type Picked } from './rules/points';
import { articleLabel, useRoadT } from './strings';

/** The offences that take points, by art. 99's rows: the contraventions of the fine tool and the helmet, then the
 *  délits a stop can bring (rows 5, 6, 7, 9, 10, 15), which a court decides. */
type Pick = { key: string; icon: string; p: Picked };
const CONTRAVENTIONS: Pick[] = [
  ...OFFENCES.filter((o) => o.points).map((o) => ({ key: o.key, icon: o.icon, p: { points: o.points, delit: false } })),
  { key: 'helmet', icon: 'helmet', p: { points: 2, delit: false } },
];
const DELITS: Pick[] = [
  { key: 'speed50', icon: 'speed', p: { points: 6, delit: true } },
  { key: 'alcohol', icon: 'alcohol', p: { points: 6, delit: true } },
  { key: 'hitRun', icon: 'hitRun', p: { points: 6, delit: true } },
  { key: 'suspended', icon: 'suspended', p: { points: 4, delit: true } },
  { key: 'injuries', icon: 'injuries', p: { points: 3, delit: true } },
  { key: 'injuriesAgg', icon: 'injuries', p: { points: 6, delit: true, aggravated: true } },
];
const ALL = [...CONTRAVENTIONS, ...DELITS];
const art = (n: string) => `/ma/loi/52-05/art_${n}`;

/** «شحال بقا ليا من نقطة؟» (R12 of the road plan; P1–P4, F6, F7 of the road tools review): a simulation from the law,
 *  never anyone's real balance (that is NARSA's, linked). The licence as dots; one stop or several, each capped by
 *  art. 100; the years and the course that bring points back (arts 33, 35). The licence follows the reader's answer
 *  on the topic's page; the fine tool opens it with its offence picked (`?o=`). */
export default function PointsPage({ slug }: { slug: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [mine] = useProfile(slug);
  const [s, set] = useToolState({ l: mine === 'probation' ? 'probation' : 'full', o: 'speed20', y: '0', c: '' });
  const { search } = useLocation();
  const licence = (s.l === 'probation' ? 'probation' : 'full') as Licence;
  const max = START[licence];
  const stops = s.o.split(';').map((x) => x.split(',').filter((k) => ALL.some((p) => p.key === k)));
  const [at, setAt] = useState(stops.length - 1);
  const current = Math.min(at, stops.length - 1);
  const write = (next: string[][]) => set({ o: next.map((x) => x.join(',')).join(';') });
  const toggle = (k: string) => write(stops.map((x, i) => (i !== current ? x : x.includes(k) ? x.filter((y) => y !== k) : [...x, k])));
  const results = stops.map((x) => atOnce(ALL.filter((p) => x.includes(p.key)).map((p) => p.p)));
  const taken = results.reduce((n, r) => n + r.total, 0);
  const after = Math.max(0, max - taken);
  const years = Number(s.y) || 0;
  const now = balanceAfter(after, max, years, s.c === '1');
  const lastCap = results[current]?.cap ?? null;
  const capDot = lastCap !== null ? max - results.slice(0, current + 1).reduce((n, r) => n + r.total, 0) : null;
  const twoThirds = licence === 'probation' && after > 0 && taken > (max * 2) / 3;
  // The offence the tool opens on is an example until the reader picks theirs (HM15 of the hard-moment review).
  const example = !new URLSearchParams(search).has('o');
  const said = taken ? t('points.takenAll', { points: t('points_n', { count: taken }), stops: t('stops_n', { count: stops.filter((x) => x.length).length }) }) : t('points.nothing');
  const over = example ? `${t('points.example')} ${said}` : said;
  const under = after === 0 ? t('points.zero') : years || s.c ? t('points.backTo', { points: t('points_n', { count: now - after }) }) : '';
  const tile = (p: Pick) => {
    const on = stops[current]?.includes(p.key);
    return (
      <li key={p.key}>
        <button type="button" aria-pressed={on} onClick={() => toggle(p.key)}
                className={`flex h-full min-h-20 w-full flex-col items-start justify-between gap-1.5 rounded-card border px-3 py-2.5 text-start transition-[border-color,background-color,transform] duration-150 active:scale-[.97] motion-reduce:transition-none ${
                  on ? 'border-2 border-[var(--t)] bg-wash' : 'border-rule bg-sheet hover:border-field'}`}>
          <span className="flex w-full items-center justify-between gap-2">
            <span className="text-[color:var(--t)]"><RoadIcon name={p.icon} size={24} /></span>
            <bdi dir="ltr" className="text-meta font-semibold tabular-nums text-ink-soft">−{p.p.points}</bdi>
          </span>
          <span className="text-body font-medium leading-snug">{t(`offences.${p.key}`)}</span>
        </button>
      </li>
    );
  };
  return (
    <KitPage slug={slug} title={t('points.title')} lead={t('points.lead')}>
      <AnswerCard share over={over} value={t('points.balance', { now, max })} under={under ? <p className="m-0">{under}</p> : null}
                  tone={now === 0 ? 'warn' : 'stamp'} />
      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('points.licence')} value={licence} onChange={(l) => set({ l })}
               options={(['probation', 'full'] as const).map((l) => ({ key: l, label: t(`points.licences.${l}`) }))} />
        <LicenceCard max={max} after={after} now={now} cap={capDot} title={t('points.card')} />
        {lastCap ? <p className="m-0 text-body">{t('points.capped', { cap: t('points_n', { count: lastCap }) })}</p> : null}
        {twoThirds ? <Note tone="warn" quiet><p className="m-0 text-body">{t('points.twoThirds')}</p></Note> : null}
        {stops.length > 1 ? (
          <Chips label={t('points.stops')} value={current} onChange={setAt}
                 options={stops.map((_, i) => ({ key: i, label: t('points.stop', { n: i + 1, points: results[i].total }) }))} />
        ) : null}
        <div className="flex flex-col gap-2">
          <span className="text-body font-semibold">{t('points.pick')}</span>
          <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-3">{CONTRAVENTIONS.map(tile)}</ul>
        </div>
        <details className="flex flex-col gap-2 rounded-card bg-paper px-4 py-3">
          <summary className="min-h-11 cursor-pointer content-center text-body font-semibold">{t('points.delits')}</summary>
          <p className="m-0 mb-2 text-meta text-ink-soft">{t('points.delitsLead')}</p>
          <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-3">{DELITS.map(tile)}</ul>
        </details>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => { write([...stops, []]); setAt(stops.length); }}>{t('points.addStop')}</Button>
          {stops.length > 1 ? <Button onClick={() => { write(stops.filter((_, i) => i !== current)); setAt(Math.max(0, current - 1)); }}>{t('points.removeStop')}</Button> : null}
        </div>
      </section>
      {after > 0 ? (
        <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
          <h2 className="m-0 text-lead font-semibold">{t('points.back')}</h2>
          <label className="flex flex-col gap-1.5">
            <span className="text-body">{t('points.years')}: <b>{t(`points.yearsN.${years}`)}</b></span>
            <input type="range" min={0} max={3} step={1} value={years} onChange={(e) => set({ y: e.target.value })} className="w-full max-w-md accent-[var(--t)]" />
          </label>
          <label className="flex min-h-11 items-center gap-3">
            <input type="checkbox" checked={s.c === '1'} onChange={(e) => set({ c: e.target.checked ? '1' : '' })} className="size-5 accent-[var(--t)]" />
            <span className="text-body">{t('points.courseToggle')}</span>
          </label>
          <p className="m-0 text-meta text-ink-soft">{t('points.backRule')}</p>
        </section>
      ) : null}
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <SourceFold paths={[art('99'), art('100'), art(licence === 'probation' ? '23' : '27'), art('35'), art('33'),
                            ...(after === 0 ? [art('22'), art('24'), art('34')] : []), ...(twoThirds ? [art('26')] : [])]} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Listen text={[over, t('points.balance', { now, max }), under].filter(Boolean).join('. ')} lang={lang} />
          <Button href="https://infractionsroutieres.narsa.gov.ma/InfractionsRoutieres/" target="_blank" rel="noreferrer">{t('points.official')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
