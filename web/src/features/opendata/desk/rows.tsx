import { dateOf, due, granted, sizeName, type AccessRow, type RequestRow } from '../desk';
import { useD } from '../desk.strings';
import { Spark } from './bits';

/** A request in a list: who, the kind, what is asked, and the day its answer is due (or where it stands). */
export function RequestLine({ r, open, onOpen, quiet = false }: { r: RequestRow; open: boolean; onOpen: () => void; quiet?: boolean }) {
  const { t, i18n } = useD();
  const d = due(t, r.days_left);
  const asks = granted(t, r.wants_api, r.wants_data);
  return (
    <li>
      <button type="button" className={`dk-row ${quiet ? 'quiet' : ''}`} aria-current={open || undefined} onClick={onOpen}>
        <span className="who">
          <b><bdi>{r.name || t('log.noName')}</bdi></b>
          <small>
            {t(`kinds.${r.kind}`, { defaultValue: r.kind })} · {r.change_of ? <span className="dk-mark change">{t('row.change')}</span> : null}
            {r.change_of ? ' ' : null}{asks}{r.wanted_size ? ` · ${sizeName(t, r.wanted_size)}` : ''}
            {r.answered ? <> · <span className="dk-mark answered">{t('row.answered')}</span></> : null}
          </small>
        </span>
        <span className="end">
          {d.words ? <span className={`dk-due ${d.mark}`}>{d.words}</span>
            : <span className="dk-state" data-state={r.state}>{t(`row.states.${r.state}`)}</span>}
          <small>{t('row.sent', { date: dateOf(r.created_at, i18n.language) })}</small>
        </span>
      </button>
    </li>
  );
}

/** An access in the ledger: the holder's name and kind, what is held, the size, the end date, the last day of use, 30
 *  days as a small line drawn left to right, the live keys. */
export function AccessLine({ a, open, onOpen, renew }: { a: AccessRow; open: boolean; onOpen: () => void; renew?: () => void }) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const live = a.state === 'live';
  return (
    <li className={renew ? 'dk-with' : undefined}>
      <button type="button" className="dk-row dk-arow" aria-current={open || undefined} onClick={onOpen}>
        <span className="who">
          <b><bdi>{a.name || t('log.noName')}</bdi></b>
          <small>{t(`kinds.${a.kind}`, { defaultValue: a.kind })} · <bdi dir="ltr">@{a.username}</bdi></small>
        </span>
        <span className="held">
          <span>{granted(t, a.api, a.data)} · {sizeName(t, a.size)}</span>
          <small className={live ? '' : 'dk-gone'}>{live ? t('accesses.until', { date: dateOf(a.ends_on, lang) }) : `${t('accesses.ended')} · ${t(`ended.${a.ended_reason || 'expired'}`)}`}</small>
        </span>
        <span className="use">
          <Spark values={a.spark} label={t('accesses.spark', { n: a.calls_30 })} />
          <small>
            {/* «never used» only for an access with no call in its 30 days either: never beside a line of calls. */}
            {[a.last_used_on ? t('accesses.lastUsed', { date: dateOf(a.last_used_on, lang) }) : a.calls_30 ? null : t('accesses.neverUsed'),
              live ? (a.keys ? t('accesses.keys', { count: a.keys }) : t('accesses.keys_zero')) : null].filter(Boolean).join(' · ')}
          </small>
        </span>
      </button>
      {renew ? <button type="button" className="dk-renew" onClick={renew} aria-label={t('waiting.renewOf', { name: a.name })}>{t('waiting.renew')}</button> : null}
    </li>
  );
}
