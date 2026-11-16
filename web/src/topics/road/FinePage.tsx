import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, DayChips, Listen, SourceFold, SourceMark } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { sharePicture } from '../kit/tool/picture';
import { toolLink, useToolState } from '../kit/tool/state';
import { fine, OFFENCES, type Start } from './rules/fines';
import { useFines } from './rules/rates';
import { OffenceTiles } from './OffenceTiles';
import { Staircase } from './Staircase';
import { articleLabel, useRoadT } from './strings';
import { todayIso } from '@/shared/services/today';

const today = () => todayIso();
const art = (n: string) => `/ma/loi/52-05/art_${n}`;

/** «شحال غادي نخلص؟» (R11 of the road plan; A1, A3, A4, F1–F10 of the road tools review): the price today on top,
 *  the staircase of the three prices over the days, paying and contesting side by side, the cases with no settlement
 *  asked as questions. Shown before a professional's review by an editorial call (Q1). It never says whether to pay
 *  or to contest. Everything is worked out on the phone; the inputs live in the address, so a link reopens them. */
export default function FinePage({ slug }: { slug: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA');
  const dh = (n: number) => t('dh', { amount: nf.format(n) });
  const [s, set] = useToolState({ o: 'speed20', s: 'radar', d: today(), again: '', delit: '' });
  const offence = OFFENCES.find((o) => o.key === s.o) ?? OFFENCES[0];
  const start = (s.s === 'officer' ? 'officer' : 'radar') as Start;
  const walk = offence.klass === 'walk';
  const rates = useFines(slug, s.d);
  const r = fine(offence, start, s.d, rates.values);
  const now = today();
  const at = r.steps.findIndex((x) => now <= x.until);
  const noDeal = !walk && (s.delit === 'yes' || (offence.klass === 1 && s.again === 'yes'));
  const labels = t(walk ? 'fine.steps.walk' : `fine.steps.${start}`, { returnObjects: true }) as string[];
  const short = t(walk ? 'fine.stepsShort.walk' : `fine.stepsShort.${start}`, { returnObjects: true }) as string[];
  const next = at >= 0 && at < r.steps.length - 1 ? r.steps[at + 1] : null;
  const left = at >= 0 ? daysUntil(r.steps[at].until) : -1;
  const pointsLine = r.points ? t('fine.pointsTaken', { points: t('points_n', { count: r.points }) }) : t('fine.noPoints');

  const over = noDeal ? t('fine.noDealOver') : at < 0 ? t('fine.lateOver') : t('fine.payToday', { date: dayWords(now, lang, false) });
  const value = noDeal ? t('fine.noDealValue') : at < 0 ? t('fine.lateValue') : r.steps[at].amount;
  const under = noDeal ? t('fine.noDealLine')
    : at < 0 ? t('fine.afterwards')
      : next ? (left <= 0 ? t('fine.fromTomorrow', { amount: dh(next.amount) }) : t('fine.next', { amount: dh(next.amount), days: t('daysLeft', { count: left }) }))
        : t('fine.lastDay', { date: dayWords(r.steps[at].until, lang) });

  const spoken = [over, typeof value === 'number' ? dh(value) : value, under, pointsLine].join('. ');
  const message = [t('fine.message'), t(`offences.${offence.key}`),
    ...r.steps.map((x, i) => `${labels[i]}: ${dh(x.amount)} (${t('fine.until', { date: dayWords(x.until, lang) })})`),
    pointsLine, here()].join('\n');
  const picture = () => sharePicture({
    dir: lang === 'fr' ? 'ltr' : 'rtl', colour: getComputedStyle(document.documentElement).getPropertyValue('--color-t-road').trim() || '#8a5a00',
    over: `${t(`offences.${offence.key}`)} · ${over}`, value: typeof value === 'number' ? dh(value) : value,
    lines: [under, pointsLine, ...r.steps.map((x, i) => `${short[i]}: ${dh(x.amount)} · ${dayWords(x.until, lang, false)}`)],
    source: r.cites.slice(0, 4).map(articleLabel).join(' · '), site: t('site'),
  }, `fine-${offence.key}`);
  const remind = () => calendarFile(r.steps.slice(Math.max(0, at)).map((x, i) => ({
    date: x.until, title: t('fine.remindTitle', { amount: dh(x.amount) }),
    detail: `${t(`offences.${offence.key}`)} — ${labels[Math.max(0, at) + i]}. ${here()}`,
  })), `fine-${offence.key}`);

  return (
    <KitPage slug={slug} title={t('fine.title')} lead={t('fine.lead')}>
      <AnswerCard over={over} value={value} format={dh} under={<p className="m-0">{under}</p>}
                  tone={noDeal || at < 0 ? 'warn' : 'stamp'}>
        {!noDeal ? <p className="m-0 text-meta text-ink-soft">{pointsLine}</p> : null}
      </AnswerCard>

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        {!noDeal ? <Staircase steps={r.steps} start={s.d} today={now} labels={short} money={(n) => nf.format(n)} /> : null}
        <OffenceTiles offences={OFFENCES} value={offence.key} onChange={(o) => set({ o })} label={t('fine.offence')}
                      cost={(o) => t(`classesShort.${o.klass}`)} />
        {offence.group === 'speed' ? (
          <Button to={toolLink(`/topics/${slug}/tools/speed`, {})} className="self-start">{t('fine.bySpeed')}</Button>
        ) : null}
        {walk ? null : (
          <Chips label={t('fine.start')} value={start} onChange={(v) => set({ s: v })}
                 options={[{ key: 'radar', label: t('fine.starts.radar') }, { key: 'officer', label: t('fine.starts.officer') }]} />
        )}
        <DayChips label={t(`fine.day.${walk ? 'officer' : start}`)} value={s.d} onChange={(d) => set({ d })} ago={[0, 1, 2, 7]} />
        {walk ? null : (
          <div className="flex flex-col gap-3 border-t border-rule pt-4">
            <span className="text-body font-semibold">{t('fine.dealAsk')}</span>
            {offence.klass === 1 ? (
              <Chips label={t('fine.againAsk')} value={s.again || 'no'} onChange={(v) => set({ again: v === 'no' ? '' : v })}
                     options={[{ key: 'no', label: t('no') }, { key: 'yes', label: t('yes') }]} />
            ) : null}
            <Chips label={t('fine.delitAsk')} value={s.delit || 'no'} onChange={(v) => set({ delit: v === 'no' ? '' : v })}
                   options={[{ key: 'no', label: t('no') }, { key: 'yes', label: t('yes') }]} />
          </div>
        )}
      </section>

      {noDeal ? null : (
        <section className="grid gap-3 sm:grid-cols-2" aria-label={t('fine.paths')}>
          <div className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-4">
            <h2 className="m-0 text-lead font-semibold">{t('fine.pay')}</h2>
            <p className="m-0 text-body">{at >= 0 ? t('fine.payNow', { amount: dh(r.steps[at].amount) }) : t('fine.lateValue')}</p>
            <p className="m-0 text-body">{pointsLine}</p>
            <span className="flex flex-wrap gap-1.5"><SourceMark path={art('28')} label={articleLabel(art('28'))} /><SourceMark path={art('219')} label={articleLabel(art('219'))} /></span>
          </div>
          <div className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-4">
            <h2 className="m-0 text-lead font-semibold">{t('fine.contestTitle')}</h2>
            <p className="m-0 text-body">{t('fine.contestDeposit', { amount: dh(r.deposit), date: dayWords(r.contestBy, lang) })}</p>
            <p className="m-0 text-body">{t('fine.contestTwo', { amount: dh(r.twoThirds) })}</p>
            <span className="flex flex-wrap gap-1.5">{['230', '231', '234'].map((n) => <SourceMark key={n} path={art(n)} label={articleLabel(art(n))} />)}</span>
          </div>
        </section>
      )}

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        {noDeal ? <p className="m-0 text-body">{t('fine.noDeal')}</p> : <p className="m-0 text-body">{t('fine.afterwards')}</p>}
        {start === 'radar' && !walk ? <p className="m-0 text-meta text-ink-soft">{t('fine.radarMargin')}</p> : null}
        <Note tone="law" quiet><p className="m-0 text-meta">{t('fine.notice')}</p></Note>
        <p className="m-0 text-meta text-ink-soft">{t('fine.ratesFrom', { date: dayWords(rates.from, lang) })}</p>
        <SourceFold paths={[...r.cites, ...(start === 'radar' ? [art('195'), art('200')] : [art('228')])]} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
          <Button onClick={() => void picture()}>{t('picture')}</Button>
          {!noDeal && at >= 0 ? <Button onClick={remind}>{t('remind')}</Button> : null}
          <Listen text={spoken} lang={lang} />
          {r.points && !noDeal ? <Button to={toolLink(`/topics/${slug}/tools/points`, { o: offence.key })}>{t('fine.toPoints')}</Button> : null}
        </div>
      </section>
    </KitPage>
  );
}
