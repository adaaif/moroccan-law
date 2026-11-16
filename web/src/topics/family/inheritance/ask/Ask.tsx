import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import Stepper from '../../../kit/tool/Stepper';
import type { Area } from '../area';
import { most, nobody, type Case } from '../case';
import type { Branch, Heir } from '../engine';
import { KIN, asked, siblingsForMother, skipped, steps, type Step } from '../flow';
import Cites from '../parts/Cites';
import { useT } from '../strings';
import { Choice, YesNo } from './controls';
import Kept from './Kept';
import { bare, codeWord, heirName, inSentence, type Sex } from './names';
import { FOLDED, ORDER, begin, move, restart, useProgress } from './progress';
import Running from './Running';

type Props = Area & { reset: () => void; load: (code: string) => void; code: string };
type T = ReturnType<typeof useT>['t'];

/** A dead child as first entered: their mother or father is the deceased's wife or husband until the reader says not. */
const NEW_BRANCH: Branch = { sex: 'm', sons: 0, daughters: 0, spouse: false, parent: true };
/** The questions this family is asked here: the estate is the next section's. */
const questions = (c: Case) => steps(c).filter((s) => s !== 'estate');
/** Where a question lands on a phone when it opens: the answer folded above it stays in view. */
const ABOVE = 56;
/** The bottom bar and a margin: nothing a tap opens may sit behind it. */
const BAR = 72;
/** «١٩٩٧» and «۱۹۹۷» typed on an Arabic keyboard, read as 1997. */
const western = (s: string) => s.replace(/[٠-٩۰-۹]/g, (d) => String(d.charCodeAt(0) & 0xf));
/** i18next's context for the deceased's sex: the masculine is the plain key. */
const of = (sex: Sex) => ({ context: sex === 'f' ? 'f' : undefined });

/** «حاسبة الإرث»'s way in (IR13, IR6, IR7, IR16 of the inheritance review): the family asked as an adoul asks it, one
 *  question at a time in the order of the law, each only when it can change the answer (flow.ts). The question in hand
 *  is open with who takes what so far under it; those answered fold to one line that reopens on a tap; those ahead are
 *  not shown. A family that came by its link opens with every question folded. Under the questions, once, who was not
 *  asked about and why, and the way to keep the family on this phone. */
