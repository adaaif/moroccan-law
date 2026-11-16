import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { buttonClass, type Variant } from '@/shared/components/buttons';
import '@/shared/locales/pages';
import { standing, type AccessBody } from './access';
import { dateOf, useGranted } from './said';

/** Sentences said as an alert, one under the other. */
export function Alerts({ lines }: { lines: string[] }) {
  if (!lines.length) return null;
  return <div role="alert" className="ax-alert">{lines.map((l) => <p key={l}>{l}</p>)}</div>;
}

/** Copies its text and says so for a moment; where the browser refuses, the text stays there to select. */
export function Copy({ text, label, variant = 'quiet' }: { text: string; label?: string; variant?: Variant }) {
  const { t } = useTranslation();
  const [done, setDone] = useState(false);
  const copy = () => {
    void navigator.clipboard?.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 1600); }, () => undefined);
  };
  return (
    <button type="button" onClick={copy} aria-live="polite" className={buttonClass(variant)}>
      {done ? t('pages:data.copied') : label ?? t('pages:data.copy')}
    </button>
  );
}

/** Where an account's request stands, in one sentence, with the way to «وصولي»: sent and waiting, a line asked of it,
 *  declined (and when it may ask again), an access held, an access ended. Nothing for an account that asked nothing. */
export function StandingLine({ body }: { body: AccessBody }) {
  const { t, i18n } = useTranslation();
  const granted = useGranted();
  const lang = i18n.language;
  const r = body.request;
  const a = body.access;
  const s = standing(body);
  let line = '';
  if (s === 'waiting' && r) line = t('pages:access.states.waiting', { date: dateOf(r.created_at, lang), days: body.answer_days });
  else if (s === 'more' && r) line = t('pages:access.states.more');
  else if ((s === 'declined' || s === 'again') && r) {
    line = `${t('pages:access.states.declined', { reason: t(`pages:access.reasons.${r.reason}.d`) })} ${
      s === 'declined' && r.ask_again_on ? t('pages:access.states.againOn', { date: dateOf(r.ask_again_on, lang) }) : t('pages:access.states.againNow')}`;
  } else if (s === 'live' && a) line = t('pages:access.states.live', { granted: granted(a), date: dateOf(a.ends_on, lang) });
  else if (s === 'ended' && a) line = t('pages:access.states.ended', { reason: t(`pages:access.ended.${a.ended_reason || 'expired'}`) });
  if (!line) return null;
  return (
    <p className="ax-standing" data-state={s}>
      <span>{line}</span>
      {s === 'more' && r?.asked ? <q dir="auto">{r.asked}</q> : null}
      <Link to="/data/access">{t('pages:access.states.toAccount')}</Link>
    </p>
  );
}
