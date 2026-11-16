/** What this device kept under the project's first name («matn.…»: the follows, the road's practice, numbers, accident
 *  page and signs) moves to «law.…» once, before anything reads it. A key already written under the new name wins.
 *  Remove this file, and its call in main.tsx, after 15 May 2027. */
export function moveOldKeys(): void {
  try {
    for (const old of Object.keys(localStorage).filter((k) => k.startsWith('matn.'))) {
      const now = `law.${old.slice(5)}`;
      if (localStorage.getItem(now) === null) localStorage.setItem(now, localStorage.getItem(old) ?? '');
      localStorage.removeItem(old);
    }
  } catch { /* a private window without storage: nothing was kept */ }
}