export default function Ask({ c, set, answer, open, setOpen, reset, load, code }: Props) {
  const { t, i18n } = useT();
  useState(() => begin(!nobody(c)));
  const { step, seen } = useProgress();
  const sex = c.deceased;
  const section = useRef<HTMLElement>(null);
  const place = useRef<HTMLDivElement>(null);
  const moved = useRef<'step' | 'end' | null>(null);
  const ask = asked(c);
  const list = questions(c);
  const n = (h: Heir) => c.counts[h] ?? 0;
  const count = (h: Heir, v: number) => set({ counts: { ...c.counts, [h]: v } });

  const go = (s: Step | null) => {
    moved.current = s ? 'step' : 'end';
    move({ step: s, seen: s && !seen.includes(s) ? [...seen, s] : seen });
  };
  /** The next question not yet asked, in the law's order; none, and every question folds. */
  const after = (from: Step, now: Case = c) => questions(now).find((s) => ORDER.indexOf(s) > ORDER.indexOf(from) && !seen.includes(s)) ?? null;
  const next = (from: Step, now: Case = c) => go(after(from, now));

  // The question that opens is brought into view, under the answer folded above it; the last «التالي» brings the tree.
  useEffect(() => {
    const why = moved.current;
    moved.current = null;
    if (!why) return;
    const behavior: ScrollBehavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
    if (why === 'end') {
      (section.current?.nextElementSibling as HTMLElement | null)?.scrollIntoView({ behavior, block: 'start' });
      return;
    }
    const r = place.current?.getBoundingClientRect();
    const room = window.innerHeight - (window.matchMedia('(min-width: 1024px)').matches ? 16 : BAR);
    // A question taller than the screen goes to its top edge, so its «التالي» is as near as it can be.
    if (r && (r.top < 0 || r.bottom > room)) window.scrollBy({ top: r.top - (r.height > room - ABOVE ? 0 : ABOVE), behavior });
  }, [step]);

  const question = (s: Step): string => t(`ask.${s}.q`, of(sex));

  const kinRows = (s: Step) => (KIN[s] ?? []).filter((h) => ask.has(h)).map((h) => {
    if (most(h) === 1) return <YesNo key={h} label={heirName(h, 1, sex, t)} value={n(h) > 0} onChange={(y) => count(h, y ? 1 : 0)} />;
    const name = heirName(h, 2, sex, t);
    return <Stepper key={h} label={bare(name)} note={codeWord(name)} value={n(h)} max={most(h)} onChange={(v) => count(h, v)} />;
  });

  const body = (s: Step): ReactNode => {
    switch (s) {
      case 'who':
        return (
          <>
            <Choice name={question(s)} value={sex} options={[{ key: 'm', label: t('ask.who.m') }, { key: 'f', label: t('ask.who.f') }]}
                    onChange={(d) => {
                      // A man leaves no husband, a woman no wife.
                      const counts = { ...c.counts };
                      delete counts[d === 'm' ? 'husband' : 'wife'];
                      set({ deceased: d, counts });
                    }} />
            <Died c={c} set={set} />
          </>
        );
      case 'spouse':
        return sex === 'm' ? (
          <Choice name={question(s)} value={n('wife')} options={[0, 1, 2, 3, 4].map((k) => ({ key: k, label: k ? String(k) : t('ask.no') }))}
                  onChange={(k) => { const now = { ...c, counts: { ...c.counts, wife: k } }; set({ counts: now.counts }); next(s, now); }} />
        ) : (
          <Choice name={question(s)} value={n('husband')} options={[{ key: 0, label: t('ask.no') }, { key: 1, label: t('ask.yes') }]}
                  onChange={(k) => { const now = { ...c, counts: { ...c.counts, husband: k } }; set({ counts: now.counts }); next(s, now); }} />
        );
      case 'children':
        return (
          <>
            <p className="m-0 text-meta text-ink-soft">{t('ask.children.hint', of(sex))}</p>
            <div className="flex flex-col">
              <Stepper label={t('ask.children.sons')} value={n('son')} onChange={(v) => count('son', v)} />
              <Stepper label={t('ask.children.daughters')} value={n('daughter')} onChange={(v) => count('daughter', v)} />
            </div>
            <YesNo label={t('ask.children.dead', of(sex))} why={t('ask.children.deadWhy')} value={c.branches.length > 0}
                   onChange={(yes) => set({ branches: yes ? (c.branches.length ? c.branches : [NEW_BRANCH]) : [] })} />
            {c.branches.map((b, i) => <Dead key={i} c={c} b={b} i={i} set={set} />)}
            {c.branches.length ? (
              <Button variant="quiet" className="self-start" onClick={() => set({ branches: [...c.branches, NEW_BRANCH] })}>{t('ask.branch.add', of(sex))}</Button>
            ) : null}
          </>
        );
      case 'parents':
        return (
          <div className="flex flex-col">
            <YesNo label={t('ask.parents.father', of(sex))} value={n('father') > 0} onChange={(y) => count('father', y ? 1 : 0)} />
            <YesNo label={t('ask.parents.mother', of(sex))} value={n('mother') > 0} onChange={(y) => count('mother', y ? 1 : 0)} />
          </div>
        );
      case 'elders':
      case 'agnates':
        return (
          <>
            {s === 'agnates' ? <p className="m-0 text-meta text-ink-soft">{t('ask.agnates.hint')}</p> : null}
            <div className="flex flex-col">{kinRows(s)}</div>
          </>
        );
      case 'siblings':
        return (
          <>
            {siblingsForMother(c) ? (
              <div className="flex flex-col gap-1">
                <p className="m-0 text-meta">{t('ask.siblings.forMother')}</p>
                <Cites today={[[347, 2], [359, 1]]} />
              </div>
            ) : <p className="m-0 text-meta text-ink-soft">{t('ask.siblings.hint')}</p>}
            <div className="flex flex-col">{kinRows(s)}</div>
          </>
        );
      case 'checks':
        return <Checks c={c} set={set} open={open} setOpen={setOpen} />;
      default:
        return null;
    }
  };

  const skips = skipped(c);
  const addAnyway = () => {
    setOpen({ tree: true });
    move({ big: true });
    requestAnimationFrame(() => document.getElementById('inh-tree')?.scrollIntoView({ block: 'start' }));
  };

  return (
    <section ref={section} id="inh-ask" aria-label={t('ask.title')} style={{ scrollMarginTop: 16 }} className="flex flex-col rounded-card bg-sheet px-4 py-3 sm:px-6">
      {list.filter((s) => s === step || seen.includes(s)).map((s) => s === step ? (
        <div key={s} ref={place} className="flex flex-col gap-3 border-t border-rule py-4 first:border-t-0 first:pt-1">
          <h2 className="m-0 text-lead font-semibold">{question(s)}</h2>
          {body(s)}
          {/* Before anyone is entered, the first question has no shares to show: its line would only push «التالي» down. */}
          {s === 'who' && answer.state === 'empty' ? null : <Running c={c} answer={answer} />}
          <Button variant="primary" className="self-start" onClick={() => next(s)}>{t(after(s) ? 'ask.next' : 'ask.finish')}</Button>
        </div>
      ) : (
        <button key={s} type="button" onClick={() => go(s)} aria-expanded="false"
                className="flex min-h-11 w-full items-center gap-3 border-t border-rule py-2 text-start first:border-t-0">
          <span className="min-w-0 flex-1 text-body leading-snug">
            <span className="text-ink-soft">{s === 'spouse' && n('wife') > 1 ? t('ask.spouse.foldMany') : t(`ask.${s}.fold`, of(sex))}{t('ask.fold.colon')}</span>
            <span className="font-semibold">{inSentence(summary(s, c, t), i18n.language)}</span>
          </span>
          <span className="shrink-0 text-meta text-stamp">{t('ask.change')}</span>
        </button>
      ))}
      {skips.length && (step === null || seen.includes('parents')) ? (
        <div className="flex flex-col gap-2 border-t border-rule pt-3 pb-1">
          {skips.map((x) => (
            <div key={x.step} className="flex flex-col gap-1">
              <p className="m-0 text-meta text-ink-soft">{t(`ask.skipped.${x.step}.${x.why}`)}</p>
              <Cites today={x.cites} />
            </div>
          ))}
          {!open.tree ? <Button variant="quiet" className="self-start" onClick={addAnyway}>{t('ask.skipped.add')}</Button> : null}
        </div>
      ) : null}
      <Kept code={code}
            onLoad={(k) => { load(k); move(FOLDED); }}
            onReset={() => { reset(); restart(); setOpen({ later: false, will: false, tanzil: false, tree: false }); }} />
    </section>
  );
}

