import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useCanTalk } from '@/features/accounts/registration';

/** The footer in three groups (P18 of the polish review): the law, the discussion, and the site; then the disclaimer. On a
 *  phone it was nine links in one run, wrapping into four lines. */
export default function Footer() {
  const { t } = useTranslation();
  // The conversation by its name while a phone's bar does not hold it (C2 of the readers review).
  const talk: [string, string][] = useCanTalk() ? [['/talk', t('nav.talk')]] : [];
  const groups: [string, [string, string][]][] = [
    [t('footer.law'), [['/topics', t('nav.topics')], ['/library', t('nav.library')], ['/bo', t('issues.title')],
                       ['/words', t('nav.words')], ['/budget', t('nav.budget')]]],
    [t('footer.talk'), [...talk, ['/questions', t('nav.questions')], ['/rules', t('nav.rules')], ['/privacy', t('nav.privacy')]]],
    [t('footer.site'), [['/blog', t('nav.blog')], ['/about', t('nav.about')], ['/corrections', t('nav.corrections')],
                        ['/open-source', t('nav.contribute')], ['/data', t('data.title')], ['/check', t('nav.check')]]],
  ];
  return (
    // The bottom bar covers the last 56 px of a phone's page: the footer leaves room for it.
    <footer className="mt-auto border-t border-rule bg-sheet pb-16 lg:pb-0" data-noprint>
      <div className="mx-auto flex max-w-6xl flex-col gap-5 px-4 py-6 sm:px-6 sm:py-8">
        {/* The wordmark's bolder cut, home's way (9 Nov 2026). */}
        <Link to="/" aria-label="قانون المغرب" className="self-start text-stamp">
          <span className="wordmark wordmark-bold block h-14" aria-hidden="true" />
        </Link>
        <div className="grid grid-cols-3 gap-x-4 gap-y-6 sm:gap-x-6">
          {groups.map(([title, links]) => (
            <nav key={title} aria-label={title} className="flex flex-col">
              <p className="m-0 mb-1 text-meta font-semibold text-ink-soft">{title}</p>
              {links.map(([to, label]) => (
                <Link key={to} to={to} className="inline-flex min-h-11 items-center self-start py-1 text-meta leading-snug text-ink no-underline hover:text-stamp sm:text-body">{label}</Link>
              ))}
            </nav>
          ))}
        </div>
        <p className="m-0 max-w-[70ch] text-meta text-ink-soft">{t('corpus.disclaimer')}</p>
        {/* What the AI did and what no specialist has reviewed, said once under every page and in full on «عن «قانون»»
            (an editorial call of 15 Nov 2026): the pages themselves no longer say it. */}
        <p className="m-0 max-w-[70ch] text-meta text-ink-soft">
          {t('footer.ai')} <Link to="/about#ab-who" className="py-2.5 font-medium">{t('footer.who')}</Link>
        </p>
      </div>
    </footer>
  );
}
