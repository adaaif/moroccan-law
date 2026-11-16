import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fileName } from '@/shared/services/fileName';

/** While articles are being chosen: how many, and the two ways out — a Word file (each article with its
 *  reference, built by the server) or the browser's print to PDF (only the chosen articles print). */
export function ExportBar({ paths, onClear }: { paths: string[]; onClear: () => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const word = async () => {
    setBusy(true);
    setFailed(false);
    try {
      const r = await fetch('/api/corpus/export/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths }),
      });
      if (!r.ok) throw new Error(String(r.status));
      const url = URL.createObjectURL(await r.blob());
      const a = Object.assign(document.createElement('a'), { href: url, download: fileName('articles.docx') });
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  const pdf = () => {
    document.body.dataset.printing = 'selection';
    const done = () => {
      delete document.body.dataset.printing;
      window.removeEventListener('afterprint', done);
    };
    window.addEventListener('afterprint', done);
    window.print();
  };

  return (
    <div data-noprint role="region" aria-label={t('reading.exportTitle')}
         className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-40 border-t border-rule bg-sheet px-4 py-3 lg:bottom-0 shadow-[0_-8px_24px_-12px_rgba(30,27,58,0.3)]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
        <span className="me-auto text-body font-medium" aria-live="polite">{t('reading.selected', { count: paths.length })}</span>
        {failed ? <span role="alert" className="text-meta text-repealed">{t('reading.exportFailed')}</span> : null}
        <button type="button" disabled={!paths.length || busy} onClick={word}
                className="h-11 rounded-control bg-stamp px-5 font-medium text-on-stamp hover:bg-stamp-deep disabled:opacity-50">
          {busy ? t('corpus.loading') : t('reading.exportWord')}
        </button>
        <button type="button" disabled={!paths.length} onClick={pdf}
                className="h-11 rounded-control border border-rule px-5 hover:bg-paper disabled:opacity-50">
          {t('reading.exportPdf')}
        </button>
        <button type="button" onClick={onClear} className="h-11 rounded-control px-3 text-ink-soft hover:bg-paper">
          {t('reading.clearSelection')}
        </button>
      </div>
    </div>
  );
}
