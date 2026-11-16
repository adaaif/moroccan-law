import { useTranslation } from 'react-i18next';
import { dismissInstall, install, iPhone } from '@/shared/services/install';
import '@/shared/locales/pages';

/** The one offer to put «قانون» on the home screen (U8 of the Moroccan-design review): a quiet strip over the bar on a
 *  phone, a small card in the corner on a desk. Android installs from it; an iPhone is told how. «لا، شكرا» is for good. */
export default function InstallOffer() {
  const { t } = useTranslation();
  const ios = iPhone();
  return (
    <aside aria-label={t('pages:install.title')} data-noprint
           className="fixed inset-x-3 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-30 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-card bg-sheet px-4 py-3 shadow-lg ring-1 ring-rule motion-safe:animate-[sheet-up_200ms_ease-out] sm:inset-x-auto lg:bottom-5 sm:end-5 sm:max-w-sm">
      <svg aria-hidden="true" width="26" height="30" viewBox="0 0 120 154" className="shrink-0">
        <path d="M16 164V77.2A48 48 0 1 1 104 77.2V164Z" transform="translate(0 -10)" className="fill-stamp" />
      </svg>
      <p className="m-0 min-w-0 flex-1 text-body">{ios ? t('pages:install.ios') : t('pages:install.title')}</p>
      <span className="flex gap-1">
        {ios ? null : <button type="button" onClick={() => void install()} className="min-h-11 rounded-control bg-stamp px-4 text-body font-semibold text-on-stamp">{t('pages:install.add')}</button>}
        <button type="button" onClick={dismissInstall} className="min-h-11 rounded-control px-3 text-body text-ink-soft hover:bg-paper">{t('pages:install.no')}</button>
      </span>
    </aside>
  );
}
