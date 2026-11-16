import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Button } from '@/shared/components/ui';
import { useDismiss } from '@/shared/components/dismiss';
import { saveFamily } from '@/shared/services/saved';
import { todayIso } from '@/shared/services/today';
import { topicColour } from '@/features/topics/colour';
import { here, whatsapp } from '../../../kit/share';
import { ENGINE, sexOf, type Case } from '../case';
import { HEIRS, article, paragraph, type Cite } from '../engine';
import { ONE } from '../frac';
import { formatAmount } from '../money';
import { inBook, treasuryCites } from '../parts/rules';
import { percent, sayShare } from '../parts/say';
import type { Share } from '../solve';
import { citeLabel, useT } from '../strings';
import {
  BEQUEST_ARTS, NAMED_ART, branchName, outWords, groupName, laterName, lineName, longDay, money, shareWords, type Ok, type T,
} from './words';

/** «ورقة الفريضة» (IR22 of the inheritance review): one paper the family takes to the adouls. Who died and who was
 *  left, the estate and what left it first, every part out of the one number with its dirhams, the compulsory
 *  bequest, those who take nothing, what the calculator assumed, the articles, the day, the engine's version and the
 *  case's code. Since 15 Nov 2026 no line that no specialist has reviewed the tool yet: «عن «قانون»» says it once, and
 *  the paper neither prints nor sends it. No person's name: the family is
 *  said by kinship (IR17 is «No»). It prints alone, goes to WhatsApp as the same text with the link that reopens it,
 *  and is kept on the phone under a name the family gives. */
