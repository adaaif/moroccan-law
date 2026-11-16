import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button, Card } from '@/shared/components/ui';
import { api } from '@/shared/services/api';
import '@/shared/locales/pages';

type Turnstile = {
  render: (box: HTMLElement, options: Record<string, unknown>) => string;
  remove: (id: string) => void;
};
declare global {
  interface Window { turnstile?: Turnstile }
}

const SCRIPT = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

let loading: Promise<void> | null = null;
function loadTurnstile(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  loading ??= new Promise<void>((done, fail) => {
    const script = document.createElement('script');
    script.src = SCRIPT;
    script.async = true;
    script.onload = () => done();
    script.onerror = () => { loading = null; fail(new Error('turnstile')); };
    document.head.appendChild(script);
  });
  return loading;
}

/**
 * Past a day's reading (back/apps/corpus/services/reading.py, 4 Nov 2026: one address is given 3000 articles and printed
 * pages a day, so the law is not copied whole at once). Without Cloudflare's check the reader is told when reading comes
 * back; with it, Turnstile runs here, and passing it gives this browser a day of its own (a cookie until midnight), then
 * the page asks again.
 */
export default function ReadingLimit({ code, retry }: { code: 'check' | 'limit'; retry: () => void }) {
  const { t, i18n } = useTranslation();
  const box = useRef<HTMLDivElement>(null);
  const again = useRef(retry);
  again.current = retry;
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [round, setRound] = useState(0);

  useEffect(() => {
    if (code !== 'check') return;
    let id = '';
    let gone = false;
    setState('loading');
    (async () => {
      try {
        const { check: sitekey } = await api<{ check: string }>('/corpus/reading/');
        if (!sitekey) throw new Error('no check');
        await loadTurnstile();
        if (gone || !box.current || !window.turnstile) return;
        id = window.turnstile.render(box.current, {
          sitekey,
          language: i18n.language === 'fr' ? 'fr' : 'ar',
          size: window.innerWidth < 360 ? 'compact' : 'normal',
          callback: async (token: string) => {
            try {
              await api('/corpus/reading/', { method: 'POST', json: { token } });
              again.current();
            } catch {
              if (!gone) setState('failed');
            }
          },
          'error-callback': () => { if (!gone) setState('failed'); },
        });
        setState('ready');
      } catch {
        if (!gone) setState('failed');
      }
    })();
    return () => {
      gone = true;
      if (id) window.turnstile?.remove(id);
    };
  }, [code, i18n.language, round]);

  return (
    <Card className="flex max-w-[45rem] flex-col items-start gap-3">
      <h1 className="m-0 text-h3 font-bold">{t('pages:missing.limitTitle')}</h1>
      <p className="m-0 max-w-[52ch] text-body text-ink-soft">{t(code === 'check' ? 'pages:missing.checkLead' : 'pages:missing.limitLead')}</p>
      {code === 'check' ? (
        <>
          <div ref={box} className="min-h-[65px]" />
          {state === 'loading' ? <p role="status" className="m-0 text-body text-ink-soft">{t('pages:missing.checkLoading')}</p> : null}
          {state === 'failed' ? (
            <>
              <p role="alert" className="m-0 text-body text-repealed">{t('pages:missing.checkFailed')}</p>
              <Button variant="primary" onClick={() => setRound((n) => n + 1)}>{t('pages:missing.retry')}</Button>
            </>
          ) : null}
        </>
      ) : null}
      <Link to="/saved" className="inline-flex min-h-11 items-center text-body font-medium no-underline">{t('nav.saved')}</Link>
    </Card>
  );
}
