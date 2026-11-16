import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/** A page that loads after its link (lazy) is not there when the browser looks for its #section: found once it stands
 *  («/privacy#check» from the form, «/rules#rule-3» from a pause on the account page). */
export function useHashTarget() {
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
  }, [hash]);
}
