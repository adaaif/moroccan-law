import { Button } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, DayChips, Listen, SourceFold } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { road, type Stop } from './rules/permit';
import { articleLabel, useLandT } from './strings';
import { todayIso } from '@/shared/services/today';

/** «طريق الرخصة», the permit's road (the land review, M12): the day the file was filed → each stop the texts date,
 *  drawn as a dashed lane, the stops gone filled, the next one said on top with its days left; the lapse in red. An
 *  express permit given early starts its year from that day. The dates are what the texts set, never the commune's
 *  answer. The inputs live in the address. */
export default function PermitPage({ slug }: { slug: string }) {
  const { t, i18n } = useLandT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ d: todayIso(), g: '' });
  const stops = road(s.d, s.g || undefined);
  const today = todayIso();
  const next = stops.find((x) => x.date >= today) ?? stops[stops.length - 1];
  const left = daysUntil(next.date);
  const title = (x: Stop) => t(`permit.stops.${x.key}.title`);
  const lines = stops.map((x) => `${dayWords(x.date, lang)}: ${title(x)}`);
  const message = [t('permit.message'), ...lines, here()].join('\n');
  const remind = () => calendarFile(stops.filter((x) => x.date >= today && x.key !== 'filed')
    .map((x) => ({ date: x.date, title: title(x), detail: here() })), 'permit');

  return (
    <KitPage slug={slug} title={t('permit.title')} lead={t('permit.lead')}>
      <AnswerCard over={`${t('permit.nextOver')}: ${title(next)}`} value={dayWords(next.date, lang)}
                  under={<p className="m-0">{left > 0 ? t('clock.left', { count: left }) : left === 0 ? t('clock.left', { count: 0 }) : t('permit.done')}</p>}
                  tone={next.key === 'lapse' && left < 30 ? 'warn' : 'stamp'} />

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <DayChips label={t('permit.filed')} value={s.d} onChange={(d) => set({ d })} ago={[0, 15, 30, 60]} />
        <Chips label={t('permit.given')} value={s.g ? 'yes' : 'no'} onChange={(v) => set({ g: v === 'yes' ? (s.g || today) : '' })}
               options={[{ key: 'no', label: t('permit.notYet') }, { key: 'yes', label: t('permit.givenOn') }]} />
        {s.g ? <DayChips label={t('permit.givenOn')} value={s.g} onChange={(g) => set({ g })} ago={[0, 7, 30]} /> : null}
      </section>

      {/* The road: a dashed lane, a stop a date, the stops gone filled, the lapse in red. */}
      <section className="rounded-card bg-sheet px-5 py-5 sm:px-7">
        <ol className="relative m-0 flex list-none flex-col p-0" style={{ paddingInlineStart: 32 }}>
          <span aria-hidden="true" className="absolute"
                style={{ insetBlock: 12, insetInlineStart: 11, width: 3, background: 'repeating-linear-gradient(var(--t) 0 8px, transparent 8px 13px)' }} />
          {stops.map((x) => {
            const past = x.date < today;
            const lapse = x.key === 'lapse';
            return (
              <li key={x.key} className="relative grid gap-x-3 py-2.5" style={{ gridTemplateColumns: '1fr auto' }}>
                <span aria-hidden="true" className="absolute rounded-full"
                      style={{ insetInlineStart: -29, top: 14, width: 15, height: 15, borderWidth: 3, borderStyle: 'solid', borderColor: lapse ? 'var(--color-sign-red)' : 'var(--t)', background: past || lapse ? (lapse ? 'var(--color-sign-red)' : 'var(--t)') : 'var(--color-sheet)' }} />
                <span lang={lang} className={`text-body font-semibold ${past ? 'text-ink-soft' : ''}`}>{title(x)}</span>
                <span className="text-body font-bold tabular-nums">{dayWords(x.date, lang, x.key === 'lapse')}</span>
                <span lang={lang} className="text-meta text-ink-soft" style={{ gridColumn: '1 / -1' }}>{t(`permit.stops.${x.key}.line`)}</span>
              </li>
            );
          })}
        </ol>
        <p className="m-0 mt-2 border-t border-rule pt-3 text-body">{t('permit.after')}</p>
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <SourceFold paths={[...new Set([...stops.flatMap((x) => x.cites), '/ma/loi/12-90/art_55'])]} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
          <Button onClick={remind}>{t('remind')}</Button>
          <Listen text={lines.join('. ')} lang={lang} />
        </div>
      </section>
    </KitPage>
  );
}
