import { create } from 'zustand';

/** How the law reads on this device: the text's size and the page's theme («auto» follows the phone). */
export type Theme = 'auto' | 'light' | 'dark';
export type TextSize = 0 | 1 | 2;

type ReadingState = {
  size: TextSize;
  theme: Theme;
  setSize: (size: TextSize) => void;
  setTheme: (theme: Theme) => void;
};

const STORAGE_KEY = 'law.reading';

function load(): Pick<ReadingState, 'size' | 'theme'> {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Partial<ReadingState>;
    return {
      size: saved.size === 0 || saved.size === 2 ? saved.size : 1,
      theme: saved.theme === 'light' || saved.theme === 'dark' ? saved.theme : 'auto',
    };
  } catch {
    return { size: 1, theme: 'auto' };
  }
}

function save(state: Pick<ReadingState, 'size' | 'theme'>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Private mode: the choice lasts for this page only.
  }
}

/** html[data-theme] drives the night tokens in app.css; «auto» leaves it to prefers-color-scheme. */
export function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return; // the prerender, in Node
  if (theme === 'auto') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

export const useReading = create<ReadingState>((set, get) => ({
  ...load(),
  setSize: (size) => {
    set({ size });
    save({ size, theme: get().theme });
  },
  setTheme: (theme) => {
    set({ theme });
    save({ size: get().size, theme });
    applyTheme(theme);
  },
}));

applyTheme(useReading.getState().theme);

/** The law's text size, step by step: the article body, its line height. Markazi is small on its body, and larger
 *  Arabic reads faster on a screen (R15 of the for-everyone review). The middle step is the scale's `law` (P3 of
 *  the polish review: 21 px on a phone, 22 on a desk), set in Markazi 500 so the law is the loudest thing on its page (P5). */
export const LAW_SIZES = [
  'text-[1.1875rem] leading-[1.8] sm:text-[1.25rem] font-medium',
  'text-law font-medium',
  'text-[1.5rem] leading-[1.75] sm:text-[1.625rem] font-medium',
] as const;

/** The same three sizes for the French law, in Source Serif 4 (N15 of the read-and-trusted review: the same size as the
 *  Arabic law), with a Latin text's tighter leading. */
export const FRENCH_SIZES = [
  'text-[1.1875rem] leading-[1.6] sm:text-[1.25rem]',
  'text-law leading-[1.6]',
  'text-[1.5rem] leading-[1.6] sm:text-[1.625rem]',
] as const;
