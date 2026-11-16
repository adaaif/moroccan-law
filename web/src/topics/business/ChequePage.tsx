import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, SourceFold, SourceMark } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { DateField, Road } from '../papers/parts';
import { ARTICLES, PRESENT, recoveryFine, road, settleFine, type Where } from './rules/cheque';
import { MoneyField, Sheet } from './parts';
import { articleLabel, useBusinessT, useMoney } from './strings';

type Side = 'holder' | 'drawer';

/** «الشيك: التواريخ والغرامات» (the business review): the cheque drawn as the paper it is (its date where a cheque
 *  writes it, its amount in its box), then its road: the last day to present it, the day it came back, the bank's
 *  injunction, the three months without a fine, the holder's actions; on top, the one thing that matters today for
 *  whoever holds it or wrote it (the commerce code arts 268, 295, 313, 314, 316, 325, as law 71.24 left them). It waits
 *  for a person's check. The inputs live in the address. */
export default function ChequePage({ slug }: { slug: string }) {
  const { t, i18n } = useBusinessT();
  const money = useMoney();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const today = todayIso();
  const [s, set] = useToolState({ s: 'holder', d: today, w: 'morocco', r: '', m: '20000', n: '1' });
  const side = (s.s === 'drawer' ? 'drawer' : 'holder') as Side;
  const where = (s.w === 'abroad' ? 'abroad' : 'morocco') as Where;
  const amount = Math.max(0, Number(s.m) || 0);
  const nth = (['1', '2', '3'].includes(s.n) ? Number(s.n) : 1) as 1 | 2 | 3;
  const stops = road(s.d, where, s.r || null);
  const at = (k: string) => stops.find((x) => x.key === k)?.date ?? '';
  const free = s.r ? today <= at('free') : false;
  const fine = recoveryFine(amount, nth, free);

  let over: string, value: string, under: string, warn = false;
  if (!s.r) {
    const left = daysUntil(at('present'));
    over = t('cheque.presentOver', { date: dayWords(at('present'), lang) });
    value = left >= 0 ? t('cheque.daysLeft', { count: left }) : t('cheque.presentPast');
    under = side === 'holder' ? (left >= 0 ? t('cheque.holderPresent') : t('cheque.holderLate')) : t('cheque.drawerPresent');
  } else if (side === 'holder') {
    const left = daysUntil(at('drawer'));
    over = t('cheque.drawerOver', { date: dayWords(at('drawer'), lang) });
    value = left >= 0 ? t('cheque.daysLeft', { count: left }) : t('cheque.lapsed');
    under = t('cheque.holderRejected');
    warn = left < 0;
  } else if (free) {
    over = t('cheque.freeOver', { date: dayWords(at('free'), lang) });
    value = t('cheque.daysLeft', { count: daysUntil(at('free')) });
    under = t('cheque.drawerFree');
  } else {
    over = t('cheque.fineOver');
    value = money(fine);
    under = today <= at('recover') ? t('cheque.drawerFine', { date: dayWords(at('recover'), lang) }) : t('cheque.drawerBanned');
    warn = true;
  }

  const title = (k: string) => t(`cheque.stops.${k}.title`);
  const message = [t('cheque.message'), ...stops.map((x) => `${dayWords(x.date, lang)}: ${title(x.key)}`), here()].join('\n');
  const remind = () => calendarFile(stops.filter((x) => x.date >= today && x.key !== 'written')
    .map((x) => ({ date: x.date, title: title(x.key), detail: here() })), 'cheque');

  return (
    <KitPage slug={slug} title={t('cheque.title')} lead={t('cheque.lead')}>
      <AnswerCard over={over} value={value} tone={warn ? 'warn' : 'stamp'} under={<p className="m-0">{under}</p>} />

      <ChequeFace date={s.d} amount={money(amount)} lang={lang} caption={t('cheque.face')} />

      <Sheet>
        <Chips label={t('cheque.side')} value={side} onChange={(v) => set({ s: v })}
               options={(['holder', 'drawer'] as Side[]).map((k) => ({ key: k, label: t(`cheque.sides.${k}`) }))} />
        <DateField label={t('cheque.written')} value={s.d} onChange={(d) => set({ d })} lang={lang} future note={t('cheque.writtenNote')} />
        <Chips label={t('cheque.where')} value={where} onChange={(w) => set({ w })}
               options={(['morocco', 'abroad'] as Where[]).map((k) => ({ key: k, label: t(`cheque.wheres.${k}`, { days: PRESENT[k] }) }))} />
        <Chips label={t('cheque.rejected')} value={s.r ? 'yes' : 'no'} onChange={(v) => set({ r: v === 'yes' ? (s.r || today) : '' })}
               options={[{ key: 'no', label: t('cheque.rejectedNo') }, { key: 'yes', label: t('cheque.rejectedYes') }]} />
        {s.r ? <DateField label={t('cheque.rejectedOn')} value={s.r} onChange={(r) => set({ r })} lang={lang} /> : null}
        <MoneyField label={t('cheque.amount')} value={s.m} onChange={(m) => set({ m })} note={t('cheque.amountNote')} />
        {side === 'drawer' && s.r ? (
          <Chips label={t('cheque.nth')} value={String(nth)} onChange={(n) => set({ n })}
                 options={['1', '2', '3'].map((k) => ({ key: k, label: t(`cheque.nths.${k}`) }))} />
        ) : null}
      </Sheet>

      <section className="rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Road today={today} lang={lang}
              stops={stops.map((x) => ({ key: x.key, date: x.date, title: title(x.key), line: t(`cheque.stops.${x.key}.line`),
                                        warn: x.key === 'free' || x.key === 'drawer', chip: <SourceMark path={x.path} label={articleLabel(x.path)} /> }))} />
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-h3 font-bold">{t('cheque.lawTitle')}</h2>
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
          <li className="text-body">• {t('cheque.law.fine', { fine: money(recoveryFine(amount, nth, false)) })}</li>
          <li className="text-body">• {t('cheque.law.notice')}</li>
          <li className="text-body">• {t('cheque.law.penalty')}</li>
          <li className="text-body">• {t('cheque.law.settle', { amount: money(settleFine(amount)) })}</li>
          <li className="text-body">• {t('cheque.law.family')}</li>
        </ul>
        <SourceFold paths={Object.values(ARTICLES)} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button to={refPath(slug, side === 'holder' ? 'journeys/cheque-bounced' : 'journeys/cheque-written')}>{t('cheque.toJourney')}</Button>
          <Button variant="quiet" to={refPath(slug, 'pages/cheque')}>{t('cheque.toPage')}</Button>
          <Button variant="quiet" onClick={remind}>{t('cheque.remind')}</Button>
          <Button variant="quiet" onClick={() => whatsapp(message)}>{t('cheque.share')}</Button>
        </div>
      </section>
    </KitPage>
  );
}

