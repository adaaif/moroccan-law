import { useState } from 'react';
import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { whatsapp } from '../kit/share';
import { AnswerCard, DayChips, SourceFold } from '../kit/tool/parts';
import { dayWords } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { Toggles } from '../papers/parts';
import { REFUSAL, RIGHTS, articles, correctBy, type Right } from './rules/letter';
import { LetterSheet, Sheet } from './parts';
import { articleLabel, useDigitalT } from './strings';

/** «طلب لشركة على معطياتي» (the digital review): the rights asked and who asks → a letter the reader copies or
 *  sends, each request naming its article of law 09.08 (7, 8, 9, 10), and, for a correction, the ten full days the
 *  company has from receiving it; then what follows a refusal (the CNDP, art. 28; the fine, art. 53). The letter's words
 *  are fixed; nothing is sent from here. It waits for a person's check. The inputs live in the address. */
export default function LetterPage({ slug }: { slug: string }) {
  const { t, i18n } = useDigitalT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ r: 'access', c: '', n: '', i: '', d: todayIso() });
  const rights = s.r.split(',').filter((r): r is Right => RIGHTS.includes(r as Right));
  const [copied, setCopied] = useState(false);
  const blank = t('letter.blank');
  const fixes = rights.includes('rectify') || rights.includes('erase');
  const lines = [
    t('letter.to', { company: s.c || blank }),
    t('letter.subject'),
    '',
    t('letter.opening', { name: s.n || blank, id: s.i || blank }),
    ...rights.map((r) => t(`letter.asks.${r}`)),
    '',
    t('letter.identity'),
    t('letter.refusal'),
    '',
    t('letter.date', { date: dayWords(todayIso(), lang) }),
    t('letter.signature', { name: s.n || blank }),
  ];
  const text = lines.join('\n');
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); } catch { setCopied(false); }
  };
  const field = (key: 'c' | 'n' | 'i', label: string, ltr = false) => (
    <label className="flex flex-col gap-1.5">
      <span className="text-body font-semibold">{label}</span>
      <input value={s[key]} dir={ltr ? 'ltr' : 'auto'} onChange={(e) => set({ [key]: e.target.value } as Partial<typeof s>)}
             className="h-12 w-full rounded-control border border-field bg-sheet px-3 text-body" style={{ maxWidth: 384 }} />
    </label>
  );
  return (
    <KitPage slug={slug} title={t('letter.title')} lead={t('letter.lead')}>
      <AnswerCard over={t('letter.over')} value={fixes ? dayWords(correctBy(s.d), lang) : t('letter.now')}
                  under={<p className="m-0">{fixes ? t('letter.fixUnder') : t('letter.nowUnder')}</p>} />
      <Sheet>
        <Toggles label={t('letter.which')} value={rights} onChange={(v) => set({ r: v.join(',') || 'access' })}
                 options={RIGHTS.map((r) => ({ key: r, label: t(`letter.rights.${r}`) }))} />
        {field('c', t('letter.company'))}
        {field('n', t('letter.name'))}
        {field('i', t('letter.id'), true)}
        {fixes ? <DayChips label={t('letter.received')} value={s.d} onChange={(d) => set({ d })} ago={[0, 3, 7]} /> : null}
        <p className="m-0 text-meta text-ink-soft">{t('letter.private')}</p>
      </Sheet>
      <LetterSheet lines={lines} dir={lang === 'fr' ? 'ltr' : 'rtl'} />
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <SourceFold paths={[...articles(rights), REFUSAL.cndp, REFUSAL.fine]} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={copy}>{copied ? t('letter.copied') : t('letter.copy')}</Button>
          <Button variant="quiet" onClick={() => whatsapp(text)}>{t('letter.share')}</Button>
          <Button variant="quiet" to={refPath(slug, 'journeys/data-request')}>{t('letter.toJourney')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
