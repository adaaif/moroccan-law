import { create } from 'zustand';

export type Tokens = { access: string; refresh: string };

type SessionState = {
  tokens: Tokens | null;
  /** Set when the server refused the session under a page: the sign-in page says so once. */
  ended: boolean;
  setTokens: (tokens: Tokens) => void;
  clear: (opts?: { ended?: boolean }) => void;
  acknowledgeEnded: () => void;
};

const STORAGE_KEY = 'law.session';

function load(): Tokens | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

export const useSession = create<SessionState>((set) => ({
  tokens: load(),
  ended: false,
  setTokens: (tokens) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    } catch {
      // Private mode: the session lasts this visit only.
    }
    set({ tokens, ended: false });
  },
  clear: (opts) => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Nothing stored.
    }
    set({ tokens: null, ended: Boolean(opts?.ended) });
  },
  acknowledgeEnded: () => set({ ended: false }),
}));