export default function Paper({ c, a, code }: { c: Case; a: Ok; code: string }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  return (
    <>
      <div className="flex flex-col gap-1.5">
        <Button variant="primary" className="self-start" onClick={() => setOpen(true)}>{t('answer.paper.open')}</Button>
        <p className="m-0 text-meta text-ink-soft">{t('answer.paper.lead')}</p>
      </div>
      {open ? <PaperView c={c} a={a} code={code} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

type Model = ReturnType<typeof paperModel>;

/** The paper as words, for the page, the print and the message alike. */
function paperModel(c: Case, a: Ok, code: string, t: T, lang: string) {
  const r = a.result;
  const m = money(a, t, lang);
  const sep = t('answer.sep');
  const after = t(`answer.after_${c.deceased}`);
  // Who was left: the living relatives, then each dead child with their own children.
  // In a French sentence the relatives are not capitalised: «Il laisse : l’épouse ; les filles (3)».
  const inline = (x: string) => (lang === 'fr' ? x.charAt(0).toLowerCase() + x.slice(1) : x);
  const family = HEIRS.filter((h) => (c.counts[h] ?? 0) > 0).map((h) => inline(groupName(h, c.counts[h] as number, t, true)));
  for (const b of c.branches) {
    if (b.sons + b.daughters === 0) continue;
    const kids = [b.sons ? t('answer.paper.sons', { count: b.sons }) : '', b.daughters ? t('answer.paper.daughters', { count: b.daughters }) : ''].filter(Boolean);
    family.push([
      t(`answer.paper.child_${b.sex}_${c.deceased}`),
      t(`answer.paper.kids_${b.sex}`, { list: kids.join(t('answer.paper.and')) }),
      b.spouse ? t(`answer.paper.spouse_${b.sex}`) : '',
      b.parent ? t(`answer.paper.parent_${b.sex}_${c.deceased}`) : '',
    ].filter(Boolean).join(' '));
  }
  const later = c.later.map((l) => {
    const sx = sexOf(l.heir);
    const theirs = HEIRS.filter((h) => (l.counts[h] ?? 0) > 0).map((h) => inline(groupName(h, l.counts[h] as number, t, true)));
    const kids = l.branches.filter((b) => b.sons + b.daughters > 0).map((b) => t(`answer.paper.child_${b.sex}_${sx}`));
    return t(`answer.paper.laterLeft_${sx}`, { heir: inline(t(`lawHeir.${l.heir}`)), family: [...theirs, ...kids].join(sep) || t('answer.paper.nobody') });
  });

  // The estate, as a ledger.
  const ledger: [string, string][] = [];
  if (a.money) {
    const out = ([['funeral', a.money.funeral], ['debts', a.money.debts], ['dowry', a.money.dowry]] as const).filter(([, v]) => v > 0n);
    if (out.length) {
      ledger.push([t('answer.estate.left'), m.dh(a.money.gross)]);
      for (const [k, v] of out) ledger.push([t(`answer.estate.${k}`), `− ${m.dh(v)}`]);
    }
    ledger.push([t(out.length ? 'answer.estate.net' : 'answer.estate.only'), m.dh(a.money.net)]);
  }

  // Before the heirs: the bequest, a will, a «تنزيل».
  const before: string[] = [];
  r.bequest.forEach((b, n) => {
    before.push(`${branchName(b, n, r.bequest, c.deceased, t)}${t('answer.colon')}${t(`answer.bequest.parent_${b.sex}`, { share: sayShare(b.parent, t), money: m.paren(b.parent) })} ${t(`answer.bequest.part_${b.sex}`, { part: sayShare(b.part, t), share: sayShare(b.share, t), money: m.paren(b.share) })}`);
  });
  if (r.bequest.length) {
    if (r.capped) before.push(t('answer.bequest.capped'));
    before.push(t('answer.bequest.court'));
    if (r.otherBequest) before.push(t('answer.bequest.other', { share: sayShare(r.otherBequest, t), money: m.paren(r.otherBequest) }));
  }
  if (r.will) {
    const whole = r.will.granted.n * r.will.asked.d === r.will.asked.n * r.will.granted.d;
    before.push(`${t('answer.will.asked', { share: sayShare(r.will.asked, t), money: m.paren(r.will.asked) })} ${whole ? t('answer.will.whole') : r.will.granted.n === 0n ? t('answer.will.none') : t('answer.will.granted', { share: sayShare(r.will.granted, t), money: m.paren(r.will.granted) })}${r.will.cut ? ` ${t(`answer.will.${r.will.cut}`)}` : ''}`);
  }
  if (a.willWaits) before.push(t('answer.will.waits'));
  if (r.tanzil) before.push(`${t('answer.tanzil.heading')}${t('answer.colon')}${t(`answer.tanzil.${r.tanzil.by}`)}${r.tanzil.cut ? ` ${t('answer.tanzil.cut')}` : ''}`);
  if (r.radd) {
    const alone = r.lines.length === 1 && r.lines[0].count === 1 ? r.lines[0] : null;
    before.push(r.raddSpouse ? t(`answer.radd.spouse_${r.raddSpouse.heir}`) : alone ? t(`answer.radd.one_${sexOf(alone.heir)}`) : t('answer.radd.plain'));
    if (r.raddSpouse) before.push(t(`answer.radd.other_${r.raddSpouse.heir}`, { share: sayShare(r.raddSpouse.fixed, t), money: m.paren(r.raddSpouse.fixed) }));
  }

  // The parts: the bequest, a will, a «تنزيل», the heirs, the Treasury, then each heir who died since with their heirs.
  // `share` and `dh` as a message says them («18 من 144», «100.000 درهم»); `cell` and `dhCell` as the table's columns,
  // whose headers already say «من 144» and «بالدرهم».
  type Line = { head?: string; under?: boolean; who: string; share: string; cell: string; dh: string | null; dhCell: string | null; pct: string };
  const common = a.common && a.common > 1n ? a.common : null;
  const row = (s: Share): Line => {
    const w = shareWords(s.each, a.common, t);
    const share = (common ? w.of ?? w.words : w.words ?? w.of) ?? '';
    const cell = common && common % s.each.d === 0n ? (s.each.n * (common / s.each.d)).toString() : share;
    return { who: lineName(s, t, true), share, cell, dh: m.paid(s), dhCell: a.paid ? formatAmount(a.paid.each[s.key], lang) : null, pct: percent(s.each) };
  };
  const lines: Line[] = [];
  // A dead child's grandchildren under their branch's name, so two branches are never confused.
  for (const g of ['bequest', 'will', 'tanzil', 'heir', 'treasury'] as const) {
    for (const s of a.shares) {
      if (s.group !== g) continue;
      const b = g === 'bequest' ? Number(s.key.slice(1, s.key.indexOf('.'))) : -1;
      const first = g === 'bequest' && a.shares.find((x) => x.group === 'bequest' && x.key.startsWith(`b${b}.`)) === s;
      lines.push({ ...row(s), head: first ? branchName(r.bequest[b], b, r.bequest, c.deceased, t) : undefined, under: g === 'bequest' });
    }
  }
  a.later.forEach((la, n) => {
    const own = a.shares.filter((s) => s.group === 'later' && s.later === n);
    if (la.gone || !own.length) return;
    const head = laterName(a, n, c.deceased, t, true);
    if (own.length === 1 && own[0].key === `l${n}`) { lines.push({ ...row(own[0]), who: head }); return; }
    own.forEach((s, i) => lines.push({ ...row(s), head: i === 0 ? head : undefined, under: true }));
  });
  const sum = a.paid ? a.shares.reduce((x, s) => x + (a.paid as NonNullable<typeof a.paid>).each[s.key] * BigInt(s.count), 0n) : null;
  const total: Line = {
    who: t('answer.total'),
    share: common ? t('answer.of', { n: common.toString(), d: common.toString() }) : t('answer.totalAll'),
    cell: common ? common.toString() : t('answer.totalAll'),
    dh: sum !== null ? m.dh(sum) : null, dhCell: sum !== null ? formatAmount(sum, lang) : null, pct: percent(ONE),
  };
  const rest = a.paid && a.paid.rest > 0n ? t('answer.rest', { count: Number(a.paid.rest) }) : null;

  const out = r.excluded.map((e) => `${groupName(e.heir, e.count, t, true)}${t('answer.colon')}${outWords(e, r, t, lang, true)}`);

  const assumed = [
    c.will || c.tanzil ? t('answer.paper.a.will') : t('answer.paper.a.noWill'),
    c.later.length ? t('answer.paper.a.later') : t('answer.paper.a.noLater'),
    ...(c.later.length && r.rules.code === '1958' ? [t('answer.later.today')] : []),
    t('answer.paper.a.muslim'),
    t('answer.paper.a.present'),
    ...(a.money ? [t('answer.paper.a.money')] : []),
    c.died ? t('answer.paper.a.died', { date: c.died.length === 4 ? c.died : longDay(c.died, lang) }) : t('answer.paper.a.after2004'),
  ];

  // Every article the answer rests on, in the code's order.
  const cites: Cite[] = [
    ...r.lines.flatMap((l) => l.cites), ...r.excluded.flatMap((e) => e.cites),
    // Written here in today's numbers, said in the numbers of the book the case is counted by.
    ...inBook(r.rules.code, [
      ...(r.named ? [NAMED_ART[r.named]] : []), ...(r.bequest.length ? BEQUEST_ARTS : []), ...(r.radd ? [[349, 6] as Cite] : []),
      ...(r.will ? (r.will.cut === 'heir' ? [280] : [277, 303]) : []), ...(r.tanzil ? [[317, r.tanzil.by === 'rise' ? 1 : 2] as Cite] : []),
      ...(a.money && a.money.net !== a.money.gross ? [322] : []),
    ]),
    ...(a.shares.some((s) => s.group === 'treasury') ? treasuryCites(r.rules.code) : []),
  ];
  const seen = new Set<string>();
  const articles = cites.filter((x) => { const k = String(x); if (seen.has(k)) return false; seen.add(k); return true; })
    .sort((x, y) => article(x) - article(y) || (paragraph(x) ?? 0) - (paragraph(y) ?? 0)).map((x) => citeLabel(x, t, r.rules.code === '1958')).join(' · ');

  return {
    title: t('answer.paper.title'),
    died: t(`answer.paper.died_${c.deceased}`),
    family: family.join(sep),
    laterHead: later.length ? t('answer.paper.laterHead', { after }) : null,
    later,
    ledger, before, lines, total, rest, out, assumed, articles,
    common,
    money: Boolean(a.paid),
    day: t('answer.paper.day', { date: longDay(todayIso(), lang) }),
    version: t('shell.version', { v: ENGINE, rules: t(`shell.rules.${r.rules.code}`) }),
    code: t('shell.code', { code: `\u2066${code}\u2069` }),
  };
}

/** The same paper as a message: plain lines, the link at its end so the receiver opens the same family. */
function paperText(p: Model, t: T): string {
  const col = t('answer.colon');
  const head = (x: string) => `${x}${col.trimEnd()}`;
  const lines = [
    `${p.title} · ${t('shell.title')}`,
    `${p.died} ${p.family}.`,
    ...(p.laterHead ? [p.laterHead, ...p.later] : []),
    ...p.ledger.map(([k, v]) => `${k}${col}${v}`),
    ...p.before,
    '',
    head(t('answer.paper.parts')),
    ...p.lines.map((l) => `${l.head ? `${l.head}\n` : ''}${l.under ? '  - ' : ''}${l.who}${col}${[l.share, l.dh, l.pct].filter(Boolean).join(' · ')}`),
    `${p.total.who}${col}${[p.total.share, p.total.dh].filter(Boolean).join(' · ')}`,
    ...(p.rest ? [p.rest] : []),
    ...(p.out.length ? ['', head(t('answer.out.heading')), ...p.out] : []),
    '',
    head(t('answer.paper.assumed')),
    ...p.assumed.map((x) => `- ${x}`),
    `${t('answer.paper.articles')}${col}${p.articles}`,
    '',
    `${p.day} · ${p.version} · ${p.code}`,
    `${t('answer.paper.link')} ${here()}`,
  ];
  return lines.join('\n').replace(/\n{3,}/g, '\n\n');
}

/** Only the paper prints, in black on white whatever the theme, tighter, so a family fits one page: the page under it,
 *  the bars and the actions go. Kept in the component, not the stylesheet. */
const PRINT = `@media print{body>*:not([data-inh-paper]){display:none!important}html,body{overflow:visible!important;background:#fff!important}
[data-inh-paper]{position:static!important;overflow:visible!important;background:#fff!important;inset:auto!important}
[data-inh-paper],[data-inh-paper] *{color:#000!important}
[data-inh-paper] [data-paper]{background:#fff!important;border:0!important;box-shadow:none!important;margin:0!important;max-width:none!important;padding:0!important}
[data-inh-paper] [data-paper]{gap:10px!important}[data-inh-paper] [data-paper] :is(th,td){padding-block:3px!important}
[data-inh-paper] [data-paper] tr{break-inside:avoid}@page{margin:12mm}}`;

function PaperView({ c, a, code, onClose }: { c: Case; a: Ok; code: string; onClose: () => void }) {
  const { t, i18n } = useT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const p = paperModel(c, a, code, t, lang);
  const close = useRef<HTMLButtonElement>(null);
  const [name, setName] = useState('');
  const [saved, setSaved] = useState(false);
  useDismiss(onClose);
  useEffect(() => {
    close.current?.focus({ preventScroll: true });
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = overflow; };
  }, []);
  const save = () => {
    saveFamily(code, name.trim() || `${p.title} · ${longDay(todayIso(), lang)}`).then(() => setSaved(true), () => setSaved(false));
  };
  const cell = 'px-2 py-2';
  const num = `${cell} whitespace-nowrap text-end`;
  return createPortal(
    <div data-inh-paper role="dialog" aria-modal="true" aria-label={p.title} lang={lang} dir={lang === 'fr' ? 'ltr' : 'rtl'}
         className="fixed inset-0 z-50 overflow-y-auto bg-paper" style={topicColour('family')}>
      <style>{PRINT}</style>
      <div data-noprint className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-rule bg-paper px-4 py-1">
        <span className="text-body font-semibold">{p.title}</span>
        <button ref={close} type="button" onClick={onClose} className="min-h-11 px-2 text-body text-ink-soft">{t('answer.paper.close')}</button>
      </div>

      <article data-paper style={{ marginBlock: 16 }} className="mx-auto flex max-w-xl flex-col gap-4 rounded-card border border-rule bg-sheet px-5 py-6 sm:px-8">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b-2 border-ink pb-2">
          <h2 className="m-0 text-h3 font-bold">{p.title}</h2>
          <span className="text-meta text-ink-soft">{p.day}</span>
        </div>

        <div className="flex flex-col gap-1">
          <p className="m-0 text-body"><span className="font-semibold">{p.died}</span> {p.family}.</p>
          {p.laterHead ? <p className="m-0 text-body">{p.laterHead} {p.later.join(t('answer.sep'))}.</p> : null}
        </div>

        {p.ledger.length ? (
          <div className="flex flex-col gap-1">
            {p.ledger.map(([k, v], i) => (
              <div key={k} className={`flex items-baseline justify-between gap-3 ${i === p.ledger.length - 1 && p.ledger.length > 1 ? 'border-t border-rule pt-1 font-semibold' : ''}`}>
                <span className="text-body">{k}</span><bdi className="text-body tabular-nums">{v}</bdi>
              </div>
            ))}
          </div>
        ) : null}

        {p.before.length ? <div className="flex flex-col gap-1.5">{p.before.map((x, i) => <p key={i} className="m-0 text-body">{x}</p>)}</div> : null}

        <div className="flex flex-col gap-1">
          <h3 className="m-0 text-body font-semibold">{t('answer.paper.parts')}</h3>
          <table className="w-full border-collapse text-meta tabular-nums">
            <thead>
              <tr className="border-b border-ink text-ink-soft">
                <th scope="col" className={`${cell} text-start font-medium`}>{t('answer.paper.col.who')}</th>
                <th scope="col" className={`${cell} text-end font-medium`}>{p.common ? t('answer.paper.col.share', { n: p.common.toString() }) : t('answer.paper.col.share1')}</th>
                {p.money ? <th scope="col" className={`${cell} text-end font-medium`}>{t('answer.paper.col.dh')}</th> : null}
                <th scope="col" className={`${cell} text-end font-medium`}>{t('answer.paper.col.pct')}</th>
              </tr>
            </thead>
            <tbody>
              {p.lines.map((l, i) => (
                <PaperRow key={i} l={l} money={p.money} cell={cell} />
              ))}
              <tr className="border-t-2 border-ink font-semibold">
                <th scope="row" className={`${cell} text-start`}>{p.total.who}</th>
                <td className={num}>{p.total.cell}</td>
                {p.money ? <td className={num}>{p.total.dhCell}</td> : null}
                <td className={num}>{p.total.pct}</td>
              </tr>
            </tbody>
          </table>
          {p.rest ? <p className="m-0 text-meta text-ink-soft">{p.rest}</p> : null}
        </div>

        {p.out.length ? (
          <div className="flex flex-col gap-1">
            <h3 className="m-0 text-body font-semibold">{t('answer.out.heading')}</h3>
            {p.out.map((x, i) => <p key={i} className="m-0 text-meta">{x}</p>)}
          </div>
        ) : null}

        <div className="flex flex-col gap-1">
          <h3 className="m-0 text-body font-semibold">{t('answer.paper.assumed')}</h3>
          <ul className="m-0 flex list-disc flex-col gap-0.5 ps-5 text-meta">{p.assumed.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>

        <p className="m-0 text-meta"><span className="font-semibold">{t('answer.paper.articles')}</span>{t('answer.colon')}{p.articles}</p>

        <div className="flex flex-col gap-1 border-t border-rule pt-3 text-meta text-ink-soft">
          <p className="m-0">{p.version}</p>
          <p className="m-0" style={{ overflowWrap: 'anywhere' }}>{p.code}</p>
        </div>
      </article>

      <div data-noprint className="mx-auto flex max-w-xl flex-col gap-3 px-4 pb-10">
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={() => window.print()}>{t('answer.paper.print')}</Button>
          <Button onClick={() => whatsapp(paperText(p, t))}>{t('answer.paper.send')}</Button>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="inh-paper-name" className="text-body font-semibold">{t('answer.paper.name')}</label>
          <div className="flex flex-wrap gap-2">
            <input id="inh-paper-name" dir="auto" value={name} maxLength={60} placeholder={t('answer.paper.namePlaceholder')}
                   onChange={(e) => { setName(e.target.value); setSaved(false); }}
                   className="h-12 min-w-0 flex-1 rounded-control border border-field bg-sheet px-3 text-body" />
            <Button onClick={save}>{t('answer.paper.save')}</Button>
          </div>
          <p aria-live="polite" className="m-0 text-meta text-ink-soft">{saved ? t('answer.paper.saved') : ''}</p>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function PaperRow({ l, money: withMoney, cell }: { l: Model['lines'][number]; money: boolean; cell: string }) {
  return (
    <>
      {l.head ? (
        <tr>
          <th scope="rowgroup" colSpan={withMoney ? 4 : 3} className={`${cell} text-start font-semibold`}>{l.head}</th>
        </tr>
      ) : null}
      <tr className="border-b border-rule">
        <th scope="row" className={`${cell} text-start font-normal ${l.under ? 'ps-5' : ''}`}>{l.who}</th>
        <td className={`${cell} whitespace-nowrap text-end`}>{l.cell}</td>
        {withMoney ? <td className={`${cell} whitespace-nowrap text-end`}>{l.dhCell}</td> : null}
        <td className={`${cell} whitespace-nowrap text-end`}>{l.pct}</td>
      </tr>
    </>
  );
}
