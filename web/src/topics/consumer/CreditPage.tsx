import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, DayChips, Listen, SourceFold } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { DayStrip } from './parts';
import { windowDays } from './rules/withdrawal';
import { ceilings, withdrawBy, type Loan } from './rules/credit';
import { articleLabel, useConsumerT } from './strings';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();
const FIELD = 'h-12 w-full max-w-64 rounded-control border border-field bg-sheet px-3 text-body tabular-nums';

/** «الكريدي» (T4 of the consumer plan): three questions on one page — the last day to withdraw, what repaying
 *  early costs, and the most a lender may ask when payments stop — each answered with the law's ceilings worked out in
 *  dirhams from the figures the reader types. The figures stay on the phone. It never says whether to borrow or pay. */
export default function CreditPage({ slug }: { slug: string }) {
  const { t, i18n } = useConsumerT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { maximumFractionDigits: 2 });
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const [s, set] = useToolState({ q: 'withdraw', loan: 'consumer', d: today(), k: '', u: '', def: '' });
  const loan = (s.loan === 'home' ? 'home' : 'consumer') as Loan;
  const q = ['withdraw', 'early', 'default'].includes(s.q) ? s.q : 'withdraw';
  const k = Number(s.k) || 0, u = Number(s.u) || 0, def = Number(s.def) || 0;
  const c = ceilings(loan, k, u, def);
  const last = withdrawBy(s.d);

  let over = '', value: string | number = '', under = '', tone: 'stamp' | 'warn' | 'good' = 'stamp';
  if (q === 'withdraw') {
    if (loan === 'home') { over = t('credit.homeOfferOver'); value = t('credit.homeOffer'); under = t('credit.homeOfferLine'); }
    else {
      const left = daysUntil(last);
      over = t('credit.withdrawOver'); value = dayWords(last, lang);
      under = left < 0 ? t('credit.passed') : t('credit.left', { count: left }); if (left < 0) tone = 'warn';
    }
  } else if (q === 'early') {
    over = t('credit.earlyOver');
    value = loan === 'home' ? (k ? dh(c.early) : t('credit.atMost2')) : t('credit.free');
    under = loan === 'home' ? t('credit.earlyHome') : t('credit.earlyConsumer'); if (loan === 'consumer') tone = 'good';
  } else {
    over = t('credit.defaultOver');
    value = k ? dh(c.lateInterest) : loan === 'home' ? t('credit.atMost2') : t('credit.atMost4');
    under = loan === 'home' ? t('credit.defaultHome') : t('credit.defaultConsumer', { indemnity: c.indemnity !== null && (u || def) ? dh(c.indemnity) : t('credit.atMost4Inst') });
  }
  const shown = typeof value === 'number' ? dh(value) : value;
  const message = [t('credit.message'), t(`credit.qs.${q}`), `${over}: ${shown}`, under, here()].join('\n');

  return (
    <KitPage slug={slug} title={t('credit.title')} lead={t('credit.lead')}>
      <AnswerCard over={over} value={shown} under={<p className="m-0">{under}</p>} tone={tone}>
        {q === 'withdraw' && loan === 'consumer' ? <div className="pt-2"><DayStrip days={windowDays(s.d, 7)} today={today()} /></div> : null}
      </AnswerCard>

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('credit.question')} value={q} onChange={(v) => set({ q: v })}
               options={['withdraw', 'early', 'default'].map((x) => ({ key: x, label: t(`credit.qs.${x}`) }))} />
        <Chips label={t('credit.kind')} value={loan} onChange={(v) => set({ loan: v })}
               options={[{ key: 'consumer', label: t('credit.consumer') }, { key: 'home', label: t('credit.home') }]} />
        {q === 'withdraw' && loan === 'consumer' ? <DayChips label={t('credit.accepted')} value={s.d} onChange={(d) => set({ d })} ago={[0, 1, 3, 6]} /> : null}
        {q !== 'withdraw' ? (
          <label className="flex flex-col gap-1.5 text-body font-semibold">{t('credit.capital')}
            <input type="number" inputMode="decimal" min={0} value={s.k} placeholder="0" onChange={(e) => set({ k: e.target.value })} className={FIELD} />
          </label>
        ) : null}
        {q === 'default' && loan === 'consumer' ? (
          <>
            <label className="flex flex-col gap-1.5 text-body font-semibold">{t('credit.unpaid')}
              <input type="number" inputMode="decimal" min={0} value={s.u} placeholder="0" onChange={(e) => set({ u: e.target.value })} className={FIELD} />
            </label>
            <label className="flex flex-col gap-1.5 text-body font-semibold">{t('credit.deferred')}
              <input type="number" inputMode="decimal" min={0} value={s.def} placeholder="0" onChange={(e) => set({ def: e.target.value })} className={FIELD} />
              <span className="text-meta font-normal text-ink-soft">{t('credit.deferredHint')}</span>
            </label>
          </>
        ) : null}
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        {q === 'default' ? <p className="m-0 text-body">{t('credit.defaultWhen')}</p> : null}
        {q === 'default' ? <p className="m-0 text-body">{t('credit.nothingElse')}</p> : null}
        {q === 'default' && loan === 'consumer' ? <p className="m-0 text-body">{t('credit.court')}</p> : null}
        <Note tone="law" quiet><p className="m-0 text-meta">{t(q === 'default' && loan === 'consumer' ? 'credit.orderNote' : 'credit.ceilingNote')}</p></Note>
        <SourceFold paths={q === 'withdraw' ? (loan === 'home' ? ['/ma/loi/31-08/art_120', '/ma/loi/31-08/art_121'] : ['/ma/loi/31-08/art_85', '/ma/loi/31-08/art_87', '/ma/loi/31-08/art_97', '/ma/loi/31-08/art_203'])
          : q === 'default' && loan === 'consumer' ? [...c.cites, '/ma/loi/31-08/art_111', '/ma/loi/31-08/art_149'] : c.cites} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
          {q === 'withdraw' && loan === 'consumer' && daysUntil(last) >= 0 ? (
            <Button onClick={() => calendarFile([{ date: last, title: t('credit.remindTitle'), detail: here() }], 'credit')}>{t('remind')}</Button>
          ) : null}
          <Button to={`/topics/${slug}/journeys/${loan === 'home' ? 'home-loan' : 'credit'}`}>{t('credit.toJourney')}</Button>
          <Listen text={[over, shown, under].join('. ')} lang={lang} />
        </div>
      </section>
    </KitPage>
  );
}
