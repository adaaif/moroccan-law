import { useEffect, useState } from 'react';

/** The reader's answer to a topic's «where do you work?» (T5 of the work plan), kept on the phone only. Every part
 *  of the page that asks hears a change at once. */
const EVENT = 'law-topic-profile';
const key = (slug: string) => `law.topic.${slug}.profile`;

function read(slug: string): string | null {
  try { return localStorage.getItem(key(slug)); } catch { return null; }
}

export function useProfile(slug: string): [string | null, (value: string | null) => void] {
  const [value, setValue] = useState(() => read(slug));
  useEffect(() => {
    const hear = () => setValue(read(slug));
    window.addEventListener(EVENT, hear);
    window.addEventListener('storage', hear);
    return () => { window.removeEventListener(EVENT, hear); window.removeEventListener('storage', hear); };
  }, [slug]);
  const set = (next: string | null) => {
    try { if (next) localStorage.setItem(key(slug), next); else localStorage.removeItem(key(slug)); } catch { /* private window */ }
    setValue(next);
    window.dispatchEvent(new Event(EVENT));
  };
  return [value, set];
}
