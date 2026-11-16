import { useEffect, useRef, useState } from 'react';
import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import {
  dateOf, dayOr, doorName, END_REASONS, heldWords, iso, num, partnerNumber, restateChange, shift, SIZES, sizeName,
  type AccessSheet as Sheet, type Programme, type Size,
} from '../desk';
import { deskApi, useAccessSheet, useActed } from '../desk.api';
import { useD } from '../desk.strings';
import { Bars, DayNumbers, DoorList, Failed, Refusal } from './bits';
import { AccountPart, Facts, History, Part, SheetHead } from './common';

export type AccessAct = 'change' | 'renew' | 'end';
const DONE: Record<AccessAct | 'key', string> = { change: 'access.changed', renew: 'access.renewed', end: 'access.endedDone', key: 'access.keyDone' };

/** A year from a day, the same day (29 February falls back to the 28th). */
const yearAfter = (day: string) => {
  const [y, m, d] = day.split('-').map(Number);
  const last = new Date(Date.UTC(y + 1, m, 0)).getUTCDate();
  return `${y + 1}-${String(m).padStart(2, '0')}-${String(Math.min(d, last)).padStart(2, '0')}`;
};

/**
 * An access's sheet: what it holds, its size and limits, its end date; its use by day and by door; its keys, with «إنهاء
 * المفتاح» for a leaked one; its downloads; its request and its account; its history. While it is live, three acts:
 * change what it holds (a second step restates the change), renew, end with a reason (a second step). A letter tells the
 * holder each time.
 */
export function AccessSheetView({ id, start, programme, onClose }: {
  id: number; start?: AccessAct; programme?: Programme; onClose: () => void;
}) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const q = useAccessSheet(id);
  const [act, setAct] = useState<AccessAct | null>(start ?? null);
  const [done, setDone] = useState<AccessAct | 'key' | null>(null);
  const top = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(`${id}-${start ?? ''}`);
  if (shown !== `${id}-${start ?? ''}`) { setShown(`${id}-${start ?? ''}`); setAct(start ?? null); setDone(null); }
  useEffect(() => { top.current?.querySelector<HTMLElement>('h2')?.focus({ preventScroll: true }); }, [id, q.isSuccess]);

  if (q.isPending) return <div className="dk-sheet"><SheetHead title={t('sheet.loading')} line={[]} onClose={onClose} /></div>;
  if (q.isError) return <div className="dk-sheet"><SheetHead title="" line={[]} onClose={onClose} /><Failed error={q.error} retry={() => void q.refetch()} /></div>;
  const s = q.data;
  const a = s.access;
  const live = a.state === 'live';
  const state = live ? t('access.state.live')
    : t('access.state.ended', { date: dayOr(a.ended_at ?? a.ends_on, lang), reason: t(`ended.${a.ended_reason || 'expired'}`) });
  return (
    <div className="dk-sheet" ref={top}>
      <SheetHead title={a.name || t('log.noName')} onClose={onClose}
                 line={[t(`kinds.${a.kind}`, { defaultValue: a.kind }), <bdi key="u" dir="ltr">@{a.username}</bdi>,
                       <span key="s" className={live ? 'dk-live' : 'dk-gone'}>{state}</span>]} />
      {done ? <p role="status" className="dk-done">{t(DONE[done])}</p> : null}
      <Part title={t('access.holds')}>
        <p className="dk-held">{heldWords(t, a, lang)}</p>
        <Facts short rows={[
          [t('act.minute'), num(a.limits.minute, lang)],
          [t('act.calls'), num(a.limits.calls, lang)],
          [t('act.articles'), num(a.limits.articles, lang)],
          [t('access.given'), dayOr(a.created_at, lang)],
          ...(a.renewed_at ? [[t('access.renewedOn'), dayOr(a.renewed_at, lang)] as [string, string]] : []),
          ...(a.ended_by ? [[t('access.endedBy'), <bdi key="by" dir="ltr">{a.ended_by}</bdi>] as [string, React.ReactNode]] : []),
        ]} />
      </Part>
      <UsePart s={s} />
      <Keys s={s} onDone={() => setDone('key')} />
      <Part title={t('access.downloads')}>
        {s.downloads.length ? (
          <ul className="dk-plain">
            {s.downloads.map((d, i) => (
              <li key={`${d.at}-${i}`}><code dir="ltr">{d.file}</code> · {t('editions.edition', { date: dateOf(d.edition, lang) })} · {dayOr(d.at, lang)} · {t(d.by === 'key' ? 'editions.byKey' : 'editions.byAccount')}</li>
            ))}
          </ul>
        ) : <p className="dk-small">{t('access.downloadsNone')}</p>}
      </Part>
      <Part title={t('access.request')}>
        <Facts rows={[
          [t('sheet.fields.purpose'), s.request.purpose || t('sheet.notSaid'), true],
          [t('sheet.fields.runs_at'), s.request.runs_at || t('sheet.notSaid'), true],
          [t('sheet.fields.volume'), t(`volumes.${s.request.volume}`, { defaultValue: s.request.volume })],
          [t('sheet.fields.commercial'), t(s.request.commercial ? 'yes' : 'no')],
        ]} />
      </Part>
      <AccountPart a={s.account} />
      <History events={s.history} />
      {live ? (
        act ? <AccessActForm key={act} act={act} s={s} programme={programme} onCancel={() => setAct(null)}
                             onDone={() => { setDone(act); setAct(null); }} />
          : (
            <div className="dk-foot acts" role="group" aria-label={t('access.acts')}>
              <Button onClick={() => setAct('change')}>{t('access.change')}</Button>
              <Button onClick={() => setAct('renew')}>{t('access.renew')}</Button>
              <Button className="dk-quiet-danger" onClick={() => setAct('end')}>{t('access.end')}</Button>
            </div>
          )
      ) : null}
    </div>
  );
}

