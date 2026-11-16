import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { Chips, DayChips } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { useProfile } from '../kit/profile';
import { forgetPurchase, keepPurchase, readPurchases, type Kept } from './purchases';
import { nextLast, receipt, type Line, type Purchase } from './rules/receipt';
import type { Channel } from './rules/withdrawal';
import { articleLabel, useConsumerT } from './strings';
import { todayIso } from '@/shared/services/today';

/** A day as the receipt prints it: its year only when it is not this year's (a guarantee runs into the next). */
const printed = (day: string, lang: string) => dayWords(day, lang, day.slice(0, 4) !== todayIso().slice(0, 4));

const CHANNELS: Channel[] = ['shop', 'online', 'door', 'credit'];
/** The paper of a till receipt, white by night as by day, its ink near black: the drawing is of a thing. */
const PAPER = '#ffffff';
const INK = '#1e1b2c';

/** «فاتورة حقوقي» (the consumer-receipt review, 26 Oct 2026): where the reader bought, what, its price and its day,
 *  and out comes the receipt of the rights that purchase gives — each line a right, the day it runs to, its articles,
 *  «لا ترد ولا تستبدل» stamped and struck through at its foot. A purchase can be kept on the phone («مشترياتي»): the
 *  topic's page then shows its soonest day. Computed on the phone from the other tools' rules; nothing is sent. The
 *  inputs live in the address. */
