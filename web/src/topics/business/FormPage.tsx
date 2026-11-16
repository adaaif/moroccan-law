import { Button } from '@/shared/components/ui';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold, SourceMark } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { ARTICLE as LISTED, find } from './rules/excluded';
import { ARTICLES, CEILING, forms, type Activity, type Form, type Who } from './rules/form';
import { MoneyField, Sheet, StampCard } from './parts';
import { articleLabel, useBusinessT, useMoney } from './strings';

/** «مقاول ذاتي، تاجر، ولا شركة؟» (the business review): alone or not, the activity, the year's turnover, a trade
 *  typed → the four forms the texts set, each pressed as a stamp when the law opens it to the reader, crossed with its
 *  reason when it does not, and under each what it obliges (the register, the books, what answers for the debts). It
 *  says what the law permits, never which to choose. It waits for a person's check. The inputs live in the address. */
export default function FormPage({ slug }: { slug: string }) {
  const { t, i18n } = useBusinessT();
  const money = useMoney();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ w: 'alone', a: 'trade', r: '120000', q: '' });
  const who = (['alone', 'few', 'five'].includes(s.w) ? s.w : 'alone') as Who;
  const activity = (s.a === 'service' ? 'service' : 'trade') as Activity;
  const turnover = Math.max(0, Number(s.r) || 0);
  const listed = s.q.trim() ? find(s.q) : [];
  const options = forms(who, activity, turnover, listed.length > 0);
  const open = options.filter((o) => o.open);
  const name = (f: Form) => t(`form.forms.${f}.name`);
  return (
    <KitPage slug={slug} title={t('form.title')} lead={t('form.lead')}>
      <AnswerCard share over={t('form.over')} value={open.map((o) => name(o.form)).join(lang === 'fr' ? ', ' : '، ')}
                  under={<p className="m-0">{t('form.under')}</p>} />

      <Sheet>
        <Chips label={t('form.who')} value={who} onChange={(w) => set({ w })}
               options={(['alone', 'few', 'five'] as Who[]).map((k) => ({ key: k, label: t(`form.whos.${k}`) }))} />
        <Chips label={t('form.activity')} value={activity} onChange={(a) => set({ a })}
               options={(['trade', 'service'] as Activity[]).map((k) => ({ key: k, label: t(`form.activities.${k}`) }))} />
        <MoneyField label={t('form.turnover')} value={s.r} onChange={(r) => set({ r })}
                    note={t('form.turnoverNote', { cap: money(CEILING[activity]) })} />
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('form.trade')}</span>
          <input type="search" dir="auto" value={s.q} onChange={(e) => set({ q: e.target.value })} placeholder={t('form.tradeHint')}
                 className="h-12 w-full max-w-sm rounded-control border border-field bg-sheet px-3 text-body" />
          {s.q.trim() ? (
            listed.length ? (
              <span className="flex flex-col gap-1.5 pt-1">
                <span className="text-meta font-semibold" style={{ color: 'var(--color-sign-red)' }}>{t('form.listed', { count: listed.length })}</span>
                <span className="flex flex-wrap gap-1.5">
                  {listed.map((x) => <span key={x} lang="ar" dir="rtl" className="rounded-full border border-field px-3 py-1 text-meta">{x}</span>)}
                </span>
                <SourceMark path={LISTED} label={articleLabel(LISTED)} />
              </span>
            ) : <span className="text-meta text-ink-soft">{t('form.notListed')}</span>
          ) : <span className="text-meta text-ink-soft">{t('form.tradeNote')}</span>}
        </label>
      </Sheet>

      <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2">
        {options.map((o) => (
          <li key={o.form}>
            <StampCard title={name(o.form)} open={o.open} stamp={o.open ? t('form.allowed') : t('form.closed')}
                       reason={o.why ? t(`form.why.${o.why}`, { cap: money(CEILING[activity]) }) : undefined}
                       chip={<SourceMark path={o.path} label={articleLabel(o.path)} />}
                       lines={(['register', 'books', 'debts'] as const).map((k) => ({ key: k, label: t(`form.rows.${k}`), text: t(`form.forms.${o.form}.${k}`) }))} />
          </li>
        ))}
      </ul>

      <Sheet>
        <p className="m-0 text-meta text-ink-soft">{t('form.never')}</p>
        <SourceFold paths={Object.values(ARTICLES)} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, 'pages/forms')}>{t('form.toPage')}</Button>
          <Button variant="quiet" to={refPath(slug, 'journeys/auto-start')}>{t('form.toAuto')}</Button>
          <Button variant="quiet" to={refPath(slug, 'journeys/sarl-start')}>{t('form.toSarl')}</Button>
          <Button variant="quiet" to={refPath(slug, 'tax:tools/own')}>{t('form.toTax')}</Button>
        </div>
      </Sheet>
    </KitPage>
  );
}
