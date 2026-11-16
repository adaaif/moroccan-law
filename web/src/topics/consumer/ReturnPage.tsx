import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, DayChips, Listen, SourceFold } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { toolLink, useToolState } from '../kit/tool/state';
import { DayStrip } from './parts';
import { canReturn, windowDays, type Channel } from './rules/withdrawal';
import { articleLabel, useConsumerT } from './strings';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();
const CHANNELS: Channel[] = ['online', 'door', 'credit', 'shop'];

/** «واش نقدر نرجعها؟» (T1 of the consumer plan): where it was bought and the day that starts the period → the
 *  last day to withdraw, the days left as a strip, and what follows (the refund's fifteen days, the sale ended with the
 *  credit); in a shop, that there is no withdrawal and the guarantee's last day. Shown before a professional's review by
 *  an editorial call (K5). It never says whether to return. The inputs live in the address. */
export default function ReturnPage({ slug }: { slug: string }) {
  const { t, i18n } = useConsumerT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ c: 'online', d: today(), conf: 'yes', svc: '', ex: '' });
  const channel = (CHANNELS.includes(s.c as Channel) ? s.c : 'online') as Channel;
  const r = canReturn({ channel, day: s.d, confirmed: s.conf !== 'no', service: s.svc === '1', excluded: s.ex === '1' });
  const now = today();

  let over: string, value: string, under: string, tone: 'stamp' | 'warn' | 'good' = 'stamp';
  if (r.kind === 'window') {
    const left = daysUntil(r.last);
    over = t('return.lastDay');
    value = dayWords(r.last, lang);
    under = left < 0 ? t('return.passed') : left === 0 ? t('return.today') : t('return.left', { count: left });
    if (left < 0) tone = 'warn';
  } else if (r.kind === 'excluded') {
    over = t('return.excludedOver'); value = t('return.none'); under = t('return.excludedLine'); tone = 'warn';
  } else {
    over = t('return.shopOver'); value = t('return.none'); under = t('return.shopLine', { date: dayWords(r.guaranteeLast, lang) }); tone = 'warn';
  }
  const after = r.kind === 'window' ? t(`return.after.${channel}`) : '';
  const spoken = [over, value, under, after].filter(Boolean).join('. ');
  const message = [t('return.message'), t(`return.channels.${channel}`), `${over}: ${value}`, under, after, here()].filter(Boolean).join('\n');
  const remind = () => r.kind === 'window' && calendarFile([{ date: r.last, title: t('return.remindTitle'), detail: `${t(`return.channels.${channel}`)}. ${here()}` }], 'return');

  return (
    <KitPage slug={slug} title={t('return.title')} lead={t('return.lead')}>
      <AnswerCard over={over} value={value} under={<p className="m-0">{under}</p>} tone={tone}>
        {r.kind === 'window' ? <div className="pt-2"><DayStrip days={windowDays(s.d, r.days)} today={now} /></div> : null}
      </AnswerCard>

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('return.where')} value={channel} onChange={(c) => set({ c })}
               options={CHANNELS.map((c) => ({ key: c, label: t(`return.channels.${c}`) }))} />
        {channel === 'shop' ? null : (
          <DayChips label={t(`return.day.${channel === 'online' && s.svc === '1' ? 'service' : channel}`)} value={s.d} onChange={(d) => set({ d })} ago={[0, 1, 2, 5]} />
        )}
        {channel === 'shop' ? <DayChips label={t('return.day.shop')} value={s.d} onChange={(d) => set({ d })} ago={[0, 1, 7, 30]} /> : null}
        {channel === 'online' ? (
          <>
            <Chips label={t('return.what')} value={s.svc === '1' ? 'service' : 'goods'} onChange={(v) => set({ svc: v === 'service' ? '1' : '' })}
                   options={[{ key: 'goods', label: t('return.goods') }, { key: 'service', label: t('return.service') }]} />
            <Chips label={t('return.confirmed')} value={s.conf === 'no' ? 'no' : 'yes'} onChange={(v) => set({ conf: v })}
                   options={[{ key: 'yes', label: t('yes') }, { key: 'no', label: t('no') }]} />
            <label className="flex min-h-11 items-start gap-3 text-body">
              <input type="checkbox" checked={s.ex === '1'} onChange={(e) => set({ ex: e.target.checked ? '1' : '' })} className="mt-1 size-5 accent-[var(--t)]" />
              <span>{t('return.exclusions')}</span>
            </label>
          </>
        ) : null}
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        {after ? <p className="m-0 text-body">{after}</p> : null}
        {r.kind === 'shop' ? <Button to={toolLink(`/topics/${slug}/tools/guarantee`, { d: s.d })} className="self-start">{t('return.toGuarantee')}</Button> : null}
        {r.kind === 'window' ? <Note tone="law" quiet><p className="m-0 text-meta">{t('return.full')}</p></Note> : null}
        <SourceFold paths={r.cites} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
          {r.kind === 'window' && daysUntil(r.last) >= 0 ? <Button onClick={remind}>{t('remind')}</Button> : null}
          {r.kind === 'window' ? <Button to={toolLink(`/topics/${slug}/tools/letters`, { l: channel === 'online' ? 'online' : channel })}>{t('return.toLetter')}</Button> : null}
          <Listen text={spoken} lang={lang} />
        </div>
      </section>
    </KitPage>
  );
}
