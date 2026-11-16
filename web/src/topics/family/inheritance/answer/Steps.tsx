import type { ReactNode } from 'react';
import type { Case } from '../case';
import type { Cite, Heir } from '../engine';
import { ONE, sub, sum, type Q } from '../frac';
import Cites from '../parts/Cites';
import { midKin, sayShare } from '../parts/say';
import { useT } from '../strings';
import { tableOf } from '../table';
import Fold from './Fold';
import { BEQUEST_ARTS, branchName, groupName, laterName, NAMED_ART, type Ok } from './words';

/** «كيفاش حسبنا» (IR20 of the inheritance review), folded: the steps in the order an adoul takes them, each with its
 *  article and paragraph as a mark that opens it over the tool. Who is shut out and by whom; each fixed share; the
 *  base; the rise or the return; who takes the rest; the correction; the compulsory bequest's two stages; the will and
 *  the «تنزيل»; an heir who died since. Under each plain reason, the code's own wording when it says it otherwise. */
export default function Steps({ c, a }: { c: Case; a: Ok }) {
  const { t, i18n } = useT();
  const r = a.result;
  const tb = tableOf(r);
  const fixed = r.lines.filter((l) => l.basis !== 'asaba' && l.fard);
  const residue = r.lines.filter((l) => l.basis === 'asaba');
  const fards: Q = sum(fixed.map((l) => l.fard as Q));
  const rest = sub(ONE, fards);
  const last = tb.radd ?? tb.awl ?? tb.base;
  const law = (plain: string, key: string) => {
    const words = t(key, { defaultValue: '' });
    return words && words !== plain ? words : null;
  };
  const by = (h: Heir | 'rule') => (h === 'rule' ? '' : midKin(h, t, i18n.language));
  return (
    <Fold title={t('answer.steps.title')}>
      {r.named ? (
        <Step title={`${t('namedLead')}${t('answer.colon')}${t(`named.${r.named}`)}`} today={[NAMED_ART[r.named]]} />
      ) : null}

      {r.excluded.length ? (
        <Section title={t('answer.steps.out')}>
          {r.excluded.map((e) => {
            const plain = t(`out.${e.why}`, { by: by(e.by) });
            return <Step key={e.heir} title={groupName(e.heir, e.count, t)} plain={plain} law={law(plain, `lawOut.${e.why}`)} cites={e.cites} />;
          })}
        </Section>
      ) : null}

      {fixed.length ? (
        <Section title={t('answer.steps.fixed')}>
          {fixed.map((l) => {
            const plain = t(`why.${l.why}`);
            return <Step key={l.heir} title={groupName(l.heir, l.count, t)} plain={plain} law={law(plain, `lawWhy.${l.why}`)} cites={l.cites} />;
          })}
        </Section>
      ) : null}

      <Section title={t('answer.steps.base')}>
        <Step plain={t(fixed.length ? 'answer.steps.baseFixed' : 'answer.steps.baseHeads', { n: tb.base.toString() })} />
        {tb.awl ? <Step plain={t('answer.steps.awl', { base: tb.base.toString(), awl: tb.awl.toString() })}
                        today={r.named && ['akdariyya', 'mubahala', 'minbariyya'].includes(r.named) ? [NAMED_ART[r.named]] : undefined} /> : null}
        {r.radd && tb.radd ? (
          <Step plain={t('answer.steps.radd', { rest: sayShare(rest, t), n: tb.radd.toString() })} law={t('answer.law349')} lawLang="ar" today={[[349, 6]]} />
        ) : null}
      </Section>

      {residue.length ? (
        <Section title={t('answer.steps.rest')}>
          <Step plain={fixed.length ? t('answer.steps.restLine', { rest: sayShare(rest, t) }) : t('answer.steps.restAll')} />
          {residue.map((l) => {
            const plain = t(`why.${l.why}`);
            return <Step key={l.heir} title={groupName(l.heir, l.count, t)} plain={plain} law={law(plain, `lawWhy.${l.why}`)} cites={l.cites} />;
          })}
        </Section>
      ) : null}

      {tb.corrected !== last && tb.corrected % last === 0n ? (
        <Section title={t('answer.steps.tashih')}>
          <Step plain={t('answer.steps.tashihLine', { n: last.toString(), times: (tb.corrected / last).toString(), corrected: tb.corrected.toString() })} />
        </Section>
      ) : null}

      {r.bequest.length ? (
        <Section title={t('answer.steps.bequest')}>
          {r.bequest.map((b, n) => (
            <Step key={n} title={branchName(b, n, r.bequest, c.deceased, t)}
                  plain={`${t(`answer.steps.stage1_${b.sex}`, { share: sayShare(b.parent, t) })} ${t(`answer.steps.stage2_${b.sex}`, { part: sayShare(b.part, t), share: sayShare(b.share, t) })}`} />
          ))}
          {r.capped ? <Step plain={t('answer.bequest.capped')} /> : null}
          <Step plain={t('answer.bequest.court')} law={t('answer.law370')} lawLang="ar" today={BEQUEST_ARTS} />
        </Section>
      ) : null}

      {r.will || r.tanzil ? (
        <Section title={t('answer.steps.will')}>
          {r.will ? (
            <Step plain={t('answer.steps.willLine', { asked: sayShare(r.will.asked, t), granted: sayShare(r.will.granted, t) })}
                  cites={r.will.cut === 'heir' ? [280, 303] : [277, 302, 303]} />
          ) : null}
          {r.tanzil ? (
            <Step plain={`${t('answer.steps.tanzilLine', { asked: sayShare(r.tanzil.asked, t), granted: sayShare(r.tanzil.total, t) })} ${t(`answer.tanzil.${r.tanzil.by}`)}`}
                  cites={r.tanzil.by === 'rise' ? [315, [317, 1]] : [315, [317, 2], 318]} />
          ) : null}
        </Section>
      ) : null}

      {a.later.some((la) => !la.gone) ? (
        <Section title={t('answer.steps.later')}>
          {a.later.map((la, n) => (la.gone ? null : (
            <Step key={n} title={laterName(a, n, c.deceased, t)} plain={t('answer.steps.laterLine', { share: sayShare(la.share, t) })} />
          )))}
        </Section>
      ) : null}
    </Fold>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h4 className="m-0 text-body font-semibold text-ink-soft">{title}</h4>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">{children}</ul>
    </section>
  );
}

/** A step: who it is about, the plain reason, the code's own wording under it, the articles. */
function Step({ title, plain, law, lawLang, cites, today }: {
  title?: string; plain?: string; law?: string | null; lawLang?: 'ar'; cites?: Cite[];
  /** Articles written here in today's numbers (`Cites`). */
  today?: Cite[];
}) {
  const { t, i18n } = useT();
  const lang = lawLang ?? (i18n.language === 'fr' ? 'fr' : 'ar');
  return (
    <li className="flex flex-col gap-1.5">
      <p className="m-0 text-body">
        {title ? <span className="font-semibold">{title}</span> : null}
        {title && plain ? t('answer.colon') : ''}
        {plain}
      </p>
      {law ? (
        <p lang={lang} dir={lang === 'ar' ? 'rtl' : 'ltr'} className={`m-0 border-s-[3px] border-stamp-line ps-3 text-lead text-ink-soft ${lang === 'ar' ? 'font-law' : 'font-law-fr'}`}>
          <span className="sr-only">{t('answer.steps.law')}: </span>{law}
        </p>
      ) : null}
      {cites?.length || today?.length ? <Cites cites={cites} today={today} /> : null}
    </li>
  );
}
