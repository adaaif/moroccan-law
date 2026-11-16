import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import type { TextDetail } from '../corpus.api';
import { longDate } from '../format';
import '@/shared/locales/pages';

/** A text's versions as a ruler, each one a link to the text as it stood then, and the law on any date
 *  (row 8): /ma/…?on=2024-01-01 shows the version in force that day. */
export default function Versions({ d }: { d: TextDetail }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [day, setDay] = useState('');
  const latest = d.versions.length - 1;
  return (
    <div className="flex flex-col gap-4">
      <ol className="m-0 flex list-none items-end gap-[3px] overflow-x-auto p-0">
        {d.versions.map((v, i) => (
          <li key={v.valid_from + i} className="flex min-w-[120px] flex-1 flex-col gap-1.5">
            <Link to={i === latest ? d.path : `${d.path}?on=${v.valid_from}`} aria-current={v.current ? 'page' : undefined}
                  className="flex flex-col gap-1.5 no-underline">
              <span className="flex flex-col leading-tight">
                <span className={`font-law text-law font-semibold ${v.current ? 'text-stamp' : 'text-ink'}`}>
                  {longDate(v.valid_from, i18n.language)}
                </span>
                <span className={`truncate text-meta ${v.current ? 'text-stamp' : 'text-ink-soft'}`}>{t(`history.kinds.${v.consolidation}`)}</span>
              </span>
              <span className={`flex h-10 items-center justify-center rounded-control text-meta font-medium ${
                v.current ? 'bg-stamp text-on-stamp' : 'bg-chip text-ink-soft hover:bg-wash hover:text-stamp'}`}>
                {v.current ? (i === latest ? t('corpus.currentVersion') : t('pages:history.shown')) : i === latest ? t('pages:history.latest') : ''}
              </span>
            </Link>
          </li>
        ))}
      </ol>
      <form className="flex flex-wrap items-center gap-2 text-meta"
            onSubmit={(e) => { e.preventDefault(); if (day) navigate(`${d.path}?on=${day}`); }}>
        <label htmlFor="law-on" className="text-ink-soft">{t('pages:history.onDate')}</label>
        <input id="law-on" type="date" value={day} onChange={(e) => setDay(e.target.value)} dir="ltr"
               className="min-h-11 rounded-control border border-field bg-sheet px-2.5 py-1.5 text-ink" />
        <button type="submit" disabled={!day} className="min-h-11 rounded-control bg-stamp px-3 py-1.5 font-medium text-on-stamp disabled:opacity-50">
          {t('pages:history.show')}
        </button>
      </form>
    </div>
  );
}
