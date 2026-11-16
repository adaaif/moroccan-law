import { useEffect } from 'react';
import { PageSkeleton } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { readDays, writeDays } from './keep';
import { allowance, pension } from './rules/cnss';
import { minimumMonthly } from './rules/pay';
import { Arts } from './parts';
import { useRateOn } from './rates';
import { useWorkT } from './strings';
import { todayIso } from '@/shared/services/today';

const MA_CNSS = 'https://www.macnss.ma/';
/** The track's end: 3,240 days give 50 %, each 216 more 1 %, up to 70 % (dahir arts 55–56). */
const CEILING_DAYS = 7560;

/** «أيامي فالضمان» (T11 of the work plan; E15 of the work-counted review): the CNSS counts in declared days, and every right
 *  has its threshold. One track from 0 to the 70 % ceiling, 1,320 and 3,240 marked, the reader's days set by a slider
 *  or typed from Ma CNSS; the pension's amount on top. The job-loss allowance as two short bars, 780 days in 36 months
 *  and 260 in the last 12, with its two conditions. The days are kept on the phone for the page's instrument. */
export default function CnssPage({ slug }: { slug: string }) {
  const { t, i18n } = useWorkT();
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const today = todayIso();
  const [s, set] = useToolState({ j: String(readDays() ?? 2400), a: '4000', x: '800', z: '270', i: '1', r: '0' });
  const days = Math.max(0, Math.min(15000, Number(s.j) || 0));
  useEffect(() => { writeDays(days); }, [days]);
  const rates = useRateOn(slug, 'pension', today);
  const ipe = useRateOn(slug, 'ipe', today);
  const smig = useRateOn(slug, 'smig', today);
  const smag = useRateOn(slug, 'smag', today);
  if (!rates || !ipe || !smig || !smag) return <KitPage slug={slug} title={t('cnss.title')} lead={t('cnss.lead')}><PageSkeleton /></KitPage>;
  const p = pension(days, Number(s.a) || 0, rates);
  const a = allowance(Number(s.x), Number(s.z), s.i === '1', s.r === '1', Number(s.a) || 0, minimumMonthly('nonfarm', smig.hour, smag.day), ipe);
  const missing = [a.missing36 ? t('cnss.missing36', { n: a.missing36 }) : '', a.missing12 ? t('cnss.missing12', { n: a.missing12 }) : '',
    s.i === '1' ? '' : t('cnss.notInvoluntary'), s.r === '1' ? '' : t('cnss.notRegistered')].filter(Boolean);
  const at = (d: number) => `${(Math.min(d, CEILING_DAYS) / CEILING_DAYS) * 100}%`;
  const card = 'flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7';
  return (
    <KitPage slug={slug} title={t('cnss.title')} lead={t('cnss.lead')}>
      <AnswerCard share over={t('cnss.over', { days })} tone={p.eligible ? 'stamp' : 'warn'}
                  value={p.eligible ? Math.round(p.amount * 100) : <span className="text-h3">{t('cnss.refundShort')}</span>}
                  format={(n) => dh(n / 100)}
                  under={p.eligible ? <span>{t('cnss.rateShort', { rate: nf.format(p.rate) })}</span> : <span>{t('cnss.toGo', { n: rates.min_days - days })}</span>} />

      <section className={card} aria-labelledby="track">
        <h2 id="track" className="m-0 text-lead font-semibold">{t('cnss.pension')}</h2>
        {/* The track: the reader's days filled, the band between 1,320 and 3,240 hatched (the rate grows with the days),
            the thresholds marked under it. Left to right on every page (HM34), its words in their own direction. */}
        <div className="relative h-5 rounded-control bg-rule" style={{ margin: '36px 8px 44px' }} aria-hidden="true" dir="ltr">
          <div className="absolute inset-y-0 rounded-control"
               style={{ insetInlineStart: at(rates.min_days), width: `calc(${at(rates.full_days)} - ${at(rates.min_days)})`, background: 'repeating-linear-gradient(135deg, transparent 0 4px, color-mix(in srgb, var(--t) 18%, transparent) 4px 8px)' }} />
          <div className="absolute inset-y-0 start-0 rounded-control bg-[var(--t)] transition-[width] duration-200 motion-reduce:transition-none" style={{ width: at(days) }} />
          {[rates.min_days, rates.full_days, CEILING_DAYS].map((d) => (
            <div key={d} className="absolute w-0.5 bg-ink" style={{ insetInlineStart: at(d), top: -8, bottom: -8 }}>
              <span style={{ top: 32 }} dir="auto" className="absolute -translate-x-1/2 whitespace-nowrap text-center text-meta leading-tight text-ink-soft">
                <b className="block tabular-nums text-ink">{d}</b>{d === rates.min_days ? t('cnss.opens') : d === rates.full_days ? '50%' : `${rates.max_rate}%`}
              </span>
            </div>
          ))}
          <span dir="auto" className="absolute -translate-x-1/2 whitespace-nowrap rounded-full bg-ink px-2.5 py-0.5 text-meta font-semibold text-sheet"
                style={{ left: at(days), top: -36 }}>{t('cnss.you', { days })}</span>
        </div>
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('cnss.days')}</span>
          <input type="range" dir="ltr" min={0} max={CEILING_DAYS} step={1} value={Math.min(days, CEILING_DAYS)} onChange={(e) => set({ j: e.target.value })}
                 style={{ accentColor: 'var(--t)' }} className="h-11 w-full" />
          <span className="flex flex-wrap items-center gap-2">
            <input type="number" inputMode="numeric" min={0} value={s.j} onChange={(e) => set({ j: e.target.value || '0' })} aria-label={t('cnss.days')}
                   className="h-12 w-32 rounded-control border border-field bg-sheet px-3 text-body tabular-nums" dir="ltr" />
            <a href={MA_CNSS} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center text-body font-medium">{t('cnss.readThem')}</a>
          </span>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('cnss.average')}</span>
          <input type="number" inputMode="decimal" min={0} value={s.a} onChange={(e) => set({ a: e.target.value || '0' })}
                 className="h-12 w-40 max-w-full rounded-control border border-field bg-sheet px-3 text-body tabular-nums" dir="ltr" />
        </label>
        {p.eligible ? (
          <p className="m-0 text-meta text-ink-soft">{t('cnss.rate', { rate: nf.format(p.rate), base: nf.format(p.base) })} = {nf.format(p.formula)} · {t('cnss.floor', { floor: p.floor })}</p>
        ) : <p className="m-0 text-body">{t('cnss.refund')}</p>}
        <Arts paths={['/ma/dahir/1-72-184/art_53', '/ma/dahir/1-72-184/art_55', '/ma/dahir/1-72-184/art_56', '/ma/decret/2-25-265/art_1', '/ma/decret/2-25-265/art_2']} />
      </section>

      <section className={card} aria-labelledby="ipe">
        <h2 id="ipe" className="m-0 text-lead font-semibold">{t('cnss.allowance')}</h2>
        <Bar label={t('cnss.days36')} need={ipe.days_36_months} value={Number(s.x)} max={936} onChange={(x) => set({ x: String(x) })} />
        <Bar label={t('cnss.days12')} need={ipe.days_12_months} value={Number(s.z)} max={312} onChange={(z) => set({ z: String(z) })} />
        <Chips label={t('cnss.involuntaryAsk')} value={s.i} onChange={(i) => set({ i })} options={[{ key: '1', label: t('cnss.yes') }, { key: '0', label: t('cnss.no') }]} />
        <Chips label={t('cnss.registeredAsk')} value={s.r} onChange={(r) => set({ r })} options={[{ key: '1', label: t('cnss.yes') }, { key: '0', label: t('cnss.no') }]} />
        <p className={`m-0 rounded-control px-4 py-3 text-body ${a.open ? '' : 'bg-amended-wash'}`} style={a.open ? { background: 'color-mix(in srgb, var(--color-in-force) 10%, var(--color-sheet))' } : undefined}>
          {a.open ? t('cnss.open', { amount: nf.format(a.amount), months: a.months }) : t('cnss.missing', { list: missing.join(t('cnss.sep')) })}
        </p>
        <Arts paths={['/ma/dahir/1-72-184/art_46-bis', '/ma/dahir/1-72-184/art_46-ter', '/ma/dahir/1-72-184/art_46-quater']} />
        <p className="m-0 text-meta text-ink-soft">{t('cnss.where')}</p>
      </section>
    </KitPage>
  );
}

/** A threshold: the days the dahir asks and the reader's against them, set by a slider in the colour of the verdict. */
function Bar({ label, need, value, max, onChange }: { label: string; need: number; value: number; max: number; onChange: (v: number) => void }) {
  const { t } = useWorkT();
  const ok = value >= need;
  return (
    <label className="flex flex-col gap-1">
      <span className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="text-body">{label}</span>
        <span className={`text-body font-semibold tabular-nums ${ok ? 'text-in-force' : 'text-amended'}`}>{t('cnss.ofNeed', { value, need })}{ok ? ' ✓' : ''}</span>
      </span>
      <input type="range" min={0} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))}
             style={{ accentColor: ok ? 'var(--t)' : 'var(--color-amended)' }} className="h-9 w-full" />
    </label>
  );
}
