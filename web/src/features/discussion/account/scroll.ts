import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/** Opened on a part (/account#notices, /account/settings#apps): there once the parts are drawn. */
export function useScrollToHash(ready: boolean) {
  const { hash } = useLocation();
  useEffect(() => {
    if (ready && hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView({ block: 'start' });
  }, [ready, hash]);
}