export default function ReceiptPage({ slug }: { slug: string }) {
  const { t, i18n } = useConsumerT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [mine] = useProfile(slug);
  const fromProfile = (CHANNELS as string[]).includes(mine ?? '') ? (mine as Channel) : 'online';
  const [s, set] = useToolState({ c: fromProfile as string, d: todayIso(), p: '1200', svc: '', conf: 'yes', ex: '', g: '0', i: '' }, ['c']);
  const [kept, setKept] = useState<Kept[]>(() => readPurchases());
  const [saved, setSaved] = useState(false);
  const channel = (CHANNELS.includes(s.c as Channel) ? s.c : 'online') as Channel;
  const purchase: Purchase = {
    channel, service: channel === 'online' && s.svc === '1', day: s.d, price: Number(s.p) || 0,
    confirmed: s.conf !== 'no', excluded: s.ex === '1', shopMonths: Number(s.g) || 0,
  };
  const lines = receipt(purchase);
  const today = todayIso();
  const next = nextLast(lines, today);
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const dayLabel = channel === 'online' && s.svc === '1' ? 'service' : channel;
  const text = (l: Line) => `${t(`receipt.lines.${l.key}.title`)}: ${t(`receipt.lines.${l.key}.detail`, { days: l.days, months: l.months })}${l.last ? ` (${printed(l.last, lang)})` : ''}`;
  const message = [t('receipt.message'), s.i || t(`return.channels.${channel}`), ...lines.filter((l) => l.key !== 'noReturnStamp').map(text), here()].join('\n');
  const keep = () => { setKept(keepPurchase(s.i.trim(), purchase, today)); setSaved(true); };
  const remind = () => next?.last && calendarFile([{ date: next.last, title: t(`receipt.lines.${next.key}.title`), detail: `${s.i || t(`return.channels.${channel}`)}. ${here()}` }], 'receipt');
  return (
    <KitPage slug={slug} title={t('receipt.title')} lead={t('receipt.lead')}>
      <section data-answer aria-live="polite" aria-labelledby="ticket" className="flex flex-col gap-3 lg:sticky lg:top-6">
        <Ticket lines={lines} purchase={purchase} item={s.i} today={today} />
        <div className="flex flex-wrap justify-center gap-2">
          <Button onClick={keep} disabled={saved}>{saved ? t('receipt.kept') : t('receipt.keep')}</Button>
          <Button variant="quiet" onClick={() => whatsapp(message)}>{t('share')}</Button>
          {next?.last ? <Button variant="quiet" onClick={remind}>{t('remind')}</Button> : null}
        </div>
      </section>

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Chips label={t('return.where')} value={channel} onChange={(c) => { set({ c }); setSaved(false); }}
               options={CHANNELS.map((c) => ({ key: c, label: t(`return.channels.${c}`) }))} />
        {channel === 'online' ? (
          <Chips label={t('return.what')} value={s.svc === '1' ? 'service' : 'goods'} onChange={(v) => { set({ svc: v === 'service' ? '1' : '' }); setSaved(false); }}
                 options={[{ key: 'goods', label: t('return.goods') }, { key: 'service', label: t('return.service') }]} />
        ) : null}
        <DayChips label={t(`return.day.${dayLabel}`)} value={s.d} onChange={(d) => { set({ d }); setSaved(false); }} ago={[0, 1, 2, 7]} />
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('receipt.price')}</span>
          <input type="number" inputMode="decimal" min={0} value={s.p === '0' ? '' : s.p} onChange={(e) => { set({ p: e.target.value || '0' }); setSaved(false); }}
                 className="h-12 w-40 max-w-full rounded-control border border-field bg-sheet px-3 text-body tabular-nums" dir="ltr" />
        </label>
        {channel === 'online' ? (
          <>
            <Chips label={t('return.confirmed')} value={s.conf === 'no' ? 'no' : 'yes'} onChange={(v) => { set({ conf: v }); setSaved(false); }}
                   options={[{ key: 'yes', label: t('yes') }, { key: 'no', label: t('no') }]} />
            <label className="flex min-h-11 items-start gap-3 text-body">
              <input type="checkbox" checked={s.ex === '1'} onChange={(e) => { set({ ex: e.target.checked ? '1' : '' }); setSaved(false); }} className="mt-1 size-5" style={{ accentColor: 'var(--t)' }} />
              <span>{t('return.exclusions')}</span>
            </label>
          </>
        ) : null}
        {!purchase.service ? (
          <Chips label={t('receipt.shopMonths')} value={s.g} onChange={(g) => { set({ g }); setSaved(false); }}
                 options={['0', '6', '12', '24'].map((m) => ({ key: m, label: m === '0' ? t('receipt.noShopGuarantee') : t('receipt.monthsN', { count: Number(m) }) }))} />
        ) : null}
        <label className="flex flex-col gap-1.5">
          <span className="text-body font-semibold">{t('receipt.item')}</span>
          <input value={s.i} onChange={(e) => { set({ i: e.target.value }); setSaved(false); }} dir="auto" maxLength={60} placeholder={t('receipt.itemHint')}
                 className="h-12 w-full max-w-sm rounded-control border border-field bg-sheet px-3 text-body" />
        </label>
      </section>

      {kept.length ? (
        <section aria-labelledby="kept" className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-5 sm:px-7">
          <h2 id="kept" className="m-0 text-lead font-semibold">{t('receipt.mine')}</h2>
          <ul className="m-0 flex list-none flex-col p-0">
            {kept.map((k) => {
              const n = nextLast(receipt(k.purchase), today);
              const left = n?.last ? daysUntil(n.last) : -1;
              return (
                <li key={k.id} className="flex items-center gap-3 border-t border-rule py-3 first:border-t-0">
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span dir="auto" className="truncate text-body font-semibold">{k.item || t(`return.channels.${k.purchase.channel}`)}</span>
                    <span className="text-meta text-ink-soft">
                      {n ? `${t(`receipt.lines.${n.key}.title`)}: ${left === 0 ? t('return.today') : t('return.left', { count: left })}` : t('receipt.nothingRuns')}
                    </span>
                  </span>
                  <Button variant="quiet" onClick={() => setKept(forgetPurchase(k.id))}>{t('receipt.forget')}</Button>
                </li>
              );
            })}
          </ul>
          <p className="m-0 text-meta text-ink-soft">{t('receipt.onPhone')}</p>
        </section>
      ) : null}

      <Note tone="warn" quiet><p className="m-0 text-meta">{t('receipt.note', { price: nf.format(3000) })}</p></Note>
    </KitPage>
  );
}

/** The receipt itself: torn at both ends, the purchase at its head, a right a line with its day and articles, the
 *  stamp at its foot. */