/** One folded question's answer in a few words: «ابن و3 بنات». */
function summary(s: Step, c: Case, t: T): string {
  const sex = c.deceased;
  const n = (h: Heir) => c.counts[h] ?? 0;
  const names = (hs: Heir[]) => hs.filter((h) => n(h) > 0)
    .map((h) => (n(h) > 1 ? `${bare(heirName(h, n(h), sex, t))} (${n(h)})` : bare(heirName(h, 1, sex, t))))
    .join(t('ask.fold.sep')) || t('ask.fold.none');
  switch (s) {
    case 'who': return t(`ask.who.${sex}`) + (c.died ? t('ask.fold.died', { year: c.died.slice(0, 4), ...of(sex) }) : '');
    case 'spouse': {
      const k = n(sex === 'm' ? 'wife' : 'husband');
      return !k ? t('ask.no') : sex === 'f' ? t('ask.yes') : k === 1 ? t('ask.fold.one') : String(k);
    }
    case 'children': {
      const parts = [
        n('son') ? (n('son') === 1 ? t('ask.fold.son') : t('ask.fold.sons', { n: n('son') })) : '',
        n('daughter') ? (n('daughter') === 1 ? t('ask.fold.daughter') : t('ask.fold.daughters', { n: n('daughter') })) : '',
      ].filter(Boolean);
      const k = c.branches.length;
      const alone = parts.length ? '' : 'Alone';
      const dead = k ? t(`ask.fold.dead${k === 1 ? 'One' : 'Many'}${alone}`, { n: k, ...of(sex) }) : '';
      return parts.length || dead ? parts.join(t('ask.fold.and')) + dead : t('ask.no');
    }
    case 'parents': return n('father') && n('mother') ? t('ask.fold.both') : n('father') ? t('ask.fold.father') : n('mother') ? t('ask.fold.mother') : t('ask.fold.none');
    case 'elders': case 'siblings': case 'agnates': return names(KIN[s] ?? []);
    case 'checks': {
      const yes = [c.later.length ? 'later' : '', c.will ? 'will' : '', c.tanzil ? 'tanzil' : '', c.unborn ? 'unborn' : '', c.other ? 'other' : ''].filter(Boolean);
      return yes.length ? yes.map((k) => t(`ask.checks.${k}Short`)).join(t('ask.fold.sep')) : t('ask.no');
    }
    default: return '';
  }
}

