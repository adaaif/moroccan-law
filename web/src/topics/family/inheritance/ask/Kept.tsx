import { useState, type FormEvent } from 'react';
import { Button } from '@/shared/components/ui';
import { longDate } from '@/features/corpus/format';
import { forgetFamily, saveFamily, useFamilies } from '@/shared/services/saved';
import { dayIn, todayIso } from '@/shared/services/today';
import { useT } from '../strings';

/** Keeping the family (IR16 of the inheritance review): «احفظ هذه العائلة» under a name the family gives, in an
 *  inline field (never the browser's prompt); the families kept on this phone, to open or forget; «ابدأ من جديد», with
 *  a way back for a slip of the finger. Shown only when there is something to keep or to reopen. Nothing is sent: the
 *  family is its code, kept in IndexedDB as «محفوظاتي» keeps articles. */
export default function Kept({ code, onLoad, onReset }: { code: string; onLoad: (code: string) => void; onReset: () => void }) {
  const { t, i18n } = useT();
  const families = useFamilies();
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState('');
  const [said, setSaid] = useState('');
  const [undo, setUndo] = useState('');
  if (!code && !families.length && !undo) return null;
  const save = (e: FormEvent) => {
    e.preventDefault();
    const n = name.trim() || t('ask.keep.untitled', { date: longDate(todayIso(), i18n.language) });
    saveFamily(code, n).then(() => setSaid(t('ask.keep.done', { name: n })), () => setSaid(t('ask.keep.failed')));
    setNaming(false);
    setName('');
  };
  const restart = () => { setUndo(code); setSaid(''); onReset(); };
  return (
    <div className="flex flex-col gap-2 border-t border-rule pt-3">
      {naming ? (
        <form onSubmit={save} className="flex flex-wrap items-end gap-2">
          <label className="flex min-w-0 flex-1 flex-col gap-1">
            <span className="text-meta font-semibold">{t('ask.keep.name')}</span>
            <input dir="auto" autoFocus value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder={t('ask.keep.placeholder')}
                   className="h-11 rounded-control border border-field bg-sheet px-3 text-body" />
          </label>
          <Button variant="primary" type="submit">{t('ask.keep.save')}</Button>
          <Button variant="quiet" onClick={() => setNaming(false)}>{t('ask.keep.cancel')}</Button>
        </form>
      ) : code ? (
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => { setNaming(true); setSaid(''); }}>{t('ask.keep.start')}</Button>
          <Button variant="quiet" onClick={restart}>{t('shell.restart')}</Button>
        </div>
      ) : null}
      {said ? <p role="status" className="m-0 text-meta text-ink-soft">{said}</p> : null}
      {undo && !code ? (
        <p role="status" className="m-0 flex flex-wrap items-center gap-x-2 text-meta text-ink-soft">
          {t('ask.keep.cleared')}
          <button type="button" onClick={() => { onLoad(undo); setUndo(''); }} className="min-h-11 font-semibold text-stamp">{t('ask.keep.back')}</button>
        </p>
      ) : null}
      {families.length ? (
        <div className="flex flex-col">
          <p className="m-0 text-meta text-ink-soft">{t('ask.keep.list')}</p>
          <ul className="m-0 flex list-none flex-col p-0">
            {families.map((f) => (
              <li key={f.code} className="flex items-center gap-x-3 border-t border-rule first:border-t-0">
                <button type="button" onClick={() => { onLoad(f.code); setUndo(''); }} aria-current={f.code === code ? 'true' : undefined}
                        className="flex min-h-11 min-w-0 flex-1 flex-col items-start justify-center py-1 text-start">
                  <span dir="auto" className={`text-body ${f.code === code ? 'font-semibold text-ink' : 'text-stamp'}`}>{f.name}</span>
                  <span className="text-meta text-ink-soft">{longDate(dayIn(new Date(f.savedAt)), i18n.language)}</span>
                </button>
                <button type="button" onClick={() => void forgetFamily(f.code)} aria-label={t('ask.keep.forgetNamed', { name: f.name })}
                        className="h-11 px-2 text-meta text-ink-soft hover:text-stamp">
                  {t('ask.keep.forget')}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