function UsePart({ s }: { s: Sheet }) {
  const { t } = useD();
  return (
    <Part title={t('access.use')}>
      {s.days.length ? (
        <>
          <Bars days={s.days} field="calls" title={t('use.calls')} />
          <DayNumbers days={s.days} />
          {Object.keys(s.doors).length ? (
            <>
              <h4 className="dk-sub">{t('access.byDoor')}</h4>
              <DoorList doors={s.doors} name={(door) => doorName(t, door)} />
            </>
          ) : null}
        </>
      ) : <p className="dk-small">{t('access.noUse')}</p>}
    </Part>
  );
}

/** The access's keys: their name, first characters, when made and last used; a live one may be ended, once asked. */
function Keys({ s, onDone }: { s: Sheet; onDone: () => void }) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const acted = useActed();
  const [asking, setAsking] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const end = async (key: number) => {
    setBusy(true); setError(null);
    try { acted(['desk', 'access', s.access.id], await deskApi.endKey(key)); setAsking(null); onDone(); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  return (
    <Part title={t('access.keys')}>
      {s.keys.length ? (
        <ul className="dk-keys">
          {s.keys.map((k) => (
            <li key={k.id} className={k.ended_at ? 'ended' : ''}>
              <span className="what">
                <b><bdi>{k.name || t('access.unnamed')}</bdi></b>
                <code dir="ltr">{k.prefix}…</code>
                <small>
                  {t('access.keyMade', { date: dayOr(k.created_at, lang) })} · {k.last_used_on ? t('access.keyUsed', { date: dayOr(k.last_used_on, lang) }) : t('access.keyUnused')}
                  {k.ended_at ? <> · {t('access.keyEnded', { date: dayOr(k.ended_at, lang) })}</> : null}
                </small>
              </span>
              {!k.ended_at && s.access.state === 'live' ? (
                asking === k.id ? (
                  <span className="dk-confirm">
                    <span>{t('access.endKeyWhat')}</span>
                    <span className="row">
                      <Button className="dk-danger" variant="primary" disabled={busy} onClick={() => void end(k.id)}>{t('access.endKeyYes')}</Button>
                      <Button variant="quiet" disabled={busy} onClick={() => setAsking(null)}>{t('act.cancel')}</Button>
                    </span>
                  </span>
                ) : <Button className="dk-quiet-danger" onClick={() => { setAsking(k.id); setError(null); }}>{t('access.endKey')}</Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : <p className="dk-small">{t('access.keysNone')}</p>}
      <Refusal error={error} />
    </Part>
  );
}

type Form = { api: boolean; data: boolean; size: Size; minute: string; calls: string; articles: string; ends_on: string; reason: string };

/** Changing, renewing or ending: a form, then (for a change or an end) a second step that says what will be done; only
 *  its button sends, with `confirm: true`. */
function AccessActForm({ act, s, programme, onCancel, onDone }: {
  act: AccessAct; s: Sheet; programme?: Programme; onCancel: () => void; onDone: () => void;
}) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const acted = useActed();
  const a = s.access;
  const wasPartner = a.size === 'partner';
  const today = todayIso();
  const [f, setF] = useState<Form>({
    api: a.api, data: a.data, size: a.size,
    minute: wasPartner ? String(a.limits.minute) : '', calls: wasPartner ? String(a.limits.calls) : '',
    articles: wasPartner ? String(a.limits.articles) : '', ends_on: yearAfter(today), reason: '',
  });
  const [sure, setSure] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  // The form comes into view when it opens; what it will do, once asked, at the top of the sheet.
  useEffect(() => {
    const said = sure ? box.current?.querySelector('.dk-restate') : box.current;
    said?.scrollIntoView({ block: sure ? 'start' : 'nearest', behavior: 'smooth' });
  }, [sure]);
  const set = (patch: Partial<Form>) => { setF((x) => ({ ...x, ...patch })); setSure(false); setError(null); };

  const partner = f.size === 'partner';
  const typed = { minute: partnerNumber(f.minute), calls: partnerNumber(f.calls), articles: partnerNumber(f.articles) };
  const before = { api: a.api, data: a.data, size: a.size, ...(wasPartner ? a.limits : {}) };
  // A partner's number left out stays when the access is a partner already, else it is the app size's.
  const after = { api: f.api, data: f.data, size: f.size,
                  ...(partner ? Object.fromEntries(Object.entries(typed).map(([k, n]) => [k, n ?? (wasPartner ? a.limits[k as 'minute'] : null)])) : {}) };

  const next = () => {
    if (act === 'change') {
      if (!f.api && !f.data) { setError(t('errors.wants.required')); return; }
      const bad = partner ? (['minute', 'calls', 'articles'] as const).find((k) => Number.isNaN(typed[k])) : undefined;
      if (bad) { setError(t(`errors.${bad}.invalid`)); return; }
      const same = f.api === a.api && f.data === a.data && f.size === a.size
        && (!partner || (['minute', 'calls', 'articles'] as const).every((k) => (typed[k] ?? a.limits[k]) === a.limits[k]));
      if (same) { setError(t('errors.change.nothing')); return; }
    }
    if (act === 'end' && !f.reason) { setError(t('errors.reason.invalid')); return; }
    setSure(true);
  };
  const send = async () => {
    setBusy(true); setError(null);
    try {
      const sheet = act === 'change'
        ? await deskApi.change(a.id, { api: f.api, data: f.data, size: f.size, ...(partner ? typed : {}) })
        : act === 'renew' ? await deskApi.renew(a.id, f.ends_on) : await deskApi.end(a.id, f.reason);
      acted(['desk', 'access', a.id], sheet);
      onDone();
    } catch (e) { setError(e); setSure(false); } finally { setBusy(false); }
  };

  const sizes = programme?.sizes;
  return (
    <div className="dk-act" ref={box}>
      <h3>{t(`access.${act}Title`)}</h3>
      {act === 'change' ? (
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
                    <input type="radio" name={`asize-${a.id}`} checked={f.size === k} onChange={() => set({ size: k })} />
                    <span>
                      <b>{sizeName(t, k)}</b>
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
          {sure ? <p className="dk-restate">{restateChange(t, before, after, lang)}</p> : null}
        </>
      ) : act === 'renew' ? (
        <label className="dk-date">
          <span>{t('act.ends')}</span>
          <input type="date" dir="ltr" value={f.ends_on} min={shift(today, 1)} onChange={(e) => set({ ends_on: e.target.value })} />
          <small>{t('access.renewLead')}</small>
        </label>
      ) : (
        <>
          <fieldset className="dk-field">
            <legend>{t('access.endReason')}</legend>
            <div className="dk-choices stacked">
              {END_REASONS.map((k) => (
                <label key={k}>
                  <input type="radio" name={`end-${a.id}`} checked={f.reason === k} onChange={() => set({ reason: k })} />
                  <span><b>{t(`ended.${k}`)}</b><small>{t(`endedSaid.${k}`)}</small></span>
                </label>
              ))}
            </div>
          </fieldset>
          {sure ? <p className="dk-restate">{t('access.endWhat', { name: iso(a.name || t('log.noName')) })}</p> : null}
        </>
      )}
      <p className="dk-small">{t('access.told')}</p>
      <Refusal error={error} />
      <div className="dk-foot">
        {act === 'renew' ? (
          <Button variant="primary" disabled={busy || !f.ends_on} onClick={() => void send()}>{t('access.renewYes', { date: dateOf(f.ends_on, lang) })}</Button>
        ) : sure ? (
          <Button variant="primary" className={act === 'end' ? 'dk-danger' : ''} disabled={busy} onClick={() => void send()}>
            {t(act === 'change' ? 'access.changeYes' : 'access.endYes')}
          </Button>
        ) : <Button variant="primary" disabled={busy} onClick={next}>{t('access.changeNext')}</Button>}
        {sure ? <Button disabled={busy} onClick={() => setSure(false)}>{t('back')}</Button> : null}
        <Button variant="quiet" disabled={busy} onClick={onCancel}>{t('act.cancel')}</Button>
      </div>
    </div>
  );
}
