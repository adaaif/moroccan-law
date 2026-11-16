import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold, SourceMark } from '../kit/tool/parts';
import { dayWords } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { DateField } from '../papers/parts';
import { ARTICLES, MAX_TERM, MONTHLY, SPARED, due, fine, monthsLate, start } from './rules/late';
import { MoneyField, Sheet } from './parts';
import { articleLabel, useBusinessT, useMoney } from './strings';

/** Bank Al-Maghrib's key rate, as its page of monetary policy decisions gave it on 27 Oct 2026 (2.25 % since the
 *  decision of 20 March 2025; kept at data/sources/bkam/key_rate_history_2026-10-27.html). The reader may change it. */
const KEY_RATE = '2.25';

/** «الفاتورة تعطلات: شحال الغرامة؟» (the business review): the invoice's date (and the delivery's, when the invoice
 *  came after its month), the agreed term, the day paid, the sum with tax → the last day to pay, the months begun late,
 *  and the fine owed to the Treasury, month by month on the invoice's own lines (the commerce code arts 78-1 to 78-6). It
 *  waits for a person's check. The inputs live in the address. */
export default function LatePage({ slug }: { slug: string }) {
  const { t, i18n } = useBusinessT();
  const money = useMoney();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const today = todayIso();
  const [s, set] = useToolState({ b: 'yes', i: today, l: '', t: '', p: '', m: '100000', k: KEY_RATE });
  const agreed = s.t === '' ? null : Math.max(0, Number(s.t) || 0);
  const last = due(s.i, s.l || null, agreed);
  const paid = s.p || today;
  const months = monthsLate(last, paid);
  const amount = Math.max(0, Number(s.m) || 0);
  const rate = Math.max(0, Number(s.k.replace(',', '.')) || 0);
  const f = fine(amount, months, rate);
  const spared = s.b === 'no';
  const from = start(s.i, s.l || null);

  return (
    <KitPage slug={slug} title={t('late.title')} lead={t('late.lead')}>
      {spared ? (
        <AnswerCard share over={t('late.sparedOver')} value={t('late.spared')} tone="good"
                    under={<p className="m-0">{t('late.sparedUnder', { amount: money(SPARED) })} <SourceMark path={ARTICLES.who} label={articleLabel(ARTICLES.who)} /></p>} />
      ) : (
        <AnswerCard over={months ? t('late.fineOver') : t('late.dueOver')} tone={months ? 'warn' : 'stamp'}
                    value={months ? money(f.total) : dayWords(last, lang)}
                    under={<p className="m-0">{months ? t('late.fineUnder', { date: dayWords(last, lang), count: months }) : t('late.onTime', { date: dayWords(last, lang) })}</p>} />
      )}

      <Sheet>
        <Chips label={t('late.big')} value={spared ? 'no' : 'yes'} onChange={(b) => set({ b })}
               options={[{ key: 'yes', label: t('late.bigYes', { amount: money(SPARED) }) }, { key: 'no', label: t('late.bigNo', { amount: money(SPARED) }) }]} />
        <DateField label={t('late.invoice')} value={s.i} onChange={(i) => set({ i })} lang={lang} />
        <Chips label={t('late.sameMonth')} value={s.l ? 'no' : 'yes'} onChange={(v) => set({ l: v === 'no' ? (s.l || s.i) : '' })}
               options={[{ key: 'yes', label: t('late.sameMonthYes') }, { key: 'no', label: t('late.sameMonthNo') }]} />
        {s.l ? <DateField label={t('late.delivered')} value={s.l} onChange={(l) => set({ l })} lang={lang} note={t('late.deliveredNote')} /> : null}
        <Chips label={t('late.term')} value={s.t === '' ? 'none' : 'agreed'} onChange={(v) => set({ t: v === 'none' ? '' : (s.t || '90') })}
               options={[{ key: 'none', label: t('late.termNone') }, { key: 'agreed', label: t('late.termAgreed') }]} />
        {s.t !== '' ? (
          <label className="flex flex-col gap-1.5">
            <span className="text-body font-semibold">{t('late.termDays')}</span>
            <input type="number" inputMode="numeric" min={0} value={s.t} onChange={(e) => set({ t: e.target.value })}
                   className="h-12 w-32 rounded-control border border-field bg-sheet px-3 text-body tabular-nums" dir="ltr" />
            <span className={`text-meta ${agreed != null && agreed > MAX_TERM ? 'font-semibold' : 'text-ink-soft'}`}
                  style={agreed != null && agreed > MAX_TERM ? { color: 'var(--color-sign-red)' } : undefined}>
              {agreed != null && agreed > MAX_TERM ? t('late.termOver', { max: MAX_TERM }) : t('late.termNote', { max: MAX_TERM })}
            </span>
          </label>
        ) : null}
        <Chips label={t('late.paidQ')} value={s.p ? 'yes' : 'no'} onChange={(v) => set({ p: v === 'yes' ? (s.p || today) : '' })}
               options={[{ key: 'no', label: t('late.paidNo') }, { key: 'yes', label: t('late.paidYes') }]} />
        {s.p ? <DateField label={t('late.paidOn')} value={s.p} onChange={(p) => set({ p })} lang={lang} /> : null}
        <MoneyField label={t('late.amount')} value={s.m} onChange={(m) => set({ m })} note={t('late.amountNote')} />
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('late.rate')}</span>
          <input type="text" inputMode="decimal" value={s.k} onChange={(e) => set({ k: e.target.value })}
                 className="h-12 w-28 rounded-control border border-field bg-sheet px-3 text-body tabular-nums" dir="ltr" />
          <span className="text-meta text-ink-soft">{t('late.rateNote')}</span>
        </label>
      </Sheet>

      {spared ? null : (
        <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-5 sm:px-7">
          <h2 className="m-0 text-h3 font-bold">{t('late.linesTitle')}</h2>
          <dl className="m-0 grid gap-x-4 gap-y-2" style={{ gridTemplateColumns: '1fr auto' }}>
            <dt className="text-body">{t('late.from', { date: dayWords(from, lang) })}</dt>
            <dd className="m-0 text-body font-semibold tabular-nums">{dayWords(last, lang)}</dd>
            <dt className="text-body">{t('late.first', { rate: s.k })}</dt>
            <dd className="m-0 text-body font-semibold tabular-nums">{money(f.first)}</dd>
            <dt className="text-body">{t('late.rest', { count: Math.max(0, months - 1), rate: (MONTHLY * 100).toLocaleString(lang === 'fr' ? 'fr-FR' : 'de-DE') })}</dt>
            <dd className="m-0 text-body font-semibold tabular-nums">{money(f.rest)}</dd>
            <dt className="border-t border-rule pt-2 text-body font-bold">{t('late.total')}</dt>
            <dd className="m-0 border-t border-rule pt-2 text-body font-bold tabular-nums">{money(f.total)}</dd>
          </dl>
          <p className="m-0 pt-2 text-meta text-ink-soft">{t('late.treasury')}</p>
        </section>
      )}

      <Sheet>
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
          {(['declare', 'sanction', 'court', 'claim'] as const).map((k) => <li key={k} className="text-body">• {t(`late.law.${k}`)}</li>)}
        </ul>
        <SourceFold paths={Object.values(ARTICLES)} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, 'journeys/late-payment')}>{t('late.toJourney')}</Button>
          <Button variant="quiet" to={refPath(slug, 'pages/terms')}>{t('late.toPage')}</Button>
        </div>
      </Sheet>
    </KitPage>
  );
}
