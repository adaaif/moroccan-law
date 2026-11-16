import { reducedMotion } from '../../kit/motion';
import { useToolState } from '../../kit/tool/state';
import { num, scale, useWidth } from '../../kit/viz/viz';
import { useRateOn } from '../../kit/api';
import { todayIso } from '@/shared/services/today';
import { BILL_YEARS, useBillYears } from '../billYears';
import { useTaxT } from '../strings';
import './story.css';

const PEOPLE: { key: string; g: number; k: number }[] = [
  { key: 'clerk', g: 6500, k: 0 }, { key: 'teacher', g: 9000, k: 2 }, { key: 'nurse', g: 12000, k: 1 }, { key: 'engineer', g: 25000, k: 2 },
];

/** Takes the reader to the curve once it is drawn (a person picked lower on the page), its handle focused so the
 *  sentence is read out. */
function showCurve() {
  let tries = 0;
  const go = () => {
    const handle = document.querySelector<SVGGElement>('#st-curve .st-handle');
    if (!handle && tries++ < 30) { requestAnimationFrame(go); return; }
    document.getElementById('st-curve')?.scrollIntoView({ block: 'center', behavior: reducedMotion() ? 'auto' : 'smooth' });
    handle?.focus({ preventScroll: true });
  };
  requestAnimationFrame(go);
}

/** Four people, five years (Y3): each one's monthly gain year by year as bars on one scale for the four, so the
 *  clerk's 48 dirhams and the engineer's 3,079 are seen for what they are; left to right as every chart, the first year
 *  full, the later ones lighter; «ما بقاتش كتخلص» when the bill takes their whole tax away; a tap puts their salary and
 *  dependents into the page (the curve and the calculator follow) and takes the reader up to the curve, their column
 *  marked as the one shown. */
