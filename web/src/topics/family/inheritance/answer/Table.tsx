import { useEffect, useRef, useState } from 'react';
import { useT } from '../strings';
import Fold from './Fold';
import { tableView } from './tableView';
import type { Ok } from './words';

/** The adoul's table (IR19 of the inheritance review), folded under the family's answer: the sentence a deed writes
 *  («أصلها من 24 وتصح من 144»), then one row a group: how it inherits, the fixed share the code names, the group's
 *  shares and one person's. The groups' column is out of the base the sentence ends on when every group's part is a
 *  whole number of it, else out of the number the engine works on; its header says which. It copies as plain text. */
export default function Table({ a }: { a: Ok }) {
  const { t } = useT();
  const view = tableView(a, t);
  const [copied, setCopied] = useState<'no' | 'yes' | 'select'>('no');
  const area = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (copied === 'select') area.current?.select(); }, [copied]);
  const copy = () => {
    try {
      if (!navigator.clipboard) { setCopied('select'); return; }
      navigator.clipboard.writeText(view.text).then(() => setCopied('yes'), () => setCopied('select'));
    } catch {
      setCopied('select');
    }
  };
  return (
    <Fold title={t('answer.table.title')}>
      <p className="m-0 text-lead font-semibold">{view.sentence}</p>
      {view.applies ? <p className="m-0 text-meta text-ink-soft">{view.applies}</p> : null}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-meta tabular-nums">
          <thead>
            <tr className="border-b border-rule text-ink-soft">
              {/* Three columns on a phone: how a group inherits sits under its name. */}
              <th scope="col" className="px-2 py-2 text-start font-medium">{view.head[0]}</th>
              <th scope="col" className="px-2 py-2 text-end font-medium">{view.head[2]}</th>
              <th scope="col" className="px-2 py-2 text-end font-medium">{view.head[3]}</th>
            </tr>
          </thead>
          <tbody>
            {view.rows.map((row, i) => (
              <tr key={i} className="border-b border-rule">
                <th scope="row" className="px-2 py-2 text-start font-normal">
                  <span className="block font-semibold">{row[0]}</span>
                  {row[1] ? <span className="block text-ink-soft">{row[1]}</span> : null}
                </th>
                <td className="px-2 py-2 text-end">{row[2]}</td>
                <td className="px-2 py-2 text-end">{row[3]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-col gap-2">
        <button type="button" onClick={copy}
                className="inline-flex h-11 items-center self-start rounded-control border border-rule bg-sheet px-5 text-body text-ink hover:border-stamp hover:text-stamp">
          {t('answer.table.copy')}
        </button>
        <p aria-live="polite" className="m-0 text-meta text-ink-soft">{copied === 'yes' ? t('answer.table.copied') : copied === 'select' ? t('answer.table.select') : ''}</p>
        {copied === 'select' ? (
          <textarea ref={area} readOnly dir="auto" rows={view.rows.length + 4} value={view.text} aria-label={t('answer.table.title')}
                    className="w-full rounded-control border border-field bg-sheet px-3 py-2 text-meta" />
        ) : null}
      </div>
    </Fold>
  );
}
