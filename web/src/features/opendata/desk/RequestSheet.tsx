import { useEffect, useRef, useState } from 'react';
import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import {
  checkAccept, dayOr, checkLine, due, granted, heldWords, iso, linkOf, LINE_MOST, num, partnerNumber, REASONS, restateAccept,
  SIZES, sizeName, type Letter, type Programme, type RequestSheet as Sheet, type Size,
} from '../desk';
import { deskApi, useActed, useRequestSheet } from '../desk.api';
import { useD } from '../desk.strings';
import { Failed, Refusal } from './bits';
import { AccountPart, Facts, History, LetterView, Part, SheetHead } from './common';

type Act = 'accept' | 'ask' | 'decline';
/** What the sheet says once an act went. */
const DONE: Record<Act, string> = { accept: 'act.accepted', ask: 'act.asked', decline: 'act.declined' };

/**
 * A request's sheet: the six answers, the account behind them, its earlier requests, the access it holds and, for a
 * change request, what it holds now against what it asks; its history. At its foot, in thumb reach, the three acts,
 * only when this superuser may decide it. Each act shows the letter the person will read before it goes.
 */
export function RequestSheetView({ id, programme, onClose, onAccess }: {
  id: number; programme?: Programme; onClose: () => void; onAccess: (id: number) => void;
}) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const q = useRequestSheet(id);
  const [act, setAct] = useState<Act | null>(null);
  const [done, setDone] = useState<Act | null>(null);
  const top = useRef<HTMLDivElement>(null);
  // Another request opened in the same place starts at its top, with nothing chosen.
  const [shown, setShown] = useState(id);
  if (shown !== id) { setShown(id); setAct(null); setDone(null); }
  useEffect(() => { top.current?.querySelector<HTMLElement>('h2')?.focus({ preventScroll: true }); }, [id, q.isSuccess]);

  if (q.isPending) return <div className="dk-sheet"><SheetHead title={t('sheet.loading')} line={[]} onClose={onClose} /></div>;
  if (q.isError) return <div className="dk-sheet"><SheetHead title="" line={[]} onClose={onClose} /><Failed error={q.error} retry={() => void q.refetch()} /></div>;
  const s = q.data;
  const r = s.request;
  const d = due(t, r.days_left);
  const line = [
    t(`kinds.${r.kind}`, { defaultValue: r.kind }),
    r.change_of ? <span className="dk-mark change">{t('row.change')}</span> : null,
    d.words ? <span className={`dk-due ${d.mark}`}>{d.words}</span> : t(`row.states.${r.state}`),
    r.answered ? <span className="dk-mark answered">{t('row.answered')}</span> : null,
  ];
  return (
    <div className="dk-sheet" ref={top}>
      <SheetHead title={r.name || t('log.noName')} line={line} onClose={onClose} />
      {done ? <p role="status" className="dk-done">{t(DONE[done])}</p> : null}
      <Answers s={s} />
      {r.change_of && r.holds ? <ChangeAsked s={s} /> : null}
      <AccountPart a={s.account} />
      <Earlier s={s} />
      <Part title={t('sheet.holds')}>
        {s.access ? (
          <button type="button" className="dk-link-row" onClick={() => onAccess(s.access!.id)}>
            <span>{heldWords(t, s.access, lang)}</span>
            <small>{s.access.state === 'live' ? t('access.state.live') : t(`ended.${s.access.ended_reason || 'expired'}`)} · {t('sheet.openAccess')}</small>
          </button>
        ) : <p className="dk-small">{t('sheet.holdsNone')}</p>}
      </Part>
      <History events={s.history} />
      {s.may_decide ? (
        act ? <ActForm key={act} act={act} s={s} programme={programme} onCancel={() => setAct(null)}
                       onDone={() => { setDone(act); setAct(null); }} />
          : <Foot onAct={setAct} />
      ) : <Standing s={s} />}
    </div>
  );
}

