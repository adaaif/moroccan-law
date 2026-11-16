import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '@/shared/services/api';
import { useNoIndex } from './noindex';
import { errorText, useT } from './strings';
import { usePageTitle } from '@/shared/services/title';
import { Page } from '@/shared/components/ui';

/** /letters/stop?t=…: a letter's stop link (R3), no sign-in needed. Stop this discussion's letters, or all. */
export default function LettersStopPage() {
  const { t } = useT();
  usePageTitle([t('letters.title')]);
  const [params] = useSearchParams();
  const token = params.get('t') ?? '';
  useNoIndex();
  const info = useQuery({ queryKey: ['letters', token], queryFn: () => api<{ path: string; label: string }>(`/discussion/letters/stop/?t=${encodeURIComponent(token)}`),
                          retry: false });
  const [done, setDone] = useState<'' | 'path' | 'all'>('');
  const [error, setError] = useState<unknown>(null);
  const stop = async (scope: 'path' | 'all') => {
    try {
      const r = await api<{ scope: 'path' | 'all' }>('/discussion/letters/stop/', { method: 'POST', json: { t: token, scope } });
      setDone(r.scope);
    } catch (e) {
      setError(e);
    }
  };
  return (
    <Page width="reading" className="gap-5">
      <div className="flex flex-col gap-4 rounded-control bg-sheet px-6 py-8 sm:px-10">
        <h1 className="m-0 font-law text-h1 font-semibold">{t('letters.title')}</h1>
        {info.error ? <p className="m-0 text-body text-repealed">{t('letters.invalid')}</p> : done ? (
          <p role="status" className="m-0 text-body text-in-force">{done === 'all' ? t('letters.stoppedAll') : t('letters.stoppedThis')}</p>
        ) : info.data ? (
          <>
            <p className="m-0 text-body text-ink-soft">{t('letters.lede')}</p>
            <div className="flex flex-col gap-2">
              {info.data.path ? (
                <button type="button" onClick={() => void stop('path')}
                        className="min-h-11 rounded-control border border-rule px-4 py-2 text-start text-body hover:bg-paper">
                  {t('letters.stopThis', { label: info.data.label })}
                </button>
              ) : null}
              <button type="button" onClick={() => void stop('all')}
                      className="min-h-11 rounded-control bg-stamp px-4 py-2 text-start text-body font-semibold text-on-stamp hover:bg-stamp-deep">
                {t('letters.stopAll')}
              </button>
            </div>
          </>
        ) : <p className="m-0 text-ink-soft">{t('loading')}</p>}
        {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
      </div>
    </Page>
  );
}
