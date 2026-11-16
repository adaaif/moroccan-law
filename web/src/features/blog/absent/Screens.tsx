import { useTranslation } from 'react-i18next';
import { n } from '../viz';
import { share } from './screens';

/**
 * Two home screens side by side: the law's, whose apps are the machines its texts still write (the telegram, the
 * typewriter, the fax, the telex), each with the count of standing texts of law that write it as its badge; and the
 * Moroccans', the ten networks the Economic, Social and Environmental Council counted in 2023, each with the share who
 * use it and, as its badge, the texts of law that name it: none. Violet is what the texts printed; the Moroccans' screen is
 * in ink. Plain tiles, never a brand's mark.
 */
export type Machine = { key: string; name: string; standing: number };
export type App = { key: string; name: string; pct: string; texts: number };

export function Screens({ machines, apps, labels }: {
  machines: Machine[];
  apps: App[];
  labels: { law: string; people: string; lawNote: string; peopleNote: string };
}) {
  const { i18n } = useTranslation('blog');
  const lang = i18n.language;
  return (
    <div className="wa-screens">
      <section className="wa-phone is-law" aria-label={labels.law}>
        <p className="wa-phone-title">{labels.law}</p>
        <ul className="wa-tiles is-four">
          {machines.map((m) => (
            <li key={m.key} className="wa-tile">
              <span className="wa-icon" aria-hidden="true"><Pictogram k={m.key} /></span>
              <span className="wa-badge" dir="ltr">{n(m.standing, lang)}</span>
              <span className="wa-tile-name">{m.name}</span>
            </li>
          ))}
        </ul>
        <p className="wa-phone-note">{labels.lawNote}</p>
      </section>
      <section className="wa-phone is-people" aria-label={labels.people}>
        <p className="wa-phone-title">{labels.people}</p>
        <ul className="wa-tiles is-ten">
          {apps.map((a) => (
            <li key={a.key} className="wa-tile">
              <span className="wa-icon is-app" aria-hidden="true"><span className="wa-pct">{share(a.pct, lang)}</span></span>
              <span className="wa-badge is-zero" dir="ltr">{n(a.texts, lang)}</span>
              <span className="wa-tile-name" dir="auto">{a.name}</span>
            </li>
          ))}
        </ul>
        <p className="wa-phone-note">{labels.peopleNote}</p>
      </section>
    </div>
  );
}

/** The four machines, drawn in one line weight: a telegram form with its pasted tape, a typewriter, a fax machine
 *  printing, a telex's punched tape. */
export function Pictogram({ k }: { k: string }) {
  const s = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <svg viewBox="0 0 40 40" width="40" height="40">
      {k === 'telegram' ? (
        <g {...s}><rect x="6" y="7" width="28" height="26" rx="2" /><path d="M10 13h12" /><rect x="10" y="18" width="20" height="5" rx="1" /><path d="M10 28h8M22 28h8" /><path d="M28 10l-3 4h3l-3 4" /></g>
      ) : k === 'typewriter' ? (
        <g {...s}><path d="M13 16V6h14v10" /><path d="M16 10h8M16 13h6" /><path d="M5 18h30l-3 15H8z" /><path d="M11 23h2M15 23h2M19 23h2M23 23h2M27 23h2M13 28h14" /></g>
      ) : k === 'fax' ? (
        <g {...s}><path d="M14 15V5h15v10" /><path d="M18 9h7M18 12h5" /><rect x="10" y="15" width="25" height="18" rx="2" /><path d="M5 17v14a2 2 0 0 0 4 0V17a2 2 0 0 0-4 0z" /><path d="M15 21h15M15 25h3M21 25h3M27 25h3M15 29h3M21 29h3M27 29h3" /></g>
      ) : (
        <g {...s}><path d="M3 14h34v12H3z" /><circle cx="8" cy="18" r="1.3" /><circle cx="13" cy="22" r="1.3" /><circle cx="18" cy="18" r="1.3" /><circle cx="18" cy="22" r="1.3" /><circle cx="23" cy="18" r="1.3" /><circle cx="28" cy="22" r="1.3" /><circle cx="33" cy="18" r="1.3" /><circle cx="33" cy="22" r="1.3" /><path d="M3 20h34" strokeDasharray="1 3" /></g>
      )}
    </svg>
  );
}
