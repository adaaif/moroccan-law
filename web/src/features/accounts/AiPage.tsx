import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button, Card, Note, Page } from '@/shared/components/ui';
import { usePageTitle } from '@/shared/services/title';
import '@/shared/locales/pages';
import { SITE_NAME } from '@/shared/services/fileName';

const TOOLS = ['search', 'fetch', 'read_articles', 'check_references', 'get_bulletin'] as const;

/** The address an assistant is given: this site's own /mcp. */
function serverUrl(): string {
  return typeof window === 'undefined' ? 'https://3adala.com/mcp' : `${window.location.origin}/mcp`;
}

function Copy({ text }: { text: string }) {
  const { t } = useTranslation();
  const [done, setDone] = useState(false);
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* One line, scrolled inside its box: a command broken at a «--» reads as two. */}
      <code dir="ltr" tabIndex={0} className="block max-w-full select-all overflow-x-auto whitespace-nowrap rounded-control bg-paper px-3 py-2 font-mono text-body">{text}</code>
      <Button onClick={async () => {
        try { await navigator.clipboard.writeText(text); setDone(true); } catch { setDone(false); }
      }}>{done ? t('pages:ai.copied') : t('pages:ai.copy')}</Button>
    </div>
  );
}

/**
 * «/ai» (MC23 of the MCP review, 3 Nov 2026): how to read the site from ChatGPT, Claude or Gemini (4 Nov:
 * Gemini's custom apps are open in the US only for now), with no account since 3 Nov. It names the assistants because the reader connects them; the site's own AI stays
 * «الذكاء الاصطناعي».
 */
export default function AiPage() {
  const { t } = useTranslation();
  usePageTitle([t('pages:ai.title')]);
  const url = serverUrl();
  return (
    <Page width="reading">
      <header className="flex flex-col gap-3">
        <h1 className="m-0 font-law text-h1 font-semibold leading-tight">{t('pages:ai.title')}</h1>
        <p className="m-0 text-lead">{t('pages:ai.lede')}</p>
      </header>

      <Card className="flex flex-col gap-3">
        <h2 className="m-0 text-h3 font-bold">{t('pages:ai.addressTitle')}</h2>
        <p className="m-0 text-body">{t('pages:ai.addressLede')}</p>
        <Copy text={url} />
        <p className="m-0 text-meta text-ink-soft">{t('pages:ai.needs')}</p>
      </Card>

      <Card className="flex flex-col gap-3">
        <h2 className="m-0 text-h3 font-bold">Claude</h2>
        <ol className="m-0 flex flex-col gap-2 ps-5 text-body">
          <li>{t('pages:ai.claude1')}</li>
          <li>{t('pages:ai.claude2')}</li>
          <li>{t('pages:ai.claude3')}</li>
          <li>{t('pages:ai.ask')}</li>
        </ol>
        <p className="m-0 text-meta text-ink-soft">{t('pages:ai.claudeFree')}</p>
      </Card>

      <Card className="flex flex-col gap-3">
        <h2 className="m-0 text-h3 font-bold">ChatGPT</h2>
        <ol className="m-0 flex flex-col gap-2 ps-5 text-body">
          <li>{t('pages:ai.chatgpt1')}</li>
          <li>{t('pages:ai.chatgpt2')}</li>
          <li>{t('pages:ai.ask')}</li>
        </ol>
        <p className="m-0 text-meta text-ink-soft">{t('pages:ai.chatgptPlans')}</p>
      </Card>

      <Card className="flex flex-col gap-3">
        <h2 className="m-0 text-h3 font-bold">Gemini</h2>
        <ol className="m-0 flex flex-col gap-2 ps-5 text-body">
          <li>{t('pages:ai.gemini1')}</li>
          <li>{t('pages:ai.gemini2')}</li>
          <li>{t('pages:ai.ask')}</li>
        </ol>
        <p className="m-0 text-meta text-ink-soft">{t('pages:ai.geminiWhere')}</p>
      </Card>

      <Card className="flex flex-col gap-3">
        <h2 className="m-0 text-h3 font-bold">{t('pages:ai.terminalTitle')}</h2>
        <h3 className="m-0 text-body font-semibold">Claude Code</h3>
        <Copy text={`claude mcp add --transport http ${SITE_NAME} ${url}`} />
        <h3 className="m-0 text-body font-semibold">Gemini CLI</h3>
        <Copy text={`gemini mcp add -s user --transport http ${SITE_NAME} ${url}`} />
      </Card>

      <Card className="flex flex-col gap-3">
        <h2 className="m-0 text-h3 font-bold">{t('pages:ai.toolsTitle')}</h2>
        <ul className="m-0 flex flex-col gap-2 ps-5 text-body">
          {TOOLS.map((tool) => <li key={tool}><code dir="ltr" className="font-mono text-meta">{tool}</code> — {t(`pages:ai.tools.${tool}`)}</li>)}
        </ul>
        <p className="m-0 text-body">{t('pages:ai.never')}</p>
        <p className="m-0 text-meta text-ink-soft">{t('pages:ai.limits')}</p>
      </Card>

      <Note tone="law">
        <p className="m-0 text-body">{t('pages:ai.notAdvice')}</p>
      </Note>

      <Card className="flex flex-col gap-2">
        <h2 className="m-0 text-h3 font-bold">{t('pages:ai.endTitle')}</h2>
        <p className="m-0 text-body">{t('pages:ai.end')}</p>
        <p className="m-0 text-meta text-ink-soft">{t('pages:ai.endAccount')} <Link to="/account/settings#apps" className="underline">{t('pages:ai.endLink')}</Link></p>
        <p className="m-0 text-meta text-ink-soft">{t('pages:ai.privacy')} <Link to="/privacy" className="underline">{t('pages:ai.privacyLink')}</Link></p>
      </Card>
    </Page>
  );
}
