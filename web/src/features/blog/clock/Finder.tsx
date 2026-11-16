import { useId, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { todayIso } from '@/shared/services/today';
import type { ClockPost } from '../blog.api';
import { Face } from './Face';
import { day, weekdayDay } from './names';
import { at, type Clock } from './time';
import { TextLink } from './TextLink';

/**
 * «شحال كانت الساعة نهار…؟»: any day, and what the law said it was in Morocco when Greenwich said noon. The face turns to
 * the answer (motion that answers the reader); the sentence names the stretch the day sits in and the text that began it.
 */
export function Finder({ c, post, lang }: { c: Clock; post: ClockPost; lang: string }) {
  const { t } = useTranslation('blog');
  const today = todayIso();
  const [picked, setPicked] = useState('1985-01-01');
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  const m = useMemo(() => at(c, `${picked}T12:00`), [c, picked]);
  const texts = useMemo(() => Object.fromEntries(post.texts.map((x) => [x.key, x])), [post]);
  const valid = /^\d{4}-\d\d-\d\d$/.test(picked) && picked >= '1900-01-01';
  const ahead = m.state === 'ahead' || m.state === 'unknown';
  const chips: [string, string][] = [
    ['1985-01-01', t('clock.finder.chip', { day: day('1985-01-01', lang) })],
    ['1943-08-15', t('clock.finder.chip', { day: day('1943-08-15', lang) })],
    ['2020-05-01', t('clock.finder.chip', { day: day('2020-05-01', lang) })],
    [today, t('clock.finder.today')],
  ];
  const since = m.since ? texts[m.since.text] : null;
  const stretch = m.state === 'none' ? null : t(m.until ? 'clock.finder.from_to' : 'clock.finder.from', {
    from: day(m.since?.at ?? post.legal_from, lang), to: m.until ? day(m.until.at, lang) : '',
  });
  return (
    <div className="ck-finder">
      <div className="ck-finder-ask">
        <label htmlFor={id} className="ck-finder-label">{t('clock.finder.label')}</label>
        <input ref={input} id={id} type="date" className="ck-date" dir="ltr" min="1900-01-01" max="2099-12-31" value={picked}
               onChange={(e) => e.target.value && setPicked(e.target.value)} />
        <div className="ck-chips" role="group" aria-label={t('clock.finder.chips')}>
          <button type="button" className="ck-chip" onClick={() => { input.current?.focus(); input.current?.showPicker?.(); }}>{t('clock.finder.birth')}</button>
          {chips.map(([d, label]) => (
            <button key={d} type="button" className="ck-chip" aria-pressed={picked === d} onClick={() => setPicked(d)}>{label}</button>
          ))}
        </div>
      </div>
      {valid ? (
        <div className="ck-finder-answer" aria-live="polite">
          <div className="ck-finder-face">
            <Face size={132} at={{ hour: ahead ? 30 : 0, minute: 0 }} gold={ahead ? [0, 30] : null} secondHand={false}
                  className={`is-smooth${m.state === 'unknown' ? ' is-unsure' : ''}`}
                  label={t(`clock.finder.face_${m.state === 'none' ? 'none' : ahead ? 'ahead' : 'gmt'}`)} />
            <p className="ck-finder-time" dir="ltr">{m.state === 'none' ? '—' : ahead ? '13:00' : '12:00'}</p>
          </div>
          <div className="ck-finder-words">
            <p className="ck-finder-day">{weekdayDay(picked, lang)}</p>
            <p className="ck-finder-state">{t(`clock.finder.${m.state}`)}</p>
            {m.state !== 'none' ? <p className="ck-finder-noon">{t(ahead ? 'clock.finder.noon_ahead' : 'clock.finder.noon_gmt')}</p> : null}
            {stretch ? (
              <p className="ck-finder-since">
                {stretch}{' '}
                {since ? <TextLink t={since} post={post} lang={lang} /> : <TextLink t={texts.d1913} post={post} lang={lang} />}
              </p>
            ) : null}
            {picked < '1956-03-02' && m.state !== 'none' ? <p className="ck-finder-zone">{t('clock.finder.zone')}</p> : null}
            {picked > today && !m.until ? <p className="ck-finder-zone">{t('clock.finder.later', { on: day(post.counted_on, lang) })}</p> : null}
          </div>
        </div>
      ) : <p className="ck-finder-answer" aria-live="polite">{t('clock.finder.invalid')}</p>}
    </div>
  );
}
