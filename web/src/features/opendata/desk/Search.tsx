import { useId } from 'react';
import { useD } from '../desk.strings';
import type { Searched } from './hooks';

export function Search({ search }: { search: Searched }) {
  const { t } = useD();
  const id = useId();
  return (
    <div className="dk-search">
      <label htmlFor={id}>{t('filters.search')}</label>
      <input id={id} type="search" dir="auto" value={search.typed} onChange={(e) => search.setTyped(e.target.value)} maxLength={100} />
    </div>
  );
}
