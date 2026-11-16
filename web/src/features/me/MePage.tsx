import { useTranslation } from 'react-i18next';
import { useMe } from '@/features/accounts/accounts.service';
import { useRegistrationOpen } from '@/features/accounts/registration';
import { ReadingSettings } from '@/features/corpus/reading/ReadingSettings';
import { applyLanguage } from '@/shared/locales/i18n';
import { useSession } from '@/shared/stores/session';
import { useSaved } from '@/shared/services/saved';
import { useFollows } from '@/features/follows/store';
import '@/shared/locales/pages';
import { usePageTitle } from '@/shared/services/title';
import { Button, Card, ListRow, Page, SectionHeader } from '@/shared/components/ui';

/** «أنا» (R1 of the for-everyone review): what is the reader's — the articles kept on this device, what they follow, their
 *  account and their questions — then «القراءة» (size, night, language: P18 of the polish review, found before only
 *  inside a text) and the pages about the site. No account is needed for anything but writing. */
export default function MePage() {
  const { t, i18n } = useTranslation();
  usePageTitle([t('pages:me.title')]);
  const signedIn = useSession((s) => s.tokens !== null);
  const me = useMe();
  const registrationOpen = useRegistrationOpen();
  const saved = useSaved();
  const follows = useFollows();
  const other = i18n.language === 'fr' ? 'ar' : 'fr';
  const rows = 'm-0 flex list-none flex-col divide-y divide-rule p-0';
  return (
    <Page width="reading">
      <h1 className="m-0 text-h1 font-bold">{t('pages:me.title')}</h1>
      {signedIn ? (
        <Card className="py-1 sm:py-1">
          <ListRow to="/account" title={<span dir="auto" className="font-semibold">{me.data?.display_name || me.data?.username || t('nav.account')}</span>}
                   lead={t('pages:me.accountLead')} />
        </Card>
      ) : registrationOpen ? (
        <Card className="flex flex-col gap-3">
          <p className="m-0 text-lead">{t('pages:me.signInLead')}</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" to="/login">{t('nav.signIn')}</Button>
            <Button variant="quiet" to="/register">{t('pages:auth.createAccount')}</Button>
          </div>
        </Card>
      ) : null}
      <Card className="py-1 sm:py-1">
        <ul className={rows}>
          <li><ListRow to="/saved" title={t('nav.saved')} lead={saved.length ? t('pages:me.savedCount', { count: saved.length }) : t('pages:me.savedNone')} /></li>
          <li><ListRow to="/me/following" title={t('pages:me.following')} lead={follows.length ? t('pages:me.followingCount', { count: follows.length }) : t('pages:me.followingNone')} /></li>
          {signedIn ? <li><ListRow to="/account#mine" title={t('pages:me.mine')} lead={t('pages:me.mineLead')} /></li> : null}
        </ul>
      </Card>
      <Card className="flex flex-col gap-4" aria-labelledby="me-reading">
        <SectionHeader id="me-reading" title={t('pages:me.reading')} lead={t('pages:me.readingLead')} />
        <ReadingSettings />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-rule pt-4">
          <span className="text-meta text-ink-soft">{t('nav.switchLanguageLabel')}</span>
          <Button lang={other} onClick={() => void applyLanguage(other)}>{t('nav.switchLanguage')}</Button>
        </div>
      </Card>
      <Card className="py-1 sm:py-1">
        <ul className={rows}>
          <li><ListRow to="/about" title={t('pages:me.about')} lead={t('pages:me.aboutLead')} /></li>
          <li><ListRow to="/library" title={t('nav.library')} lead={t('home.libraryLead')} /></li>
          <li><ListRow to="/corrections" title={t('pages:me.corrections')} lead={t('pages:me.correctionsLead')} /></li>
          <li><ListRow to="/rules" title={t('nav.rules')} /></li>
          <li><ListRow to="/privacy" title={t('nav.privacy')} /></li>
        </ul>
      </Card>
    </Page>
  );
}
