import { useSyncExternalStore } from 'react';
import { useTranslation } from 'react-i18next';
import { useReading } from '@/shared/stores/reading';

const query = '(prefers-color-scheme: dark)';
function subscribe(changed: () => void) {
  const media = window.matchMedia(query);
  media.addEventListener('change', changed);
  return () => media.removeEventListener('change', changed);
}
const deviceDark = () => window.matchMedia(query).matches;

/** The header and reading settings share one preference, including the device's automatic mode. */
export function ThemeToggle() {
  const { t } = useTranslation();
  const theme = useReading((s) => s.theme);
  const setTheme = useReading((s) => s.setTheme);
  const automaticDark = useSyncExternalStore(subscribe, deviceDark, () => false);
  const dark = theme === 'dark' || (theme === 'auto' && automaticDark);
  return (
    <button type="button" aria-label={t('nav.nightMode')} aria-pressed={dark} title={t('nav.nightMode')}
            onClick={() => setTheme(dark ? 'light' : 'dark')}
            className="flex size-11 shrink-0 items-center justify-center rounded-control text-ink hover:bg-paper">
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {dark ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></>
          : <path d="M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13Z" />}
      </svg>
    </button>
  );
}
