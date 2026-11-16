import { useState, type CSSProperties, type ReactNode } from 'react';
import { Button } from '@/shared/components/ui';
import type { Area } from '../area';
import { most, nobody, sexOf } from '../case';
import type { BequestLine, Branch, Cite, Heir } from '../engine';
import { KIN } from '../flow';
import Cites from '../parts/Cites';
import { sayShare } from '../parts/say';
import { useT } from '../strings';
import { Choice } from './controls';
import { bare, codeWord, heirName, inSentence, outWord } from './names';
import { move, useProgress } from './progress';

const ELDERS: Heir[] = ['grandfather', 'grandmotherF', 'grandmotherM'];
const PARENTS: Heir[] = ['father', 'mother'];
const CHILDREN: Heir[] = ['son', 'daughter'];
/** A son's children given as a kind: only from an old link. New ones are entered under their dead parent (IR1). */
const GRAND: Heir[] = ['sonsSon', 'sonsDaughter'];
const SIBLINGS = KIN.siblings ?? [];
const AGNATES = KIN.agnates ?? [];
/** Three tiles a row on a 390 px phone, two in edit mode, where − and + sit on the tile. */
const TILE: CSSProperties = { flex: '1 1 6rem', maxWidth: '12rem' };
const EDIT: CSSProperties = { flex: '1 1 9rem', maxWidth: '14rem' };
/** A dead child in edit mode holds two counters: a row of its own. */
const WIDE: CSSProperties = { flex: '1 1 100%', maxWidth: '22rem' };
const DOT: CSSProperties = { width: 26, height: 26 };
const NEW = (sex: 'm' | 'f'): Branch => ({ sex, sons: 1, daughters: 0, spouse: false, parent: true });

/** Each dead child's bequest line: the engine keeps the children's branches in order and leaves out those owed none. */
function bequestsOf(branches: Branch[], lines: BequestLine[]): (BequestLine | null)[] {
  let k = 0;
  return branches.map((b) => {
    const x = lines[k];
    if (x && x.sex === b.sex && x.sons === b.sons && x.daughters === b.daughters) { k++; return x; }
    return null;
  });
}

/** The family as a picture, and the expert's direct way in (IR13, IR15 of the inheritance review). Parents above,
 *  the deceased with the wife or husband beside, the children below, a dead child with their children under them; the
 *  brothers and sisters and the far agnates in a row of their own. Only the family is drawn, each with their share in
 *  words, or «لا يرث هنا» in grey, and a tap says why with its articles. While the questions are in use it folds to a
 *  small picture so the answer stays near; in edit mode it shows every kind of heir with − and + on the tile. */
