import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, Listen, SourceMark } from '../kit/tool/parts';
import { dayWords } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { MARGINS_PATH, PRESENTATIONS, SUGAR_ORDERS, inForce, sugarOn, type Presentation } from './rules/sugar';
import { useSugar } from './rules/rates';
import { articleLabel, useConsumerT } from './strings';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();

/** «الثمن اللي حددات الدولة» (T7 of the consumer plan, K4): sugar's maximum price by presentation on a day, from
 *  the order in force then; what a wholesaler and a retailer may add on it, in dirhams; and the price over the years,
 *  each year its order. Medicines wait for a person's check of the price list (K4). */
export default function PricesPage({ slug }: { slug: string }) {
  const { t, i18n } = useConsumerT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const rows = useSugar(slug);
  const years = [...rows].sort((a, b) => a.from.localeCompare(b.from));
  const [s, set] = useToolState({ p: 'g1', on: today() });
  const p = (PRESENTATIONS.some((x) => x.key === s.p) ? s.p : 'g1') as Presentation;
  const price = sugarOn(rows, s.on, p);
  const row = inForce(rows, s.on);
  const order = row ? SUGAR_ORDERS[row.from] : undefined;
  // The bars run from the lowest price to the highest: the prices differ by a few hundredths, a bar from zero hides it.
  const known = years.map((r) => r.values[p]).filter((v): v is number => v !== undefined);
  const lo = Math.min(...known), hi = Math.max(...known);
  const width = (v: number) => (hi > lo ? 25 + (75 * (v - lo)) / (hi - lo) : 100);
  const under = price?.total ? t('prices.withMargins', { wholesale: dh(price.wholesale!), retail: dh(price.retail!), total: dh(price.total) }) : t('prices.noMargins');
  const message = [t('prices.message'), t(`prices.p.${p}`), price ? `${t('prices.factory')}: ${dh(price.factory)}` : '', price?.total ? under : '', here()].filter(Boolean).join('\n');
  return (
    <KitPage slug={slug} title={t('prices.title')} lead={t('prices.lead')}>
      <AnswerCard over={t('prices.over', { what: t(`prices.p.${p}`), date: dayWords(s.on, lang, true) })}
                  value={price ? dh(price.factory) : t('prices.none')} under={<p className="m-0">{price ? under : t('prices.before')}</p>}>
        {order ? <p className="m-0 text-meta text-ink-soft">{t('prices.order', { order: order.order, issue: order.issue, date: dayWords(row!.from, lang) })}</p> : null}
      </AnswerCard>

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('prices.what')} value={p} onChange={(v) => set({ p: v })}
               options={PRESENTATIONS.map((x) => ({ key: x.key, label: t(`prices.p.${x.key}`) }))} />
        <Chips label={t('prices.when')} value={years.some((r) => r.from === s.on) ? s.on : today()}
               onChange={(v) => set({ on: v })}
               options={[{ key: today(), label: t('prices.today') }, ...years.slice(0, -1).reverse().map((r) => ({ key: r.from, label: r.from.slice(0, 4) }))]} />
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-labelledby="years">
        <h2 id="years" className="m-0 text-lead font-semibold">{t('prices.years')}</h2>
        <ol className="m-0 flex list-none flex-col gap-2 p-0">
          {years.map((r) => {
            const v = r.values[p];
            const o = SUGAR_ORDERS[r.from];
            return (
              <li key={r.from} className="flex flex-col gap-1">
                <div className="flex items-baseline justify-between gap-2 text-meta">
                  <span className="font-semibold">{t('prices.from', { date: dayWords(r.from, lang) })}</span>
                  <span className="tabular-nums">{v !== undefined ? dh(v) : '—'}</span>
                </div>
                <div className="h-3 rounded-full bg-rule">
                  <div className="h-full rounded-full bg-[var(--t)] transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${v ? width(v) : 0}%` }} />
                </div>
                {o ? <span className="text-meta text-ink-soft">{t('prices.byOrder', { order: o.order, issue: o.issue })}</span> : null}
              </li>
            );
          })}
        </ol>
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Note tone="law" quiet><p className="m-0 text-meta">{t('prices.notice')}</p></Note>
        <p className="m-0 text-meta text-ink-soft">{t('prices.medicines')}</p>
        <span className="flex flex-wrap gap-1.5">
          {order ? <SourceMark path={order.path} label={articleLabel(order.path)} /> : null}
          <SourceMark path={MARGINS_PATH} label={t('prices.marginsLabel')} />
          <SourceMark path="/ma/loi/104-12/art_2" label={articleLabel('/ma/loi/104-12/art_2')} />
        </span>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
          <Listen text={[t(`prices.p.${p}`), price ? dh(price.factory) : '', price?.total ? under : ''].join('. ')} lang={lang} />
        </div>
      </section>
    </KitPage>
  );
}