/** The six answers, the terms the person accepted, what was asked and answered. */
function Answers({ s }: { s: Sheet }) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const r = s.request;
  const link = linkOf(r.runs_at);
  const rows: [string, React.ReactNode, boolean?][] = [
    [t(r.change_of ? 'sheet.fields.why' : 'sheet.fields.purpose'), r.purpose, true],
    [t('sheet.fields.wants'), granted(t, r.wants_api, r.wants_data)],
  ];
  if (r.wanted_size) rows.push([t('sheet.fields.size'), sizeName(t, r.wanted_size)]);
  rows.push([t('sheet.fields.runs_at'), r.runs_at ? (link ? <a href={link} target="_blank" rel="noreferrer noopener" dir="ltr">{r.runs_at}</a> : r.runs_at) : t('sheet.notSaid'), true]);
  if (r.volume) rows.push([t('sheet.fields.volume'), t(`volumes.${r.volume}`, { defaultValue: r.volume })]);
  rows.push([t('sheet.fields.commercial'), t(r.commercial ? 'yes' : 'no')]);
  rows.push([t('sheet.fields.terms'), dayOr(r.terms, lang)]);
  rows.push([t('sheet.fields.sent'), dayOr(r.created_at, lang)]);
  if (r.asked) rows.push([t('sheet.fields.asked'), r.asked, true]);
  if (r.answer) rows.push([t('sheet.fields.answer'), r.answer, true]);
  return <Part title={t('sheet.answers')}><Facts rows={rows} /></Part>;
}

/** For a change request: what its access holds now, beside what it asks. */
function ChangeAsked({ s }: { s: Sheet }) {
  const { t } = useD();
  const r = s.request;
  const now = r.holds!;
  return (
    <Part title={t('sheet.change')}>
      <table className="dk-compare">
        <thead><tr><th scope="col" /><th scope="col">{t('sheet.now')}</th><th scope="col">{t('sheet.asks')}</th></tr></thead>
        <tbody>
          <tr><th scope="row">{t('granted.api')}</th><td>{t(now.api ? 'yes' : 'no')}</td><td className={r.wants_api !== now.api ? 'moved' : ''}>{t(r.wants_api ? 'yes' : 'no')}</td></tr>
          <tr><th scope="row">{t('granted.data')}</th><td>{t(now.data ? 'yes' : 'no')}</td><td className={r.wants_data !== now.data ? 'moved' : ''}>{t(r.wants_data ? 'yes' : 'no')}</td></tr>
          <tr><th scope="row">{t('act.size')}</th><td>{sizeName(t, now.size)}</td>
            <td className={r.wanted_size && r.wanted_size !== now.size ? 'moved' : ''}>{r.wanted_size ? sizeName(t, r.wanted_size) : t('sheet.sameSize')}</td></tr>
        </tbody>
      </table>
    </Part>
  );
}

function Earlier({ s }: { s: Sheet }) {
  const { t, i18n } = useD();
  return (
    <Part title={t('sheet.earlier')}>
      {s.earlier.length ? (
        <ul className="dk-plain">
          {s.earlier.map((e) => (
            <li key={e.id}>
              {t('sheet.earlierLine', { date: dayOr(e.created_at, i18n.language),
                what: e.change_of ? `${t('row.change')}: ${granted(t, e.wants_api, e.wants_data)}` : granted(t, e.wants_api, e.wants_data),
                state: e.state === 'declined' && e.reason ? `${t('row.states.declined')} (${t(`reasons.${e.reason}`)})` : t(`row.states.${e.state}`) })}
            </li>
          ))}
        </ul>
      ) : <p className="dk-small">{t('sheet.earlierNone')}</p>}
    </Part>
  );
}

/** Why there is nothing to decide: it was decided, it waits for its account, or it is this superuser's own. */
function Standing({ s }: { s: Sheet }) {
  const { t, i18n } = useD();
  const r = s.request;
  const date = dayOr(r.decided_at, i18n.language);
  // Still open, it is this superuser's own: someone else decides it.
  const line = r.state === 'accepted' ? t('sheet.decidedAccepted', { date, by: iso(r.decided_by ?? '—') })
    : r.state === 'declined' ? t('sheet.decidedDeclined', { date, reason: t(`reasons.${r.reason}`, { defaultValue: r.reason }) })
      : t('sheet.own');
  return <p className="dk-standing">{line}</p>;
}