/** The cheque as the paper it is: the bank's band at its top, the amount in its box, the date where a cheque writes it,
 *  the payee's line, the signature, and the line of numbers along its foot. Paper in both themes; an object, so never
 *  mirrored. */
function ChequeFace({ date, amount, lang, caption }: { date: string; amount: string; lang: string; caption: string }) {
  return (
    <figure className="m-0 flex justify-center" aria-hidden="true">
      <div dir="ltr" className="relative w-full overflow-hidden" style={{ maxWidth: 420, aspectRatio: '175 / 80', borderRadius: 10, background: PAPER, border: `1.5px solid ${EDGE}`, color: INK }}>
        <div className="absolute inset-x-0 top-0" style={{ height: '16%', background: BAND }} />
        <div className="absolute flex items-center justify-center font-bold tabular-nums"
             style={{ right: '5%', top: '22%', width: '36%', height: '18%', border: `1.5px solid ${EDGE}`, borderRadius: 4, background: '#fff', fontSize: 'clamp(0.85rem, 0.7rem + 0.8vw, 1.15rem)' }}>
          {amount}
        </div>
        <div className="absolute flex flex-col" style={{ left: '5%', top: '24%', width: '50%', gap: 7 }}>
          <span style={{ height: 6, width: '90%', borderRadius: 3, background: LINE }} />
          <span style={{ height: 6, width: '70%', borderRadius: 3, background: LINE }} />
        </div>
        <div className="absolute flex flex-col items-end" style={{ right: '5%', top: '48%', gap: 2 }}>
          <span dir={lang === 'fr' ? 'ltr' : 'rtl'} lang={lang} className="text-meta font-semibold" style={{ color: SOFT }}>{caption}</span>
          <span className="font-bold tabular-nums" style={{ fontSize: 'clamp(1rem, 0.85rem + 1vw, 1.35rem)' }}>{date.split('-').reverse().join('/')}</span>
        </div>
        <svg viewBox="0 0 60 20" className="absolute" style={{ left: '8%', bottom: '24%', width: '24%' }}>
          <path d="M2 14c5-12 8 6 13-2s6 5 11 0 5 4 9-1 6 3 10 0" fill="none" stroke={INK} strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <div className="absolute inset-x-0 bottom-0 truncate" style={{ padding: '0 5% 3%', fontFamily: 'ui-monospace, monospace', letterSpacing: '0.18em', fontSize: 'clamp(0.6rem, 0.5rem + 0.6vw, 0.8rem)', color: SOFT }}>
          0000000 000000000000 00
        </div>
      </div>
    </figure>
  );
}
/** The cheque's paper and ink, fixed in both themes (it is an object): a warm paper, the topic's sienna in its band. */
const PAPER = 'linear-gradient(160deg, #FBF6EF 0%, #F6EEE3 60%, #F2E7DA 100%)';
const BAND = 'linear-gradient(90deg, #E9D3BF, #F1E1D2)';
const EDGE = '#D9BFA6';
const LINE = '#E3D2C1';
const INK = '#2A1A10';
const SOFT = '#6F5646';