export function People({ slug }: { slug: string }) {
  const { t, i18n } = useTaxT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ g: '10000', k: '0' });
  // Four people, four computations: a fixed list, so each has its own hook.
  const all = [useBillYears(slug, PEOPLE[0].g, PEOPLE[0].k), useBillYears(slug, PEOPLE[1].g, PEOPLE[1].k),
    useBillYears(slug, PEOPLE[2].g, PEOPLE[2].k), useBillYears(slug, PEOPLE[3].g, PEOPLE[3].k)];
  const most = Math.max(1, ...all.flatMap((b) => b?.years.map((x) => x.gain) ?? []));
  return (
    <section className="st-block" aria-labelledby="st-people">
      <h2 id="st-people" className="st-q">{t('story.peopleTitle')}</h2>
      <p className="st-sub">{t('story.peopleSub')}</p>
      <ul className="st-people">
        {PEOPLE.map((p, i) => {
          const b = all[i];
          if (!b) return <li key={p.key} className="st-person st-wait" />;
          const gains = b.years.map((x) => x.gain);
          const freed = b.today.monthly.tax > 0 && b.years[0].r.monthly.tax === 0;
          return (
            <li key={p.key} className="st-person">
              <button type="button" aria-pressed={s.g === String(p.g) && s.k === String(p.k)} aria-label={t('story.pickPerson', { who: t(`story.who.${p.key}`) })}
                      onClick={() => { set({ g: String(p.g), k: String(p.k) }); showCurve(); }}>
                <span className="st-who">
                  <b>{t(`story.who.${p.key}`)}</b>
                  <span className="st-person-line">{t(p.k ? 'story.personLine' : 'story.personLineNone', { g: num(p.g, lang), count: p.k })}</span>
                </span>
                <span className="st-gain"><span className="st-person-big">+{num(gains[4], lang)}</span><small>{t('story.perMonth2031')}</small></span>
                {/* A chart: 2027 at the left on an Arabic page too. */}
                <span className="st-bars" dir="ltr" aria-hidden="true">
                  {gains.map((g, k) => (
                    <span key={k} className="st-bar-col">
                      <span className="st-bar-v">{num(g, lang)}</span>
                      <span className="st-bar" style={{ height: `${Math.max(2, (g / most) * 62)}px`, opacity: k ? 0.55 : 1 }} />
                    </span>
                  ))}
                </span>
                <span className="st-now">
                  <span className="st-years" dir="ltr" aria-hidden="true">{BILL_YEARS.map((y) => <span key={y}>{y}</span>)}</span>
                </span>
                <span className={`st-now${freed ? ' st-freed' : ''}`} style={{ gridArea: 'auto', gridColumn: '1 / -1' }}>
                  {freed ? t('story.freed') : t('story.today', { v: num(b.today.monthly.tax, lang) })}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="st-source">{t('story.source')}</p>
    </section>
  );
}

/** The road to 2031 (Y4): the top rate year by year as a stepped line, each year's rate and the income it starts at said
 *  on it; today's law in grey. Its title is its finding. The years run left to right, in Arabic too (the chart rule of
 *  1 Nov 2026). */
export function Road() {
  const { t, i18n } = useTaxT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const years = ['2026', ...BILL_YEARS];
  const rate = [37, 37, 37, 35, 30, 30];
  const from = [180000, 180000, 200000, 200000, 200000, 500000];
  if (width < 200) return <div ref={ref} className="st-block" />;
  const phone = width < 560;
  // «Aujourd’hui» is wider than a year's column on a phone: the year stands for it there, the grey band still says it.
  const today = phone && t('story.todayShort').length > 6 ? years[0] : t('story.todayShort');
  const h = phone ? 230 : 250, m = { t: 30, b: 40, s: 12 };
  const seg = (width - 2 * m.s) / years.length;
  const x = (i: number) => m.s + i * seg;
  const y = scale(25, 40, h - m.b, m.t);
  let d = '';
  years.forEach((_, i) => { d += `${i ? 'L' : 'M'}${x(i)},${y(rate[i])}L${x(i + 1)},${y(rate[i])}`; });
  return (
    <section className="st-block" aria-labelledby="st-road">
      <h2 id="st-road" className="st-q">{t('story.roadTitle')}</h2>
      <p className="st-sub">{t('story.roadSub')}</p>
      <div ref={ref} className="st-road">
        <svg style={{ direction: 'ltr' }} width={width} height={h} role="img" aria-label={t('story.roadAria', { list: rate.join('، ') })}>
          <rect x={Math.min(x(0), x(1))} y={m.t - 8} width={seg} height={h - m.t - m.b + 8} fill="var(--color-ink-soft)" opacity={0.07} />
          <path d={d} fill="none" stroke="var(--t)" strokeWidth={3.5} />
          {years.map((yr, i) => {
            const cx = (x(i) + x(i + 1)) / 2;
            return (
              <g key={yr}>
                <text x={cx} y={y(rate[i]) - 12} textAnchor="middle" className={`st-label${i ? ' st-strong' : ''}`}>{rate[i]}%</text>
                {!phone ? <text x={cx} y={y(rate[i]) + 22} textAnchor="middle" className="st-tick">{t('story.above', { v: num(from[i], lang) })}</text> : null}
                <text x={cx} y={h - 12} textAnchor="middle" className={i ? 'st-tick' : 'st-tick st-law'}>{i ? yr : today}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <p className="st-read"><b>{t('story.youMean')}</b> {t('story.roadMeans')}</p>
      <p className="st-source">{t('story.source')}</p>
    </section>
  );
}

/** «كيفاش حسبنا» (Y7): what the computation assumes, read from the rates the tools use, and where the speech's figures
 *  assume otherwise. */
export function Method({ slug }: { slug: string }) {
  const { t, i18n } = useTaxT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const cnss = useRateOn('work', 'cnss', todayIso());
  const family = useRateOn(slug, 'family', todayIso());
  return (
    <details className="st-method" id="method">
      <summary>{t('story.methodTitle')}</summary>
      <ul>
        <li>{t('story.m1')}</li>
        {cnss ? <li>{t('story.m2', { pension: (cnss.worker_long + cnss.worker_short + cnss.worker_ipe).toFixed(2).replace('.', ','), ceiling: num(cnss.ceiling, lang), amo: String(cnss.worker_amo).replace('.', ',') })}</li> : null}
        <li>{t('story.m3')}</li>
        {family ? <li>{t('story.m4', { per: num(family.per, lang), max: num(family.max, lang) })}</li> : null}
        <li>{t('story.m5')}</li>
        <li>{t('story.m6')}</li>
      </ul>
    </details>
  );
}
