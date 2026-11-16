import { useState } from 'react';
import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { whatsapp } from '../kit/share';
import { Chips, SourceFold } from '../kit/tool/parts';
import { dayWords } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { noteUse } from '../kit/use';
import { LETTERS, filled, type Field, type LetterKey } from './rules/letters';
import { articleLabel, useConsumerT } from './strings';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();

/** «رسائل كتذكر القانون» (T8 of the consumer plan, K2): a letter filled on the phone, quoting its articles, never
 *  sent by the site. The fields stay in this page only (not in the address: a name is the reader's own). */
export default function LettersPage({ slug }: { slug: string }) {
  const { t, i18n } = useConsumerT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ l: 'online' });
  const letter = LETTERS.find((x) => x.key === s.l) ?? LETTERS[0];
  const [values, setValues] = useState<Partial<Record<Field, string>>>({ day: today() });
  const [copied, setCopied] = useState(false);
  const f = filled({ ...values, day: values.day ? dayWords(values.day, lang) : '' }, letter.fields);
  const text = t(`letters.${letter.key}.body`, { ...f, today: dayWords(today(), lang), interpolation: { escapeValue: false } });
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); noteUse('share'); setTimeout(() => setCopied(false), 2000); } catch { setCopied(false); }
  };
  return (
    <KitPage slug={slug} title={t('letters.title')} lead={t('letters.lead')}>
      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('letters.which')} value={letter.key} onChange={(l: LetterKey) => set({ l })}
               options={LETTERS.map((x) => ({ key: x.key, label: t(`letters.${x.key}.name`) }))} />
        <div className="grid gap-3 sm:grid-cols-2">
          {letter.fields.map((field) => (
            <label key={field} className="flex flex-col gap-1.5 text-body font-semibold">{t(`letters.fields.${field}`, { context: letter.key, defaultValue: t(`letters.fields.${field}`) })}
              <input type={field === 'day' ? 'date' : 'text'} dir={field === 'day' ? 'ltr' : undefined} value={values[field] ?? ''}
                     onChange={(e) => setValues({ ...values, [field]: e.target.value })}
                     className="h-12 w-full rounded-control border border-field bg-sheet px-3 text-body font-normal" />
            </label>
          ))}
        </div>
      </section>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-live="polite">
        <h2 className="m-0 text-lead font-semibold">{t('letters.preview')}</h2>
        <p lang={lang} className="m-0 whitespace-pre-line rounded-control bg-paper px-4 py-4 font-law text-law leading-relaxed">{text}</p>
        <Note tone="law" quiet><p className="m-0 text-meta">{t('letters.how')}</p></Note>
        <SourceFold paths={letter.cites} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={() => void copy()}>{copied ? t('letters.copied') : t('letters.copy')}</Button>
          <Button onClick={() => whatsapp(text)}>{t('share')}</Button>
        </div>
        <p className="m-0 text-meta text-ink-soft">{t('letters.nothingSent')}</p>
      </section>
    </KitPage>
  );
}
