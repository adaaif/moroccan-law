import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { api, ApiError } from '@/shared/services/api';
import { Floating } from './Popover';
import '@/shared/locales/pages';

const KINDS = ['reading', 'link', 'missing', 'other'] as const;

/** «بلّغ عن خطأ»: what is wrong in this article, the words concerned (the reader's selection, when there is
 *  one inside the article), a note. It goes to a person's review queue; nothing about the reader is kept. In the row
 *  under the article in focus of a text read from scans (`row`, UX4 of the phone-test review), it says «خطأ في
 *  القراءة؟», and its form offers the printed page to compare with (`pageHref`). */
export function ReportError({ path, label, articleId, row = false, pageHref }: {
  path: string;
  label: string;
  articleId: string;
  row?: boolean;
  pageHref?: string | null;
}) {
  const { t } = useTranslation();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [kind, setKind] = useState<(typeof KINDS)[number]>('reading');
  const [quote, setQuote] = useState('');
  const [message, setMessage] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error' | 'empty'>('idle');
  const close = useCallback(() => setAnchor(null), []);

  const open = (el: HTMLElement) => {
    // The words the reader selected in this article, if any, are what the report is about.
    const sel = window.getSelection();
    const inside = sel && sel.rangeCount && document.getElementById(articleId)?.contains(sel.anchorNode);
    setQuote(inside ? sel.toString().trim().slice(0, 1000) : '');
    setState('idle');
    setAnchor(el);
  };

  const send = async () => {
    if (!quote.trim() && !message.trim()) {
      setState('empty');
      return;
    }
    setState('sending');
    try {
      await api('/quality/reports/', { method: 'POST', json: { path, kind, quote, message } });
      setState('sent');
      setMessage('');
    } catch (e) {
      setState(e instanceof ApiError && e.codeFor('message') ? 'empty' : 'error');
    }
  };

  return (
    <>
      <button type="button" onClick={(e) => (anchor ? close() : open(e.currentTarget))} aria-expanded={Boolean(anchor)}
              className={row
                ? `inline-flex h-11 min-w-11 items-center justify-center gap-2 rounded-control px-3 text-body ${anchor ? 'bg-wash text-stamp' : 'text-ink hover:bg-paper hover:text-stamp'}`
                : 'text-ink-soft hover:text-stamp'}>
        {row ? <FlagIcon /> : null}
        {t(row ? 'pages:quality.reportRow' : 'pages:quality.report')}
      </button>
      {anchor ? (
        <Floating anchor={anchor} onClose={close} label={t('pages:quality.reportTitle', { label })}>
          {state === 'sent' ? (
            // One quiet way on, for a reader who has just compared the law with its page: the words still in doubt.
            <div role="status" className="flex flex-col items-start gap-1">
              <p className="m-0">{t('pages:quality.sent')}</p>
              <Link to="/open-source" onClick={close} className="inline-flex min-h-11 items-center text-meta font-medium">{t('nav.contribute')}</Link>
            </div>
          ) : (
            <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); void send(); }}>
              <p className="m-0 font-medium">{t('pages:quality.reportTitle', { label })}</p>
              <div role="radiogroup" aria-label={t('pages:quality.kind')} className="flex flex-wrap gap-1.5">
                {KINDS.map((k) => (
                  <button key={k} type="button" role="radio" aria-checked={kind === k} onClick={() => setKind(k)}
                          className={`h-11 rounded-full border px-3 text-meta ${kind === k ? 'border-stamp bg-wash text-stamp' : 'border-rule'}`}>
                    {t(`pages:quality.kinds.${k}`)}
                  </button>
                ))}
              </div>
              {pageHref ? (
                <Link to={pageHref} onClick={close} className="inline-flex min-h-11 items-center text-meta font-medium">
                  {t('pages:quality.comparePage')}
                </Link>
              ) : null}
              <label className="flex flex-col gap-1 text-meta">
                <span className="text-ink-soft">{t('pages:quality.quote')}</span>
                <input dir="auto" value={quote} onChange={(e) => setQuote(e.target.value)}
                       className="h-11 rounded-control border border-field bg-sheet px-3 text-ink" />
              </label>
              <label className="flex flex-col gap-1 text-meta">
                <span className="text-ink-soft">{t('pages:quality.message')}</span>
                <textarea dir="auto" rows={3} value={message} onChange={(e) => setMessage(e.target.value)}
                          className="rounded-control border border-field bg-sheet px-3 py-2 text-ink" />
              </label>
              {state === 'empty' ? <p role="alert" className="m-0 text-meta text-repealed">{t('pages:quality.empty')}</p> : null}
              {state === 'error' ? <p role="alert" className="m-0 text-meta text-repealed">{t('pages:quality.failed')}</p> : null}
              <div className="flex items-center gap-3">
                <button type="submit" disabled={state === 'sending'}
                        className="h-11 rounded-control bg-stamp px-4 font-medium text-on-stamp hover:bg-stamp-deep disabled:opacity-60">
                  {t('pages:quality.send')}
                </button>
                <span className="text-meta text-ink-soft">{t('pages:quality.privacy')}</span>
              </div>
            </form>
          )}
        </Floating>
      ) : null}
    </>
  );
}

function FlagIcon() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 21V4" /><path d="M5 4h11l-2 4 2 4H5" />
    </svg>
  );
}