function Ticket({ lines, purchase, item, today }: { lines: Line[]; purchase: Purchase; item: string; today: string }) {
  const { t, i18n } = useConsumerT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const stamp = lines.find((l) => l.key === 'noReturnStamp');
  return (
    <div className="mx-auto w-full max-w-[22rem]" style={{ color: INK, filter: 'drop-shadow(0 10px 18px rgba(20,16,40,.16))' }}>
      <Torn />
      <div className="flex flex-col gap-3 px-5 pb-4 pt-3" style={{ background: PAPER }}>
        <div className="flex flex-col items-center gap-0.5 text-center">
          {/* The receipt's shop name: the site's, in the page's language (PX29 of the where-it-trips review). */}
          <span className="text-lead font-bold">{i18n.language === 'fr' ? i18n.t('app.name') : `«${i18n.t('app.name')}»`}</span>
          <h2 id="ticket" className="m-0 text-body font-semibold">{t('receipt.heading')}</h2>
          {item ? <span dir="auto" className="text-body">{item}</span> : null}
          <span className="text-meta" style={{ opacity: 0.7 }}>{t(`return.channels.${purchase.channel}`)}{purchase.service ? `${lang === 'fr' ? ', ' : '، '}${t('return.service')}` : ''}</span>
        </div>
        <div className="flex justify-between gap-3 border-y border-dashed py-2 text-meta tabular-nums" style={{ borderColor: INK }}>
          <span>{printed(purchase.day, lang)}</span>
          <span dir="ltr">{t('dh', { amount: nf.format(purchase.price) })}</span>
        </div>
        <ul className="m-0 flex list-none flex-col p-0">
          {lines.filter((l) => l.key !== 'noReturnStamp').map((l) => {
            const left = l.last ? daysUntil(l.last) : null;
            return (
              <li key={l.key} className="flex flex-col gap-0.5 border-b border-dotted py-2 last:border-b-0" style={{ borderColor: 'rgba(30,27,44,.35)' }}>
                <span className="flex items-baseline justify-between gap-3">
                  <span className="text-body font-semibold">{t(`receipt.lines.${l.key}.title`)}</span>
                  {l.last ? <span className="shrink-0 text-meta font-semibold tabular-nums">{printed(l.last, lang)}</span> : null}
                </span>
                <span className="text-meta leading-snug" style={{ opacity: 0.8 }}>{t(`receipt.lines.${l.key}.detail`, { days: l.days, months: l.months })}</span>
                {left !== null && left >= 0 && l.key === 'withdraw' ? (
                  <span className="self-start rounded-[4px] px-1.5 text-meta font-semibold" style={{ background: INK, color: PAPER }}>
                    {left === 0 ? t('return.today') : t('return.left', { count: left })}
                  </span>
                ) : null}
                <span className="flex flex-wrap gap-x-2">
                  {l.cites.map((c) => <Link key={c} to={c} lang="ar" dir="rtl" className="text-meta no-underline hover:underline" style={{ color: '#5b3a9e' }}>{articleLabel(c)}</Link>)}
                </span>
              </li>
            );
          })}
        </ul>
        {stamp ? (
          // «لا ترد ولا تستبدل», as shops stamp it, struck through: the guarantee stands (art. 65, DOC art. 571).
          <div className="flex flex-col items-center gap-1 pt-1 text-center">
            <span lang="ar" className="-rotate-3 rounded-[4px] border-2 px-3 py-0.5 text-lead font-bold line-through decoration-2"
                  style={{ borderColor: '#b42318', color: '#b42318' }}>
              لا ترد ولا تستبدل
            </span>
            <span className="text-meta">{t('receipt.stampNote')}</span>
            <span className="flex flex-wrap justify-center gap-x-2">
              {stamp.cites.map((c) => <Link key={c} to={c} lang="ar" dir="rtl" className="text-meta no-underline hover:underline" style={{ color: '#5b3a9e' }}>{articleLabel(c)}</Link>)}
            </span>
          </div>
        ) : null}
        <p className="m-0 border-t border-dashed pt-2 text-center text-meta" style={{ borderColor: INK, opacity: 0.7 }}>
          {t('receipt.printed', { date: printed(today, lang) })}
        </p>
      </div>
      <Torn bottom />
    </div>
  );
}

/** A receipt's torn edge: the paper's teeth, top or bottom. */
function Torn({ bottom = false }: { bottom?: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 352 10" preserveAspectRatio="none" className={`block h-2.5 w-full ${bottom ? 'rotate-180' : ''}`}>
      <path d={`M0 10 ${Array.from({ length: 22 }, (_, i) => `L${i * 16 + 8} 0 L${(i + 1) * 16} 10`).join(' ')} Z`} fill={PAPER} />
    </svg>
  );
}
