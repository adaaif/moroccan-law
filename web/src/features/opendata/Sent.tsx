import { useTranslation } from 'react-i18next';
import '@/shared/locales/pages';
import type { RequestRow } from './access';
import './locales/mine';
import { dateOf, useGranted } from './said';

/** What was sent, folded: the six answers as the account may read them (law 09-08), or for a request to change an
 *  access, what it asked to hold, the size and why; then the line asked and the answer given, when there are. */
export function Sent({ request: r, open = false }: { request: RequestRow; open?: boolean }) {
  const { t, i18n } = useTranslation('mine');
  const granted = useGranted();
  const change = r.change_of != null;
  const rows: [string, string, boolean?][] = change ? [
    ['wants', granted(r)],
    ['size', r.wanted_size ? t(`pages:access.how.size.${r.wanted_size}.t`) : ''],
    ['why', r.purpose, true],
  ] : [
    ['name', r.name, true],
    ['kind', r.kind ? t(`pages:access.form.kinds.${r.kind}`) : ''],
    ['purpose', r.purpose, true],
    ['wants', granted(r)],
    ['runs_at', r.runs_at, true],
    ['volume', r.volume ? t(`pages:access.form.volumes.${r.volume}`) : ''],
    ['commercial', t(r.commercial ? 'pages:access.form.yes' : 'pages:access.form.no')],
  ];
  if (r.asked) rows.push(['asked', r.asked, true]);
  if (r.answer) rows.push(['answer', r.answer, true]);
  return (
    <details className="ax-sent" open={open}>
      <summary>{t(change ? 'sent.summaryChange' : 'sent.summary', { date: dateOf(r.created_at, i18n.language) })}</summary>
      <dl>
        {rows.filter(([, v]) => v).map(([k, v, typed]) => (
          <div key={k}><dt>{t(`sent.fields.${k}`)}</dt><dd dir={typed ? 'auto' : undefined}>{v}</dd></div>
        ))}
      </dl>
    </details>
  );
}
