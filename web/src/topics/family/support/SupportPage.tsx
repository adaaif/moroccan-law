import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../../kit/parts';
import { AnswerCard, Chips } from '../../kit/tool/parts';
import { useFamilyT } from '../strings';
import { AMOUNTS, MAX_CHILDREN, PERIODS, periodOn, SEPTEMBER, SOURCES, support, type Child, type Period } from './rules';
import { todayIso } from '@/shared/services/today';

/** «الدعم المباشر للأطفال» (F10 of the family plan): the amount the decree fixes for an eligible family, line by line
 *  with its source, the September grant apart. Whether a family is eligible is the state's to say. */
export default function SupportPage({ slug }: { slug: string }) {
  const { t, i18n } = useFamilyT();
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA');
  const [period, setPeriod] = useState<Period>(() => periodOn(todayIso()));
  const [children, setChildren] = useState<Child[]>([{ status: 'schooled', level: 'primary', disabled: false, orphan: false }]);
  const s = support(children, period);
  const a = AMOUNTS[period];
  const edit = (i: number, c: Partial<Child>) => setChildren(children.map((x, j) => (j === i ? { ...x, ...c } : x)));
  const dh = (n: number) => t('support.dh', { amount: nf.format(n) });
  return (
    <KitPage slug={slug} title={t('support.title')} lead={t('support.lead')}>
      {/* The answer on top, the children touched in below (G13 of the family-papers review). */}
      <AnswerCard share over={t('support.monthly')} value={s.monthly} format={dh}
                  under={s.september.total ? <span>{t('support.september')}: {dh(s.september.total)}</span> : undefined} />
      <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('support.year')} value={period} onChange={setPeriod}
               options={PERIODS.map((p) => ({ key: p.key, label: t(`support.periods.${p.key}`) }))} />
        <div className="flex flex-col gap-1">
          <h2 className="m-0 text-lead font-semibold">{t('support.children')}</h2>
          <p className="m-0 text-meta text-ink-soft">{t('support.childrenLead')}</p>
        </div>
        <ol className="m-0 flex list-none flex-col gap-3 p-0">
          {children.map((c, i) => (
            <li key={i} className="flex flex-col gap-2 rounded-control bg-paper px-4 py-3">
              <div className="flex items-center justify-between">
                <span className="text-body font-semibold">{t('support.child', { n: i + 1 })}</span>
                <Button variant="quiet" onClick={() => setChildren(children.filter((_, j) => j !== i))}>{t('support.remove')}</Button>
              </div>
              <Chips value={c.status} onChange={(status) => edit(i, { status, level: status === 'schooled' ? c.level : 'none' })}
                     options={(['schooled', 'notSchooled'] as const).map((k) => ({ key: k, label: t(`support.status.${k}`) }))} />
              {c.status === 'schooled' ? (
                <Chips value={c.level} onChange={(level) => edit(i, { level })}
                       options={(['none', 'primary', 'upper'] as const).map((l) => ({ key: l, label: t(`support.level.${l}`) }))} />
              ) : null}
              <div className="flex flex-wrap gap-x-5">
                <label className="inline-flex min-h-11 items-center gap-2"><input type="checkbox" checked={c.disabled} onChange={() => edit(i, { disabled: !c.disabled })} className="size-5" />{t('support.disabled')}</label>
                <label className="inline-flex min-h-11 items-center gap-2"><input type="checkbox" checked={c.orphan} onChange={() => edit(i, { orphan: !c.orphan })} className="size-5" />{t('support.orphan')}</label>
              </div>
            </li>
          ))}
        </ol>
        {children.length < MAX_CHILDREN ? (
          <Button className="self-start" onClick={() => setChildren([...children, { status: 'schooled', level: 'none', disabled: false, orphan: false }])}>{t('support.add')}</Button>
        ) : null}
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-live="polite">
        <ul className="m-0 flex list-none flex-col gap-1 p-0 text-body">
          {s.flat ? <li>{t('support.line.flat')}</li> : null}
          {s.first.schooled ? <li>{t('support.line.first', { n: s.first.schooled, amount: a.first.schooled })}</li> : null}
          {s.first.notSchooled ? <li>{t('support.line.first', { n: s.first.notSchooled, amount: a.first.notSchooled })}</li> : null}
          {s.later.schooled ? <li>{t('support.line.later', { n: s.later.schooled, amount: a.later.schooled })}</li> : null}
          {s.later.notSchooled ? <li>{t('support.line.later', { n: s.later.notSchooled, amount: a.later.notSchooled })}</li> : null}
          {s.supplement ? <li>{t('support.line.supplement', { n: s.supplement, amount: a.supplement })}</li> : null}
          {s.raised ? <li>{t('support.line.floor')}</li> : null}
        </ul>
        {s.supplement ? <p className="m-0 text-meta text-ink-soft">{t('support.supplementNote')}</p> : null}
        {s.september.total ? (
          <div className="flex flex-col gap-1 border-t border-rule pt-3">
            <p className="m-0 text-meta font-semibold text-ink-soft">{t('support.september')}</p>
            <p className="m-0 text-lead font-semibold">{dh(s.september.total)}</p>
            {s.september.primary ? <p className="m-0 text-meta">{t('support.septemberLine', { n: s.september.primary, amount: SEPTEMBER.primary })}</p> : null}
            {s.september.upper ? <p className="m-0 text-meta">{t('support.septemberLine', { n: s.september.upper, amount: SEPTEMBER.upper })}</p> : null}
            <p className="m-0 text-meta text-ink-soft">{t('support.septemberNote')}</p>
          </div>
        ) : null}
        <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
          {Object.values(SOURCES).map((x) => (
            <li key={x.path}><Link to={x.path} lang="ar" dir="rtl" className="inline-flex min-h-9 items-center rounded-full bg-wash px-3 text-meta text-stamp no-underline">{x.label}</Link></li>
          ))}
        </ul>
      </section>
      <Note tone="warn" quiet>
        <p className="m-0 text-meta">{t('support.eligibility')}</p>
        <p className="m-0 text-meta">{t('support.noCumul')}</p>
        <p className="m-0 text-meta">{t('support.birth')}</p>
      </Note>
    </KitPage>
  );
}