export default function Tree({ c, set, answer, open, setOpen }: Area) {
  const { t, i18n } = useT();
  const { step, seen, big } = useProgress();
  const [chosen, setChosen] = useState<string | null>(null);
  const editing = open.tree;
  const sex = c.deceased;
  const spouse: Heir = sex === 'm' ? 'wife' : 'husband';
  const n = (h: Heir) => c.counts[h] ?? 0;
  const ok = answer.state === 'ok' ? answer.result : null;
  const lineOf = (h: Heir) => ok?.lines.find((l) => l.heir === h);
  const outOf = (h: Heir) => ok?.excluded.find((e) => e.heir === h);
  const bequests = bequestsOf(c.branches, ok?.bequest ?? []);
  const none = nobody(c);
  const there = (hs: Heir[]) => hs.filter((h) => n(h) > 0);
  const setN = (h: Heir, v: number) => set({ counts: { ...c.counts, [h]: Math.max(0, Math.min(most(h), v)) } });
  const putBranch = (i: number, patch: Partial<Branch>) => set({ branches: c.branches.map((x, j) => (j === i ? { ...x, ...patch } : x)) });
  const each = (h: Heir, share: string) => t(`ask.tree.each${sexOf(h) === 'f' ? 'F' : 'M'}`, { share });

  /** Under a tile: one person's share in words, or that they take nothing here. */
  const shareOf = (h: Heir): { text: string; out: boolean } | null => {
    const l = lineOf(h);
    if (l) return { text: n(h) > 1 ? each(h, sayShare(l.each, t)) : sayShare(l.each, t), out: false };
    return ok && n(h) ? { text: outWord(h, n(h), t), out: true } : null;
  };
  /** One kind of a dead child's children: one person's part and how it comes (the bequest, or a place among the
   *  heirs when no son survives), or nothing here. */
  const kidShare = (b: Branch, i: number, boy: boolean): { share: string; how: string; out: boolean } | null => {
    if (!ok) return null;
    const count = boy ? b.sons : b.daughters;
    const say = (x: Parameters<typeof sayShare>[0]) => (count > 1 ? t(`ask.tree.each${boy ? 'M' : 'F'}`, { share: sayShare(x, t) }) : sayShare(x, t));
    const bq = bequests[i];
    if (bq) return { share: say(boy ? bq.son : bq.daughter), how: t('ask.tree.bequest'), out: false };
    const l = b.sex === 'm' ? lineOf(boy ? 'sonsSon' : 'sonsDaughter') : undefined;
    if (l) return { share: say(l.each), how: t('ask.tree.inherit'), out: false };
    return { share: t(`ask.tree.out.${boy ? 'm' : 'f'}${count > 1 ? 'p' : ''}`), how: '', out: true };
  };
  const kidsOf = (b: Branch) => [
    b.sons ? (b.sons === 1 ? t('ask.tree.kidSon') : t('ask.tree.kidSons', { n: b.sons })) : '',
    b.daughters ? (b.daughters === 1 ? t('ask.tree.kidDaughter') : t('ask.tree.kidDaughters', { n: b.daughters })) : '',
  ].filter(Boolean).join(t('ask.fold.and')) || t('ask.tree.noKids');

  const tile = (h: Heir) => {
    const k = n(h);
    const name = heirName(h, Math.max(k, 1), sex, t);
    const s = shareOf(h);
    const look = s?.out ? 'border-dashed border-field bg-paper text-ink-soft' : 'border-[var(--t)] bg-sheet text-ink';
    if (editing) {
      const max = GRAND.includes(h) ? k : most(h);
      return (
        <div key={h} role="group" aria-label={bare(name)} style={EDIT}
             className={`flex min-w-0 flex-col items-center gap-0.5 rounded-control border px-1.5 pt-2 text-center leading-snug ${k ? look : 'border-dashed border-field bg-sheet text-ink-soft'}`}>
          <span className="text-meta font-semibold">{bare(name)}</span>
          {codeWord(name) ? <span className="text-meta text-ink-soft">{codeWord(name)}</span> : null}
          {k && s ? <span className={`text-meta ${s.out ? '' : 'font-semibold text-[color:var(--t)]'}`}>{s.text}</span> : null}
          <span className="flex items-center">
            <button type="button" aria-label={t('ask.tree.less', { name: bare(name) })} disabled={!k} onClick={() => setN(h, k - 1)}
                    className="size-11 rounded-full text-lead text-ink hover:text-stamp disabled:opacity-40">−</button>
            <output aria-live="polite" style={{ minWidth: 24 }} className="text-center text-lead font-semibold tabular-nums text-ink">{k}</output>
            <button type="button" aria-label={t('ask.tree.more', { name: bare(name) })} disabled={k >= max} onClick={() => setN(h, k + 1)}
                    className="size-11 rounded-full text-lead text-ink hover:text-stamp disabled:opacity-40">+</button>
          </span>
        </div>
      );
    }
    return (
      <button key={h} type="button" onClick={() => setChosen(chosen === h ? null : h)} aria-pressed={chosen === h} style={TILE}
              className={`flex min-h-14 flex-col items-center justify-center rounded-control border px-2 py-1.5 text-center leading-snug ${look} ${chosen === h ? 'ring-2 ring-ink' : ''}`}>
        <span className="text-meta font-semibold">{bare(name)}{k > 1 ? ` (${k})` : ''}</span>
        {s ? <span className={`whitespace-nowrap text-meta ${s.out ? '' : 'font-semibold text-[color:var(--t)]'}`}>{s.text}</span> : null}
      </button>
    );
  };

  const dead = (b: Branch, i: number) => {
    const key = `b${i}`;
    const title = t(`ask.branch.${b.sex === 'm' ? 'son' : 'daughter'}`, { context: sex === 'f' ? 'f' : undefined });
    if (editing) {
      const row = (label: string, v: number, put: (v: number) => void) => (
        <span className="flex items-center gap-1" role="group" aria-label={label}>
          <span className="text-meta">{label}</span>
          <button type="button" aria-label={t('ask.tree.less', { name: label })} disabled={!v} onClick={() => put(v - 1)} className="size-11 rounded-full text-lead hover:text-stamp disabled:opacity-40">−</button>
          <output aria-live="polite" style={{ minWidth: 20 }} className="text-center text-lead font-semibold tabular-nums">{v}</output>
          <button type="button" aria-label={t('ask.tree.more', { name: label })} disabled={v >= 20} onClick={() => put(v + 1)} className="size-11 rounded-full text-lead hover:text-stamp disabled:opacity-40">+</button>
        </span>
      );
      return (
        <div key={key} role="group" aria-label={title} style={WIDE} className="flex min-w-0 flex-col items-center rounded-control border border-dashed border-ink-soft bg-sheet px-1.5 pt-2 text-center leading-snug">
          <span className="text-meta font-semibold">{title}</span>
          {row(t('ask.tree.boysCount'), b.sons, (v) => putBranch(i, { sons: v }))}
          {row(t('ask.tree.girlsCount'), b.daughters, (v) => putBranch(i, { daughters: v }))}
          <span className="flex flex-wrap justify-center">
            <button type="button" onClick={() => { move({ step: 'children', seen: seen.includes('children') ? seen : [...seen, 'children'] }); requestAnimationFrame(() => document.getElementById('inh-ask')?.scrollIntoView({ block: 'start' })); }}
                    className="min-h-11 px-2 text-meta text-stamp">{t('ask.tree.questions')}</button>
            <button type="button" onClick={() => set({ branches: c.branches.filter((_, j) => j !== i) })} className="min-h-11 px-2 text-meta text-ink-soft hover:text-stamp">{t('ask.branch.remove')}</button>
          </span>
        </div>
      );
    }
    return (
      <button key={key} type="button" onClick={() => setChosen(chosen === key ? null : key)} aria-pressed={chosen === key} style={TILE}
              className={`flex min-h-14 flex-col items-center justify-center rounded-control border border-dashed border-ink-soft bg-sheet px-2 py-1.5 text-center leading-snug text-ink ${chosen === key ? 'ring-2 ring-ink' : ''}`}>
        <span className="text-meta font-semibold">{title}</span>
        <span className="text-meta text-ink-soft">{kidsOf(b)}</span>
      </button>
    );
  };
  /** Under a dead child, their children: each kind a tile with its part (IR1: the bequest is never missing). */
  const grandkids = (b: Branch, i: number) => {
    const key = `b${i}`;
    return ([true, false] as const).filter((boy) => (boy ? b.sons : b.daughters) > 0).map((boy) => {
      const count = boy ? b.sons : b.daughters;
      const s = kidShare(b, i, boy);
      return (
        <button key={`${key}${boy ? 's' : 'd'}`} type="button" onClick={() => setChosen(chosen === key ? null : key)} aria-pressed={chosen === key} style={TILE}
                className={`flex min-h-14 flex-col items-center justify-center rounded-control border px-2 py-1.5 text-center leading-snug ${s?.out ? 'border-dashed border-field bg-paper text-ink-soft' : 'border-[var(--t)] bg-sheet text-ink'} ${chosen === key ? 'ring-2 ring-ink' : ''}`}>
          <span className="text-meta font-semibold">{t(`ask.tree.${boy ? 'boy' : 'girl'}${count > 1 ? 's' : ''}`, { n: count })}</span>
          {s ? <span className={`whitespace-nowrap text-meta ${s.out ? '' : 'font-semibold text-[color:var(--t)]'}`}>{s.share}</span> : null}
          {s?.how ? <span className="text-meta text-ink-soft">{s.how}</span> : null}
        </button>
      );
    });
  };

  const self = (
    <div key="self" style={TILE} className="flex min-h-14 flex-col items-center justify-center rounded-control bg-ink px-2 py-1.5 text-center leading-snug text-sheet">
      <span className="text-body font-semibold">{t('ask.tree.deceased', { context: sex === 'f' ? 'f' : undefined })}</span>
      {c.died ? <span className="text-meta">{c.died.slice(0, 4)}</span> : null}
    </div>
  );
  const link = <span aria-hidden="true" className="mx-auto block bg-rule" style={{ width: 2, height: 10 }} />;
  const row = (key: string, items: ReactNode[], label?: string) => (items.length ? (
    <div key={key} className="flex flex-col gap-1.5">
      {label ? <span className="text-meta text-ink-soft">{label}</span> : null}
      <div className="flex flex-wrap justify-center gap-2">{items}</div>
    </div>
  ) : null);

  // The generations, top to bottom; in edit mode every kind the code names, else only the family.
  const pick = (hs: Heir[]) => (editing ? hs.filter((h) => !GRAND.includes(h) || n(h)) : there(hs));
  const kids = [...pick([...CHILDREN, ...GRAND]).map(tile), ...c.branches.map(dead)];
  if (editing) {
    kids.push(
      <button key="add-son" type="button" style={EDIT} onClick={() => set({ branches: [...c.branches, NEW('m')] })}
              className="min-h-14 self-center rounded-control border border-dashed border-field bg-sheet px-2 text-meta text-ink-soft hover:text-stamp">{t('ask.tree.addSon', { context: sex === 'f' ? 'f' : undefined })}</button>,
      <button key="add-daughter" type="button" style={EDIT} onClick={() => set({ branches: [...c.branches, NEW('f')] })}
              className="min-h-14 self-center rounded-control border border-dashed border-field bg-sheet px-2 text-meta text-ink-soft hover:text-stamp">{t('ask.tree.addDaughter', { context: sex === 'f' ? 'f' : undefined })}</button>,
    );
  }
  const generations = [
    row('elders', pick(ELDERS).map(tile), editing ? t('ask.tree.elders') : undefined),
    row('parents', pick(PARENTS).map(tile), editing ? t('ask.tree.parents') : undefined),
    row('self', [self, ...pick([spouse]).map(tile)]),
    row('kids', kids, editing ? t('ask.tree.children') : undefined),
    ...(editing ? [] : c.branches.map((b, i) => row(`kids${i}`, grandkids(b, i), t(`ask.tree.kidsOf${b.sex === 'm' ? 'Son' : 'Daughter'}`, { context: sex === 'f' ? 'f' : undefined })))),
  ].filter(Boolean);
  const side = editing
    ? [row('siblings', SIBLINGS.map(tile), t('ask.tree.siblings')), row('agnates', AGNATES.map(tile), t('ask.tree.agnates'))].filter(Boolean)
    : [row('side', there([...SIBLINGS, ...AGNATES]).map(tile), t('ask.tree.side'))].filter(Boolean);

  // Why, for the tile tapped: the reason in the family's words, the code's own one tap below, the articles.
  const detail = (): ReactNode => {
    if (!chosen || !ok || editing) return null;
    let title = '', text = '', law = '';
    // `cites`: the engine's, in its book's numbers; `today`: written here, in today's.
    let cites: Cite[] = [];
    let today: Cite[] = [];
    if (chosen.startsWith('b')) {
      const i = Number(chosen.slice(1));
      const b = c.branches[i];
      if (!b) return null;
      const bq = bequests[i];
      title = t(`ask.branch.${b.sex === 'm' ? 'son' : 'daughter'}`, { context: sex === 'f' ? 'f' : undefined });
      if (bq) {
        text = t('ask.tree.bequestWhy', { context: b.sex === 'f' ? 'f' : undefined, parent: sayShare(bq.parent, t), part: sayShare(bq.part, t) });
        today = [369, 370, 371, 372];
      } else {
        const l = b.sex === 'm' ? lineOf('sonsSon') ?? lineOf('sonsDaughter') : undefined;
        text = l ? t('ask.tree.inheritWhy') : t('ask.tree.nothingWhy');
        cites = l ? l.cites : [];
        today = l ? [371] : [369, 370];
      }
    } else {
      const h = chosen as Heir;
      const l = lineOf(h), e = outOf(h);
      if (!l && !e) return null;
      const by = e && e.by !== 'rule' ? inSentence(bare(heirName(e.by, 1, sex, t)), i18n.language) : '';
      title = heirName(h, n(h), sex, t);
      text = l ? t(`why.${l.why}`) : t(`out.${e!.why}`, { by });
      law = l ? t(`lawWhy.${l.why}`) : t(`lawOut.${e!.why}`, { by });
      cites = l?.cites ?? e?.cites ?? [];
    }
    return (
      <div aria-live="polite" className="flex flex-col gap-1.5 rounded-control bg-paper px-4 py-3">
        <p className="m-0 text-body font-semibold">{title}</p>
        <p className="m-0 text-body">{text}</p>
        {law && law !== text ? (
          <details>
            <summary className="flex min-h-11 cursor-pointer items-center text-meta text-stamp">{t('ask.tree.law')}</summary>
            <p className="m-0 text-meta text-ink-soft">{law}</p>
          </details>
        ) : null}
        <Cites cites={cites} today={today} />
      </div>
    );
  };

  const editButton = (
    <Button variant={editing ? 'primary' : 'secondary'} onClick={() => { setOpen({ tree: !editing }); setChosen(null); }}>
      {t(editing ? 'ask.tree.done' : 'ask.tree.edit')}
    </Button>
  );

  // While a question is open the tree is a small picture, a dot for each kind of relative, so the answer stays near.
  if (!editing && (none || (step !== null && !big))) {
    const dot = (key: string, kind: 'in' | 'out' | 'self' | 'gone', label = '') => (
      <span key={key} style={DOT} className={`inline-flex items-center justify-center rounded-full text-meta font-semibold ${
        kind === 'in' ? 'bg-[var(--t)] text-sheet' : kind === 'self' ? 'bg-ink text-sheet' : kind === 'gone' ? 'border-2 border-ink-soft' : 'border border-dashed border-ink-soft text-ink-soft'}`}>{label}</span>
    );
    const dots = (hs: Heir[]) => there(hs).map((h) => dot(h, ok && !lineOf(h) ? 'out' : 'in', n(h) > 1 ? String(n(h)) : ''));
    const lines = [
      dots([...ELDERS, ...PARENTS]),
      [dot('self', 'self'), ...dots([spouse])],
      [...dots([...CHILDREN, ...GRAND]), ...c.branches.flatMap((b, i) => [dot(`b${i}`, 'gone'), ...(b.sons + b.daughters ? [dot(`k${i}`, kidShare(b, i, b.sons > 0)?.out === false ? 'in' : 'out', String(b.sons + b.daughters))] : [])])],
      dots([...SIBLINGS, ...AGNATES]),
    ].filter((l) => l.length);
    return (
      <section id="inh-tree" aria-labelledby="inh-tree-h" style={{ scrollMarginTop: 16 }} className="flex items-center gap-3 rounded-card bg-sheet px-4 py-3 sm:px-6">
        <div className="flex min-w-0 flex-1 flex-col items-start gap-1">
          <h2 id="inh-tree-h" className="m-0 text-body font-semibold">{t('ask.tree.title')}</h2>
          {none ? <p className="m-0 text-meta text-ink-soft">{t('ask.tree.empty')}</p> : null}
          <span className="flex flex-wrap gap-1">
            {!none ? <button type="button" onClick={() => move({ big: true })} aria-expanded={false} className="min-h-11 text-body text-stamp">{t('ask.tree.show')}</button> : null}
            {editButton}
          </span>
        </div>
        {!none ? (
          <button type="button" onClick={() => move({ big: true })} aria-label={t('ask.tree.show')} className="flex shrink-0 flex-col items-center gap-1 rounded-control p-1">
            {lines.map((l, i) => <span key={i} className="flex justify-center gap-1">{l}</span>)}
          </button>
        ) : null}
      </section>
    );
  }

  return (
    <section id="inh-tree" aria-labelledby="inh-tree-h" style={{ scrollMarginTop: 16 }} className="flex flex-col gap-3 rounded-card bg-sheet px-4 py-4 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="inh-tree-h" className="m-0 text-lead font-semibold">{t('ask.tree.title')}</h2>
        <span className="flex flex-wrap gap-1">
          {!editing && step !== null ? <Button variant="quiet" onClick={() => move({ big: false })} aria-expanded>{t('ask.tree.fold')}</Button> : null}
          {editButton}
        </span>
      </div>
      {editing ? (
        <>
          <p className="m-0 text-meta text-ink-soft">{t('ask.tree.editHint')}</p>
          <div className="flex flex-col gap-1.5">
            <span className="text-meta text-ink-soft">{t('ask.who.q')}</span>
            <Choice name={t('ask.who.q')} value={sex} options={[{ key: 'm', label: t('ask.who.m') }, { key: 'f', label: t('ask.who.f') }]}
                    onChange={(d) => { const counts = { ...c.counts }; delete counts[d === 'm' ? 'husband' : 'wife']; set({ deceased: d, counts }); }} />
          </div>
        </>
      ) : ok ? <p className="m-0 text-meta text-ink-soft">{t('ask.tree.tap')}</p> : null}
      <div className="flex flex-col">
        {generations.map((g, i) => <div key={i}>{i ? link : null}{g}</div>)}
      </div>
      {side.length ? <div className="flex flex-col gap-3 border-t border-rule pt-3">{side}</div> : null}
      {detail()}
    </section>
  );
}
