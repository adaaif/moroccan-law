import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, DayChips, Listen, SourceFold, SourceMark } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { toolLink, useToolState } from '../kit/tool/state';
import { Periods, type Span } from './parts';
import { guarantee } from './rules/guarantee';
import { articleLabel, useConsumerT } from './strings';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();
const MONTHS = ['0', '6', '12', '24'];

/** «الضمان ديالي باقي؟» (T2 of the consumer plan): the day of delivery, movable or not, the shop's guarantee and
 *  the days in repair → the legal guarantee's last day and the shop's, on one line of time with today; what the law lets
 *  the buyer ask (DOC 556). Art. 65's seven-day notice is read as set aside (K1), and the page says so. Shown before a
 *  professional's review by an editorial call (K5). */
export default function GuaranteePage({ slug }: { slug: string }) {
  const { t, i18n } = useConsumerT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ d: today(), im: '', m: '12', r: '' });
  const months = Number(s.m) || 0;
  const repair = Math.max(0, Math.min(3650, Number(s.r) || 0));
  const g = guarantee({ delivered: s.d, immovable: s.im === '1', shopMonths: months, repairDays: repair });
  const now = today();
  const left = daysUntil(g.legalLast);
  const shopLeft = g.shopLast ? daysUntil(g.shopLast) : null;

  const over = t('guarantee.over');
  const value = dayWords(g.legalLast, lang);
  const under = left < 0 ? t('guarantee.passed') : t('guarantee.left', { count: left });
  const shopLine = g.shopLast
    ? (shopLeft! < 0 ? t('guarantee.shopPassed', { date: dayWords(g.shopLast, lang) }) : t('guarantee.shopLine', { date: dayWords(g.shopLast, lang), count: shopLeft }))
    : t('guarantee.noShop');
  const spans: Span[] = [{ from: s.d, to: g.legalLast, label: t('guarantee.legal'), tone: 'main' }];
  if (g.shopBase && g.shopLast) {
    spans.push({ from: s.d, to: g.shopBase, label: t('guarantee.shop', { count: months }), tone: 'soft' });
    if (g.shopLast > g.shopBase) spans.push({ from: g.shopBase, to: g.shopLast, label: t('guarantee.repairs', { count: repair }), tone: 'extra' });
  }
  const message = [t('guarantee.message'), `${over}: ${value}`, under, shopLine, here()].join('\n');
  const remind = () => calendarFile([{ date: g.legalLast, title: t('guarantee.remindTitle'), detail: here() },
    ...(g.shopLast && shopLeft! >= 0 ? [{ date: g.shopLast, title: t('guarantee.remindShop'), detail: here() }] : [])], 'guarantee');

  return (
    <KitPage slug={slug} title={t('guarantee.title')} lead={t('guarantee.lead')}>
      <AnswerCard over={over} value={value} under={<p className="m-0">{under}</p>} tone={left < 0 ? 'warn' : 'stamp'}>
        <p className="m-0 text-meta text-ink-soft">{shopLine}</p>
      </AnswerCard>

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Periods spans={spans} today={now} caption={t('guarantee.caption')} />
        <DayChips label={t('guarantee.delivered')} value={s.d} onChange={(d) => set({ d })} ago={[0, 30, 180, 365]} />
        <Chips label={t('guarantee.kind')} value={s.im === '1' ? 'im' : 'mov'} onChange={(v) => set({ im: v === 'im' ? '1' : '' })}
               options={[{ key: 'mov', label: t('guarantee.movable') }, { key: 'im', label: t('guarantee.immovable') }]} />
        <Chips label={t('guarantee.card')} value={MONTHS.includes(s.m) ? s.m : 'other'} onChange={(v) => set({ m: v === 'other' ? '36' : v })}
               options={[...MONTHS.map((m) => ({ key: m, label: m === '0' ? t('guarantee.noCard') : t('guarantee.months', { count: Number(m) }) })), { key: 'other', label: t('guarantee.other') }]} />
        {!MONTHS.includes(s.m) ? (
          <label className="flex flex-col gap-1.5 text-body font-semibold">{t('guarantee.monthsAsk')}
            <input type="number" inputMode="numeric" min={1} max={120} value={s.m} onChange={(e) => set({ m: e.target.value })}
                   className="h-12 w-32 rounded-control border border-field bg-sheet px-3 text-body font-normal" />
          </label>
        ) : null}
        {months ? (
          <label className="flex flex-col gap-1.5 text-body font-semibold">{t('guarantee.repairAsk')}
            <input type="number" inputMode="numeric" min={0} max={3650} value={s.r} placeholder="0" onChange={(e) => set({ r: e.target.value })}
                   className="h-12 w-32 rounded-control border border-field bg-sheet px-3 text-body font-normal" />
            <span className="text-meta font-normal text-ink-soft">{t('guarantee.repairHint')}</span>
          </label>
        ) : null}
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-lead font-semibold">{t('guarantee.askTitle')}</h2>
        <p className="m-0 text-body">{t('guarantee.ask')}</p>
        <span className="flex flex-wrap gap-1.5"><SourceMark path="/ma/code/doc/art_556" label={articleLabel('/ma/code/doc/art_556')} /><SourceMark path="/ma/loi/31-08/art_65" label={articleLabel('/ma/loi/31-08/art_65')} /></span>
        <Note tone="law" quiet><p className="m-0 text-meta">{t('guarantee.k1')}</p></Note>
        <SourceFold paths={g.cites} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
          {left >= 0 ? <Button onClick={remind}>{t('remind')}</Button> : null}
          <Button to={toolLink(`/topics/${slug}/tools/letters`, { l: 'guarantee' })}>{t('guarantee.toLetter')}</Button>
          <Button to={`/topics/${slug}/journeys/defect`}>{t('guarantee.toJourney')}</Button>
          <Listen text={[over, value, under, shopLine].join('. ')} lang={lang} />
        </div>
      </section>
    </KitPage>
  );
}
