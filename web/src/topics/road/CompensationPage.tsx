import { useState } from 'react';
import { Button, Note, PageSkeleton } from '@/shared/components/ui';
import { useRates } from '../kit/api';
import { KitPage } from '../kit/parts';
import { transition } from '../kit/motion';
import { AnswerCard, Listen, SourceFold } from '../kit/tool/parts';
import { dayWords } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { compensate, type Table } from './rules/compensation';
import { CapitalMap } from './CapitalMap';
import { FIELD } from './parts';
import { articleLabel, useRoadT } from './strings';
import { todayIso } from '@/shared/services/today';

const FROM = '2026-01-29';
const today = () => todayIso();
const STEPS = ['day', 'age', 'earnings', 'rate'] as const;

/** The permanent-incapacity indemnity under the 2026 table (R13 of the road plan; C1 of the road tools review): kept
 *  back until a lawyer has read its cases (Q5). Four short steps — the day, the age, the earnings, the doctor's rate —
 *  with the answer on top all along, then the table as a map with the reader's cell lit. Never a rate of its own. */
export default function CompensationPage({ slug }: { slug: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { maximumFractionDigits: 0 });
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const q = useRates(slug, 'capital');
  const [s, set] = useToolState({ d: today(), a: '30', e: '', r: '10' });
  const [at, setAt] = useState(0);
  const table = q.data?.rows?.[0]?.values as unknown as Table | undefined;
  if (!table) return <KitPage slug={slug} title={t('compensation.title')} lead={t('compensation.lead')}><PageSkeleton /></KitPage>;
  const age = Math.max(0, Math.min(120, Number(s.a) || 0)), earnings = Number(s.e) || 0, rate = Math.max(0, Math.min(100, Number(s.r) || 0));
  const before = s.d < FROM;
  const r = before ? null : compensate(table, s.d, age, earnings, rate);
  const go = (i: number) => transition(() => setAt(Math.max(0, Math.min(STEPS.length - 1, i))));
  const num = (key: 'a' | 'e' | 'r', label: string, max?: number, hint?: string) => (
    <label className="flex flex-col gap-1.5">
      <span className="text-lead font-semibold">{label}</span>
      <input type="number" inputMode="decimal" min={0} max={max} value={s[key]} autoFocus
             onChange={(e) => set({ [key]: e.target.value })} className={`${FIELD} text-lead`} dir="ltr" />
      {hint ? <span className="text-meta text-ink-soft">{hint}</span> : null}
    </label>
  );
  return (
    <KitPage slug={slug} title={t('compensation.title')} lead={t('compensation.lead')}>
      <Note tone="warn" quiet><p className="m-0 text-body">{t('compensation.review')}</p></Note>
      <AnswerCard share over={before || !r ? t('compensation.beforeOver') : t('compensation.indemnityAt', { rate })}
                  value={before || !r ? t('compensation.beforeValue') : r.indemnity} format={dh} tone={before ? 'warn' : 'stamp'}
                  under={r ? <p className="m-0">{t('compensation.capitalLine', { capital: dh(r.capital), age, earnings: dh(r.earnings) })}</p> : <p className="m-0">{t('compensation.before')}</p>} />
      <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <ol aria-label={t('compensation.steps')} className="m-0 flex list-none gap-1.5 p-0">
          {STEPS.map((k, i) => (
            <li key={k} className="flex-1">
              <button type="button" onClick={() => go(i)} aria-current={i === at ? 'step' : undefined}
                      className={`flex min-h-11 w-full flex-col items-center justify-center gap-1 text-meta ${i === at ? 'font-semibold text-ink' : 'text-ink-soft'}`}>
                <span className={`block h-1.5 w-full rounded-full ${i <= at ? 'bg-[var(--t)]' : 'bg-rule'}`} />{t(`compensation.stepNames.${k}`)}
              </button>
            </li>
          ))}
        </ol>
        <div key={at} className="motion-safe:animate-[rise_220ms_ease-out_both]">
          {at === 0 ? (
            <label className="flex flex-col gap-1.5">
              <span className="text-lead font-semibold">{t('compensation.day')}</span>
              <input type="date" value={s.d} min="2000-01-01" max={today()} onChange={(e) => e.target.value && set({ d: e.target.value })} className={FIELD} dir="ltr" />
              <span className="text-meta text-ink-soft">{dayWords(s.d, lang)}</span>
            </label>
          ) : at === 1 ? num('a', t('compensation.age'), 120)
            : at === 2 ? num('e', t('compensation.earnings'), undefined, t('compensation.earningsHint'))
              : num('r', t('compensation.rate'), 100, t('compensation.doctor'))}
        </div>
        <div className="flex gap-2">
          {at > 0 ? <Button onClick={() => go(at - 1)}>{t('compensation.back')}</Button> : null}
          {at < STEPS.length - 1 ? <Button variant="primary" onClick={() => go(at + 1)}>{t('compensation.next')}</Button> : null}
        </div>
      </section>
      {r ? (
        <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
          <h2 className="m-0 text-lead font-semibold">{t('compensation.where')}</h2>
          <CapitalMap table={table} result={r} age={age} />
          <p className="m-0 text-meta text-ink-soft">{t('compensation.rows', { rows: r.rows.map((x) => `${nf.format(x.earnings)} → ${nf.format(x.capital)}${x.page ? ` (ص. ${x.page})` : ''}`).join('، ') })}</p>
          {r.rows.length > 1 ? <p className="m-0 text-meta text-ink-soft">{t('compensation.between')}</p> : null}
          <p className="m-0 text-meta text-ink-soft">{t('compensation.minimum', { amount: dh(r.minimum) })} · {t('compensation.floor', { amount: dh(r.pointFloor) })}</p>
          {r.misprint ? <Note tone="warn" quiet><p className="m-0 text-body">{t('compensation.misprint', { printed: nf.format(r.misprint.printed), steps: nf.format(r.misprint.steps), page: r.misprint.page })}</p></Note> : null}
        </section>
      ) : null}
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body">{t('compensation.doctor')}</p>
        <SourceFold paths={['/ma/dahir/1-84-177/art_5', '/ma/dahir/1-84-177/art_9', '/ma/dahir/1-84-177/art_6', '/ma/loi/70-24/art_5', '/ma/loi/70-24/art_7', '/ma/loi/70-24/annex']} label={articleLabel} />
        {r ? <Listen text={[t('compensation.indemnityAt', { rate }), dh(r.indemnity), t('compensation.capitalLine', { capital: dh(r.capital), age, earnings: dh(r.earnings) })].join('. ')} lang={lang} /> : null}
      </section>
    </KitPage>
  );
}
