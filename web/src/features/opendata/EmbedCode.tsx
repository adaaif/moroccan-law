import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Floating } from '@/features/corpus/reading/Popover';

/** «ضمّن»: the code that puts this article on another page (a news site, a course page). */
export function EmbedCode({ path, label }: { path: string; label: string }) {
  const { t } = useTranslation();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [copied, setCopied] = useState(false);
  const close = useCallback(() => setAnchor(null), []);
  const code = `<iframe src="${window.location.origin}/embed${path}" title="${label}" width="100%" height="420" style="border:0" loading="lazy"></iframe>`;
  return (
    <>
      <button type="button" onClick={(e) => setAnchor(anchor ? null : e.currentTarget)} aria-expanded={Boolean(anchor)}
              className="text-ink-soft hover:text-stamp">
        {t('data.embedAction')}
      </button>
      {anchor ? (
        <Floating anchor={anchor} onClose={close} label={t('data.embedAction')}>
          <p className="m-0 text-meta text-ink-soft">{t('data.embedHelp')}</p>
          <textarea readOnly dir="ltr" rows={4} value={code} onFocus={(e) => e.currentTarget.select()}
                    className="mt-2 w-full rounded-control border border-field bg-paper p-2 font-mono text-meta text-ink" />
          <button type="button" className="mt-2 text-meta font-medium text-stamp"
                  onClick={() => { void navigator.clipboard?.writeText(code); setCopied(true); }}>
            {copied ? t('corpus.copied') : t('data.copyCode')}
          </button>
        </Floating>
      ) : null}
    </>
  );
}
