import { useTranslation } from 'react-i18next';
import { useReading, type TextSize, type Theme } from '@/shared/stores/reading';
import '@/shared/locales/pages';

/** How the law reads on this device: its size and the night. In the reading bar, and in «أنا» (P18 of
 *  the polish review: a reader looking for the night found it only inside a text). */
export function ReadingSettings() {
  const { t } = useTranslation();
  const { size, theme, setSize, setTheme } = useReading();
  const sizes: TextSize[] = [0, 1, 2];
  const themes: Theme[] = ['auto', 'light', 'dark'];
  const choice = (on: boolean) => `min-h-11 flex-1 rounded-control border ${on ? 'border-stamp bg-wash text-stamp' : 'border-field'}`;
  return (
    <>
      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 text-meta text-ink-soft">{t('reading.textSize')}</legend>
        <div className="flex gap-2">
          {sizes.map((s) => (
            <button key={s} type="button" aria-pressed={size === s} onClick={() => setSize(s)} aria-label={t(`pages:sizes.${s}`)}
                    className={`${choice(size === s)} font-law ${['text-lead', 'text-law', 'text-h2'][s]}`}>
              أ
            </button>
          ))}
        </div>
      </fieldset>
      <fieldset className="m-0 mt-4 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 text-meta text-ink-soft">{t('reading.theme')}</legend>
        <div className="flex gap-2">
          {themes.map((x) => (
            <button key={x} type="button" aria-pressed={theme === x} onClick={() => setTheme(x)} className={`${choice(theme === x)} text-meta`}>
              {t(`reading.theme_${x}`)}
            </button>
          ))}
        </div>
      </fieldset>
    </>
  );
}