/** The death taken to be after 5 February 2004, when the family code took effect, said in one quiet line; «لا، قبل ذلك»
 *  opens a year, and only a year the family typed is kept (IR6): never today's date, never one nobody gave. */
function Died({ c, set }: Pick<Area, 'c' | 'set'>) {
  const { t } = useT();
  const [before, setBefore] = useState(c.died !== '');
  const [year, setYear] = useState(c.died.slice(0, 4));
  const now = Number(todayIso().slice(0, 4));
  const y = Number(year);
  const good = /^\d{4}$/.test(year) && y >= 1900 && y <= now;
  if (!before) {
    return (
      <p className="m-0 flex flex-wrap items-center gap-x-2 text-meta text-ink-soft">
        <span>{t('ask.who.after')}</span>
        <button type="button" onClick={() => setBefore(true)} className="min-h-11 font-semibold text-stamp">{t('ask.who.before')}</button>
      </p>
    );
  }
  const typed = (v: string) => {
    const d = western(v).replace(/\D/g, '').slice(0, 4);
    const k = Number(d);
    setYear(d);
    set({ died: d.length === 4 && k >= 1900 && k <= now ? d : '' });
  };
  return (
    <div className="flex flex-col gap-2 rounded-control bg-paper px-3 py-2">
      <label className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-body">{t('ask.who.year')}</span>
        <input inputMode="numeric" dir="ltr" autoComplete="off" value={year} placeholder="1997" onChange={(e) => typed(e.target.value)}
               className="h-11 rounded-control border border-field bg-sheet px-3 text-body tabular-nums" style={{ width: '7rem' }} />
      </label>
      {year.length === 4 && !good ? <p role="status" className="m-0 text-meta text-ink-soft">{t('ask.who.bad')}</p> : null}
      {good && y === 2004 ? (
        // The code took effect within 2004: that year needs its day.
        <label className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-meta">{t('ask.who.day')}</span>
          <input type="date" dir="ltr" min="2004-01-01" max="2004-12-31" value={c.died.length === 10 ? c.died : ''}
                 onChange={(e) => set({ died: e.target.value || '2004' })}
                 className="h-11 rounded-control border border-field bg-sheet px-3 text-body" />
        </label>
      ) : null}
      <button type="button" onClick={() => { setBefore(false); setYear(''); set({ died: '' }); }} className="min-h-11 self-start text-meta text-stamp">
        {t('ask.who.undo')}
      </button>
    </div>
  );
}

/** A son or daughter who died before the deceased and left children: the only way grandchildren are entered (IR1), so
 *  the bequest of arts 369–372 is never silently missing. Their own widow or widower, and whether the deceased's wife or
 *  husband is their parent, change the grandchildren's part (IR2). */
