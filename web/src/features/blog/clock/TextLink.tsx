import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { ClockPost, ClockText } from '../blog.api';
import { textName } from './names';

/** A text as the post names it: its name (to its own address when the site has cut it, else to its printed page) and the
 *  Bulletin's issue and page as the stamp every source wears on the site, a tap from the printed page. */
export function TextLink({ t: text, post, lang, stamp = true, compact = false }: { t: ClockText; post: ClockPost; lang: string; stamp?: boolean; compact?: boolean }) {
  const { t } = useTranslation('blog');
  const f = post.figures.texts[text.key];
  const name = textName(text, lang);
  const to = f?.path ?? f?.viewer ?? null;
  // A «bis» issue as the Arabic Bulletin prints it: «6720 مكرر».
  const issue = f ? `${f.issue.replace(' bis', lang === 'fr' ? ' bis' : ' مكرر')}${f.edition === 'translation_fr' ? ` ${t('clock.frEdition')}` : ''}` : null;
  if (compact && f) {
    // A narrow column: the name, and the issue and page in the stamp's violet, one tap from the printed page.
    return (
      <span className="ck-ref is-compact">
        {to ? <Link to={to}>{name}</Link> : name}{' '}
        {f.viewer ? <Link to={f.viewer} className="ck-ref-page" title={t('clock.seePage')}>{t('clock.pageShort', { issue, page: f.page })}</Link> : null}
      </span>
    );
  }
  return (
    <span className="ck-ref">
      {to ? <Link to={to}>{name}</Link> : name}
      {stamp && f ? <>{' '}<Stamp issue={issue} page={f.page} to={f.viewer} className="ck-ref-stamp" /></> : null}
    </span>
  );
}
