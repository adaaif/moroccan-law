import { useState } from 'react';
import { heardAt } from './audio/heard';
import { discussionApi, REASONS, type Contribution, type Reason } from './discussion.api';
import { Sheet } from '@/shared/components/Sheet';
import { clock, errorText, useT } from './strings';

/** Reporting a contribution: the reasons of a law site, a line of details, the moment in a voice. A person
 *  reviews it, and its author never learns who reported. */
export function ReportSheet({ c, onClose }: { c: Contribution; onClose: () => void }) {
  const { t } = useT();
  const [reason, setReason] = useState<Reason | null>(null);
  const [details, setDetails] = useState('');
  const moment = c.voice ? heardAt.get(c.voice.id) : undefined;
  const [atMoment, setAtMoment] = useState(Boolean(moment));
  const [state, setState] = useState<'' | 'busy' | 'sent'>('');
  const [error, setError] = useState<unknown>(null);

  const send = async () => {
    if (!reason) return;
    setState('busy');
    setError(null);
    try {
      await discussionApi.report(c.id, reason, details, atMoment && moment !== undefined ? moment : undefined);
      setState('sent');
    } catch (e) {
      setError(e);
      setState('');
    }
  };

  return (
    <Sheet centered label={t('reportSheet.title')} onClose={onClose}>
      <h2 className="m-0 mb-3 text-lead font-semibold">{t('reportSheet.title')}</h2>
      {state === 'sent' ? (
        <div className="flex flex-col gap-4">
          <p role="status" className="m-0 text-body">{t('reportSheet.sent')}</p>
          <button type="button" onClick={onClose} className="h-11 rounded-control border border-rule text-body hover:bg-paper">{t('pictures.close')}</button>
        </div>
      ) : (
        <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); void send(); }}>
          <fieldset className="m-0 border-0 p-0">
            <legend className="sr-only">{t('reportSheet.reasonLabel')}</legend>
            {REASONS.map((r) => (
              <label key={r} className="flex min-h-12 cursor-pointer items-center gap-3 border-t border-rule-soft px-1 text-body first:border-t-0">
                <input type="radio" name="reason" value={r} checked={reason === r} onChange={() => setReason(r)}
                       className="size-4 accent-[var(--color-stamp)]" />
                {t(`reasons.${r}`)}
              </label>
            ))}
          </fieldset>
          {moment !== undefined ? (
            <label className="flex items-center gap-2 text-meta">
              <input type="checkbox" checked={atMoment} onChange={(e) => setAtMoment(e.target.checked)} className="size-4 accent-[var(--color-stamp)]" />
              <span>{t('reportSheet.moment', { time: clock(moment) })}</span>
            </label>
          ) : null}
          <label className="flex flex-col gap-1.5 text-meta">
            {t('reportSheet.details')}
            <textarea dir="auto" value={details} onChange={(e) => setDetails(e.target.value)} rows={2} maxLength={500}
                      className="rounded-control border border-field bg-paper px-3 py-2 text-body focus:border-stamp focus:bg-sheet focus:outline-none" />
          </label>
          {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={!reason || state === 'busy'}
                    className="h-11 rounded-control bg-stamp px-6 text-body font-semibold text-on-stamp hover:bg-stamp-deep disabled:opacity-60">
              {t('reportSheet.send')}
            </button>
            <span className="text-meta text-ink-soft">{t('reportSheet.who')}</span>
          </div>
        </form>
      )}
    </Sheet>
  );
}