function Dead({ c, b, i, set }: { c: Case; b: Branch; i: number; set: Area['set'] }) {
  const { t } = useT();
  const put = (patch: Partial<Branch>) => set({ branches: c.branches.map((x, j) => (j === i ? { ...x, ...patch } : x)) });
  const mates = c.deceased === 'm' ? c.counts.wife ?? 0 : c.counts.husband ?? 0;
  const parent = c.deceased === 'm' ? (mates > 1 ? 'parentWives' : 'parentWife') : 'parentHusband';
  return (
    <div className="flex flex-col gap-2 rounded-control bg-paper px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-body font-semibold">{t(`ask.branch.${b.sex === 'm' ? 'son' : 'daughter'}`, of(c.deceased))}</span>
        <Button variant="quiet" onClick={() => set({ branches: c.branches.filter((_, j) => j !== i) })}>{t('ask.branch.remove')}</Button>
      </div>
      <Choice name={t('ask.branch.sex')} value={b.sex} onChange={(sex) => put({ sex })}
              options={[{ key: 'm', label: t('ask.branch.isSon') }, { key: 'f', label: t('ask.branch.isDaughter') }]} />
      <div className="flex flex-col">
        <Stepper label={t('ask.branch.sons', of(b.sex))} value={b.sons} onChange={(v) => put({ sons: v })} />
        <Stepper label={t('ask.branch.daughters', of(b.sex))} value={b.daughters} onChange={(v) => put({ daughters: v })} />
      </div>
      <div className="flex flex-col">
        <YesNo label={t('ask.branch.spouse', of(b.sex))} why={t('ask.branch.spouseWhy', of(b.sex))} value={Boolean(b.spouse)} onChange={(spouse) => put({ spouse })} />
        {mates ? (
          <YesNo label={t(`ask.branch.${parent}`, of(b.sex))} why={t('ask.branch.parentWhy', of(c.deceased === 'm' ? 'f' : 'm'))}
                 value={b.parent !== false} onChange={(p) => put({ parent: p })} />
        ) : null}
      </div>
    </div>
  );
}

/** What the tool cannot count, asked before the answer (IR7), each with why it is asked. A yes opens the part of the
 *  page that handles it (an heir who died since, a will, a «تنزيل»), or stops the tool (a child to be born; someone
 *  missing, of another faith, not recognised by the father, or who killed the deceased): the answer says who decides. */
function Checks({ c, set, open, setOpen }: Pick<Area, 'c' | 'set' | 'open' | 'setOpen'>) {
  const { t } = useT();
  const sex = c.deceased;
  const willOrTanzil = open.will || open.tanzil || Boolean(c.will || c.tanzil);
  return (
    <div className="flex flex-col">
      <YesNo label={t('ask.checks.later', of(sex))} why={t('ask.checks.laterWhy')} value={open.later || c.later.length > 0}
             onChange={(y) => { setOpen({ later: y }); if (!y && c.later.length) set({ later: [] }); }} />
      <YesNo label={t('ask.checks.will', of(sex))} why={t('ask.checks.willWhy')} value={willOrTanzil}
             onChange={(y) => {
               setOpen(y ? { will: true } : { will: false, tanzil: false });
               if (!y && (c.will || c.tanzil)) set({ will: null, tanzil: null });
             }}>
        {willOrTanzil ? (
          <div className="ms-4 flex flex-col">
            <YesNo label={t('ask.checks.tanzil', of(sex))} why={t('ask.checks.tanzilWhy')} value={open.tanzil || Boolean(c.tanzil)}
                   onChange={(y) => { setOpen({ tanzil: y }); if (!y && c.tanzil) set({ tanzil: null }); }} />
          </div>
        ) : null}
      </YesNo>
      <YesNo label={t('ask.checks.unborn', of(sex))} why={t('ask.checks.unbornWhy')} value={c.unborn} onChange={(unborn) => set({ unborn })} />
      <YesNo label={t('ask.checks.other', of(sex))} why={t('ask.checks.otherWhy')} value={c.other} onChange={(other) => set({ other })} />
    </div>
  );
}
