import { useT } from './strings';

/** Help nearby, on a discussion about a personal matter (R12 of the for-everyone review): free legal aid, a lawyer for one's
 *  own case, the units that take in women and children who suffer violence. Only 31 % know of legal aid near them.
 *  Folded to two lines so the discussion still shows on a phone. */
export function HelpNearby() {
  const { t } = useT();
  return (
    <details className="group rounded-card bg-talk-wash px-4 py-3 sm:px-5" data-noprint>
      <summary className="flex cursor-pointer list-none items-start gap-2 [&::-webkit-details-marker]:hidden">
        <svg aria-hidden="true" className="mt-0.5 shrink-0 text-talk" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
          <path d="M12 21s-7-4.4-7-9.6A4 4 0 0 1 12 8.6a4 4 0 0 1 7 2.8C19 16.6 12 21 12 21z" />
        </svg>
        <span className="flex min-w-0 flex-col">
          <span className="text-body font-bold text-talk">{t('help.title')}</span>
          <span className="text-meta text-ink-soft group-open:hidden">{t('help.summary')}</span>
        </span>
        <svg aria-hidden="true" className="ms-auto mt-1 shrink-0 text-talk transition-transform group-open:rotate-180" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </summary>
      <div className="mt-2 flex flex-col gap-2">
        <p className="m-0 text-body leading-relaxed">{t('help.legalAid')}</p>
        <p className="m-0 text-body leading-relaxed">{t('help.lawyer')}</p>
        <p className="m-0 text-body leading-relaxed">{t('help.violence')}</p>
      </div>
    </details>
  );
}
