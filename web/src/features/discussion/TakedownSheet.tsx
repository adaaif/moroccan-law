import { useState } from 'react';
import { discussionApi, type Contribution } from './discussion.api';
import { Sheet } from '@/shared/components/Sheet';
import { errorText, useT } from './strings';

/** «هذه المساهمة تذكرني» (M11): a person named in a contribution asks for it to go. No account needed; it goes to
 *  the top of the reviewers' queue, and its author never learns who asked. */
export function TakedownSheet({ c, onClose }: { c: Contribution; onClose: () => void }) {
  const { t } = useT();
  const [details, setDetails] = useState('');
  const [contact, setContact] = useState('');
  const [state, setState] = useState<'' | 'busy' | 'sent'>('');
  const [error, setError] = useState<unknown>(null);
  return (
    <Sheet centered label={t('takedown.title')} onClose={onClose}>
      <h2 className="m-0 mb-2 text-lead font-semibold">{t('takedown.title')}</h2>
      {state === 'sent' ? (
        <div className="flex flex-col gap-4">
          <p role="status" className="m-0 text-body">{t('takedown.sent')}</p>
          <button type="button" onClick={onClose} className="h-11 rounded-control border border-rule text-body hover:bg-paper">{t('pictures.close')}</button>
        </div>
      ) : (
        <form className="flex flex-col gap-3" onSubmit={async (e) => {
          e.preventDefault();
          setState('busy');
          setError(null);
          try {
            await discussionApi.takedown(c.id, details, contact);
            setState('sent');
          } catch (err) {
            setError(err);
            setState('');
          }
        }}>
          <p className="m-0 text-meta text-ink-soft">{t('takedown.lede')}</p>
          <label className="flex flex-col gap-1.5 text-meta">
            {t('takedown.details')}
            <textarea dir="auto" value={details} onChange={(e) => setDetails(e.target.value)} rows={3} maxLength={500} required
                      className="rounded-control border border-field bg-paper px-3 py-2 text-body focus:border-stamp focus:bg-sheet focus:outline-none" />
          </label>
          <label className="flex flex-col gap-1.5 text-meta">
            {t('takedown.contact')}
            <input dir="auto" value={contact} onChange={(e) => setContact(e.target.value)} maxLength={200}
                   className="h-11 rounded-control border border-field bg-paper px-3 text-body focus:border-stamp focus:bg-sheet focus:outline-none" />
          </label>
          {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
          <button type="submit" disabled={!details.trim() || state === 'busy'}
                  className="h-11 self-start rounded-control bg-stamp px-6 text-body font-semibold text-on-stamp hover:bg-stamp-deep disabled:opacity-60">
            {t('takedown.send')}
          </button>
        </form>
      )}
    </Sheet>
  );
}
