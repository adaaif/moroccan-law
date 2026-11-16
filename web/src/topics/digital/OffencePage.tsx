import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, DayChips, SourceFold, SourceMark } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { OFFENCES, SITUATIONS, lapses, spell, type Range, type Situation } from './rules/offence';
import { Sheet, Thread, type Message } from './parts';
import { articleLabel, useDigitalT, useMoney } from './strings';

const JOURNEY: Record<Situation, string> = {
  hacked: 'journeys/hacked', altered: 'journeys/hacked', scam: 'journeys/scam', extortion: 'journeys/extortion',
  intimate: 'journeys/extortion', montage: 'journeys/defamed', harassment: 'journeys/extortion', defamation: 'journeys/defamed',
  insult: 'journeys/defamed', data: 'journeys/cndp',
};

/** «شنو كيقول القانون على اللي وقع ليا؟» (the digital review): what happened online → the law answering in a
 *  conversation: the offence and its article, the penalty as printed, the heavier one a text writes and when, whether the
 *  victim's complaint is needed, where to complain, and the last day before the prescription from the day of the facts.
 *  It names the texts; the court qualifies and decides. It waits for a person's check. The inputs live in the address. */
export default function OffencePage({ slug }: { slug: string }) {
  const { t, i18n } = useDigitalT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const money = useMoney();
  const [s, set] = useToolState({ w: 'extortion', a: 'no', d: todayIso() });
  const what = (SITUATIONS.includes(s.w as Situation) ? s.w : 'extortion') as Situation;
  const o = OFFENCES[what];
  const heavier = Boolean(o.aggravated) && s.a === 'yes';
  const last = lapses(o, s.d);
  const left = daysUntil(last);
  const months = (m: number) => { const [n, u] = spell(m); return t(`offence.${u}`, { count: n }); };
  const prison = (r: Range) => t('offence.prisonRange', { from: months(r[0]), to: months(r[1]) });
  const fine = (r: Range) => t('offence.fineRange', { from: money(r[0]), to: money(r[1]) });
  const penalty = [o.prison ? prison(o.prison) : null, fine(o.fine)].filter(Boolean).join(o.either ? t('offence.or') : t('offence.and'));
  const chip = (path: string) => <SourceMark path={path} label={articleLabel(path)} />;

  const messages: Message[] = [
    { key: 'me', who: 'me', body: t(`offence.said.${what}`), time: dayWords(s.d, lang, false) },
    { key: 'what', who: 'them', body: <><b>{t(`offence.names.${what}`)}</b>{t('offence.punished', { penalty })}</>, chip: chip(o.path) },
  ];
  if (o.aggravated) {
    const a = o.aggravated;
    const words = a.doubled ? t('offence.doubled') : [a.prison ? prison(a.prison) : null, a.fine ? fine(a.fine) : null].filter(Boolean).join(t('offence.and'));
    messages.push({ key: 'heavier', who: 'them', warn: heavier, body: t(`offence.heavier.${a.when}`, { penalty: words }), chip: chip(a.path) });
  }
  if (o.complaint) messages.push({ key: 'complaint', who: 'them', body: t('offence.complaint'), chip: chip(o.complaint) });
  messages.push({ key: 'where', who: 'them', body: t(`offence.where.${o.where}`), chip: chip(o.wherePath) });
  messages.push({ key: 'lapse', who: 'them', warn: left < 60, body: t(o.prescription.months ? 'offence.lapseMonths' : 'offence.lapseYears', { count: o.prescription.months ?? o.prescription.years, date: dayWords(last, lang) }), chip: chip(o.prescription.path) });

  const paths = [...new Set([o.path, o.aggravated?.path, o.complaint, o.wherePath, o.prescription.path].filter(Boolean) as string[])];
  return (
    <KitPage slug={slug} title={t('offence.title')} lead={t('offence.lead')}>
      <AnswerCard over={t(`offence.names.${what}`)} tone={left < 0 ? 'warn' : 'stamp'}
                  value={o.prison ? prison(heavier && o.aggravated?.prison ? o.aggravated.prison : o.prison) : fine(o.fine)}
                  under={<p className="m-0">{left < 0 ? t('offence.lapsed') : t('offence.left', { count: left })}</p>} />
      <Sheet>
        <Chips label={t('offence.which')} value={what} onChange={(w) => set({ w })}
               options={SITUATIONS.map((k) => ({ key: k, label: t(`offence.labels.${k}`) }))} />
        {o.aggravated ? (
          <Chips label={t(`offence.ask.${o.aggravated.when}`)} value={s.a === 'yes' ? 'yes' : 'no'} onChange={(a) => set({ a })}
                 options={[{ key: 'no', label: t('offence.no') }, { key: 'yes', label: t('offence.yes') }]} />
        ) : null}
        <DayChips label={t(o.prescription.months ? 'offence.dayPublished' : 'offence.dayFacts')} value={s.d} onChange={(d) => set({ d })} ago={[0, 7, 30]} />
      </Sheet>
      <Thread messages={messages} label={t('offence.threadLabel')} />
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-body text-ink-soft">{t('offence.court')}</p>
        <SourceFold paths={paths} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, JOURNEY[what])}>{t('offence.toJourney')}</Button>
          <Button variant="quiet" to={refPath(slug, 'pages/offences')}>{t('offence.toPage')}</Button>
          <Button variant="quiet" onClick={() => whatsapp([t('offence.message'), t(`offence.names.${what}`), penalty, here()].join('\n'))}>{t('offence.share')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
