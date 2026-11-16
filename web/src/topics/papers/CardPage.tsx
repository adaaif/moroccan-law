import { Button } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { calendarFile, whatsapp, here } from '../kit/share';
import { AnswerCard, Chips, SourceFold, SourceMark } from '../kit/tool/parts';
import { dayWords, daysUntil } from '../kit/tool/days';
import { useToolState } from '../kit/tool/state';
import { addDays } from './rules/dates';
import { ARTICLES, EVENTS, FINES, card, ifIssuedToday, type Event } from './rules/card';
import { CardFace, DateField, Toggles } from './parts';
import { articleLabel, useMoney, usePapersT } from './strings';

/** «البطاقة ديالي» (the papers review): a birth date, and the date the card prints as its end if the reader has one,
 *  and what changed since → the card drawn with that date, the days left or the renewal due, why, what to bring, what it
 *  costs, and what a delay may cost (law 04.20 arts 2, 13, 15; decree 2.20.521 arts 1, 3, 5; tax code art. 252). It
 *  waits for a person's check. The inputs live in the address. */
export default function CardPage({ slug }: { slug: string }) {
  const { t, i18n } = usePapersT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const money = useMoney();
  const today = todayIso();
  const [s, set] = useToolState({ b: '', h: 'yes', e: '', ev: '' });
  const events = s.ev.split(',').filter((x): x is Event => (EVENTS as readonly string[]).includes(x));
  const birth = s.b;
  const has = s.h === 'yes';
  // Nothing is said until the reader gave what it rests on: a birth date, and the card's end if they have one.
  const state = birth && (!has || s.e) ? card(birth, today, has ? s.e : null, events) : null;
  const left = state?.state === 'valid' ? daysUntil(state.last) : null;

  const value = !state ? t(birth ? 'card.startEnd' : 'card.start')
    : state.state === 'valid' ? t('card.left', { count: left! })
    : state.state === 'renew' ? t('card.renewNow')
    : state.state === 'none-due' ? t('card.dueNow')
    : t('card.dueOn', { date: dayWords(state.duty, lang) });
  const over = !state ? t('card.startOver') : state.state === 'valid' ? t('card.validOver', { date: dayWords(state.last, lang) })
    : state.state === 'renew' ? t('card.renewOver') : t('card.noneOver');
  const faceLabel = has && s.e ? dayWords(s.e, lang) : birth ? dayWords(ifIssuedToday(birth, today), lang) : '—';
  const message = [t('card.message'), over, value, here()].join('\n');
  const remind = () => state?.state === 'valid' && calendarFile([{ date: addDays(state.last, -60), title: t('card.remindTitle'), detail: here() }], 'card');

  return (
    <KitPage slug={slug} title={t('card.title')} lead={t('card.lead')}>
      <AnswerCard over={over} value={value} tone={state && state.state !== 'valid' && state.state !== 'none-young' ? 'warn' : 'stamp'}
                  under={state ? <p className="m-0">{t(`card.under.${state.state}`, { min: money(FINES.never[0]), max: money(FINES.never[1]) })}</p> : null} />

      <section className="rounded-card bg-sheet px-5 py-5 sm:px-7">
        <div>
          <CardFace birth={birth} last={has && s.e ? s.e : birth ? ifIssuedToday(birth, today) : null} lang={lang}
                    caption={has && s.e ? t('card.faceEnd') : t('card.faceIfToday')} label={faceLabel}
                    warn={state?.state === 'renew'} />
        </div>
      </section>

      <section className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <DateField label={t('card.birth')} value={s.b} onChange={(b) => set({ b })} lang={lang} note={t('card.birthNote')} />
        <Chips label={t('card.has')} value={s.h} onChange={(h) => set({ h })}
               options={[{ key: 'yes', label: t('card.hasYes') }, { key: 'no', label: t('card.hasNo') }]} />
        {has ? <DateField label={t('card.end')} value={s.e} onChange={(e) => set({ e })} lang={lang} future note={t('card.endNote')} /> : null}
        {has ? (
          <Toggles label={t('card.changed')} value={events} onChange={(v) => set({ ev: v.join(',') })}
                   options={(['moved', 'name', 'birthday', 'marital', 'lost'] as Event[]).map((k) => ({ key: k, label: t(`card.events.${k}`) }))} />
        ) : null}
      </section>

      {state ? (
        <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
          {state.state === 'renew' ? (
            <>
              <h2 className="m-0 text-h3 font-bold">{t('card.why')}</h2>
              <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
                {state.why.map((w) => <li key={w} className="text-body">• {t(`card.reasons.${w}`)}</li>)}
              </ul>
              <p className="m-0 text-body">{t('card.fineRenew', { min: money(FINES.renew[0]), max: money(FINES.renew[1]) })} <SourceMark path={ARTICLES.fines} label={articleLabel(ARTICLES.fines)} /></p>
            </>
          ) : null}
          {state.state === 'valid' && state.twelve ? <p className="m-0 text-body">{t('card.twelve', { date: dayWords(state.twelve, lang) })} <SourceMark path={ARTICLES.prints} label={articleLabel(ARTICLES.prints)} /></p> : null}
          <p className="m-0 text-body">{t('card.fee', { fee: money(state.fee) })} <SourceMark path={ARTICLES.stamp} label={articleLabel(ARTICLES.stamp)} /></p>
          <p className="m-0 text-body">{t('card.ifToday', { date: dayWords(ifIssuedToday(birth, today), lang) })} <SourceMark path={ARTICLES.validity} label={articleLabel(ARTICLES.validity)} /></p>
          <p className="m-0 text-body">{t('card.spares')} <SourceMark path={ARTICLES.spares} label={articleLabel(ARTICLES.spares)} /></p>
          <SourceFold paths={[ARTICLES.duty, ARTICLES.validity, ARTICLES.renew, ARTICLES.fines, ARTICLES.stamp]} label={articleLabel} />
          <div className="flex flex-wrap gap-2">
            <Button to={refPath(slug, state.state === 'renew' || state.state === 'valid' ? 'checklists/card-renew' : 'checklists/card-first')}>{t('card.toList')}</Button>
            <Button variant="quiet" to={refPath(slug, state.state === 'renew' && events.includes('lost') ? 'journeys/card-lost' : state.state === 'renew' || state.state === 'valid' ? 'journeys/card-renew' : 'journeys/card-first')}>{t('card.toJourney')}</Button>
            {state.state === 'valid' ? <Button variant="quiet" onClick={remind}>{t('card.remind')}</Button> : null}
            <Button variant="quiet" onClick={() => whatsapp(message)}>{t('card.share')}</Button>
          </div>
        </section>
      ) : null}
    </KitPage>
  );
}