/** The three acts, at the foot of the sheet where a thumb reaches. */
function Foot({ onAct }: { onAct: (a: Act) => void }) {
  const { t } = useD();
  return (
    <div className="dk-foot acts" role="group" aria-label={t('act.label')}>
      <Button variant="primary" onClick={() => onAct('accept')}>{t('act.accept')}</Button>
      <Button onClick={() => onAct('ask')}>{t('act.ask')}</Button>
      <Button className="dk-quiet-danger" onClick={() => onAct('decline')}>{t('act.decline')}</Button>
    </div>
  );
}

type Form = { api: boolean; data: boolean; size: Size; minute: string; calls: string; articles: string; ends_on: string; line: string; reason: string };

/**
 * One act, in two steps: what it gives, asks or says, then the letter the person will read (from the server's preview),
 * with what accepting gives said once more; only the second step's button sends, with `confirm: true` for accepting.
 */
function ActForm({ act, s, programme, onCancel, onDone }: {
  act: Act; s: Sheet; programme?: Programme; onCancel: () => void; onDone: () => void;
}) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const acted = useActed();
  const change = Boolean(s.request.change_of);
  const p = s.proposed;
  const [f, setF] = useState<Form>({ api: p.api, data: p.data, size: p.size, minute: '', calls: '', articles: '',
                                     ends_on: p.ends_on ?? '', line: '', reason: '' });
  const [letter, setLetter] = useState<Letter | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const shown = useRef<HTMLDivElement>(null);
  // The form comes into view when it opens; the letter, once it came, at the top of the sheet.
  useEffect(() => {
    (letter ? shown.current : box.current)?.scrollIntoView({ block: letter ? 'start' : 'nearest', behavior: 'smooth' });
  }, [letter]);
  const set = (patch: Partial<Form>) => { setF((x) => ({ ...x, ...patch })); setLetter(null); setError(null); };

  const numbers = { minute: partnerNumber(f.minute), calls: partnerNumber(f.calls), articles: partnerNumber(f.articles) };
  const partner = f.size === 'partner';
  // A change request keeps its access's end date unless it is changed here.
  const endsOn = change && f.ends_on === (p.ends_on ?? '') ? null : f.ends_on || null;
  const grant = { api: f.api, data: f.data, size: f.size, ends_on: endsOn,
                  ...(partner ? numbers : { minute: null, calls: null, articles: null }) };
  const body = act === 'accept' ? grant : act === 'ask' ? { line: f.line } : { reason: f.reason };

  const next = async () => {
    const bad = partner ? (['minute', 'calls', 'articles'] as const).find((k) => Number.isNaN(numbers[k])) : undefined;
    const local: [string, string] | null = act === 'accept' ? (checkAccept(grant, todayIso()) ?? (bad ? [bad, 'invalid'] : null))
      : act === 'ask' ? checkLine(f.line) : f.reason ? null : ['reason', 'invalid'];
    if (local) { setError(t(`errors.${local[0]}.${local[1]}`)); return; }
    setBusy(true); setError(null);
    try { setLetter(await deskApi.preview(s.request.id, { act, ...body })); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const send = async () => {
    setBusy(true); setError(null);
    try {
      const id = s.request.id;
      const sheet = act === 'accept' ? await deskApi.accept(id, grant) : act === 'ask' ? await deskApi.ask(id, f.line) : await deskApi.decline(id, f.reason);
      acted(['desk', 'request', id], sheet);
      onDone();
    } catch (e) { setError(e); setLetter(null); } finally { setBusy(false); }
  };

  const title = act === 'accept' ? t(change ? 'act.changeTitle' : 'act.acceptTitle') : t(`act.${act}Title`);
  const sendLabel = act === 'accept' ? t(change ? 'act.changeSend' : 'act.acceptSend') : t(`act.${act}Send`);
  const sizes = programme?.sizes;
  return (
    <div className="dk-act" ref={box}>
      <h3>{title}</h3>
      {act === 'accept' ? (
        <>
          <fieldset className="dk-field">
            <legend>{t('act.give')}</legend>
            <div className="dk-choices">
              <label><input type="checkbox" checked={f.api} onChange={(e) => set({ api: e.target.checked })} />{t('granted.api')}</label>
              <label><input type="checkbox" checked={f.data} onChange={(e) => set({ data: e.target.checked })} />{t('granted.data')}</label>
            </div>
          </fieldset>
          <fieldset className="dk-field">
            <legend>{t('act.size')}</legend>
            <div className="dk-choices stacked">
              {SIZES.map((k) => {
                const n = k === 'partner' ? null : sizes?.[k];
                return (
                  <label key={k}>
                    <input type="radio" name={`size-${s.request.id}`} checked={f.size === k} onChange={() => set({ size: k })} />
                    <span>
                      <b>{sizeName(t, k)}</b>{k === p.size ? <em> · {t('act.proposed')}</em> : null}
                      <small>{n ? t('act.sizeLine', { minute: num(n.minute, lang), calls: num(n.calls, lang), articles: num(n.articles, lang) }) : t('act.partnerLine')}</small>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>
          {partner ? (
            <fieldset className="dk-field">
              <legend>{t('act.numbers')}</legend>
              <p className="dk-small">{t('act.numbersLead')}</p>
              <div className="dk-numbers-in">
                {(['minute', 'calls', 'articles'] as const).map((k) => (
                  <label key={k}>
                    <span>{t(`act.${k}`)}</span>
                    <input inputMode="numeric" dir="ltr" value={f[k]} placeholder={sizes ? String(sizes.app[k]) : ''}
                           onChange={(e) => set({ [k]: e.target.value.replace(/[^\d]/g, '') })} />
                  </label>
                ))}
              </div>
            </fieldset>
          ) : null}
          <label className="dk-date">
            <span>{t('act.ends')}</span>
            <input type="date" dir="ltr" value={f.ends_on} min={todayIso()} onChange={(e) => set({ ends_on: e.target.value })} />
            {change ? <small>{t('act.endsKept')}</small> : null}
          </label>
        </>
      ) : act === 'ask' ? (
        <>
          <label className="dk-line">
            <span>{t('act.line')}</span>
            <input dir="auto" value={f.line} onChange={(e) => set({ line: e.target.value })} maxLength={LINE_MOST + 40} />
            <small className={LINE_MOST - f.line.length < 30 ? 'low' : ''}>{t('act.left', { n: Math.max(0, LINE_MOST - f.line.length) })}</small>
          </label>
          {s.questions.length ? (
            <div className="dk-again">
              <span>{t('act.again')}</span>
              {s.questions.map((q) => <button key={q} type="button" dir="auto" onClick={() => set({ line: q })}>{q}</button>)}
            </div>
          ) : null}
        </>
      ) : (
        <fieldset className="dk-field">
          <legend>{t('act.reason')}</legend>
          <div className="dk-choices stacked">
            {REASONS.map((k) => (
              <label key={k}>
                <input type="radio" name={`reason-${s.request.id}`} checked={f.reason === k} onChange={() => set({ reason: k })} />
                <span><b>{t(`reasons.${k}`)}</b><small>{t(`reasonSaid.${k}`)}</small></span>
              </label>
            ))}
          </div>
        </fieldset>
      )}
      {letter ? (
        <div className="dk-said" ref={shown}>
          {act === 'accept' ? <p className="dk-restate">{restateAccept(t, { ...grant, ends_on: grant.ends_on ?? p.ends_on }, lang, change)}</p> : null}
          <LetterView letter={letter} to={s.account.email} />
        </div>
      ) : null}
      <Refusal error={error} />
      <div className="dk-foot">
        {letter ? (
          <Button variant="primary" className={act === 'decline' ? 'dk-danger' : ''} disabled={busy} onClick={() => void send()}>{sendLabel}</Button>
        ) : <Button variant="primary" disabled={busy} onClick={() => void next()}>{t('act.next')}</Button>}
        {letter ? <Button disabled={busy} onClick={() => setLetter(null)}>{t('back')}</Button> : null}
        <Button variant="quiet" disabled={busy} onClick={onCancel}>{t('act.cancel')}</Button>
      </div>
    </div>
  );
}
