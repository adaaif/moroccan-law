import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Sheet } from '@/shared/components/Sheet';
import '@/shared/locales/pages';
import { fileName } from '@/shared/services/fileName';

type Shape = 'post' | 'story';

/** «صورة للمشاركة» (R14 of the for-everyone review): the server's picture of an article, a told text or an answer, as a
 *  post (4:5) or a story (9:16), to forward through the phone's share sheet or keep. The WhatsApp text stays beside it. */
export default function ShareImage({ path, answer, register, className = '', children }: {
  path?: string;
  answer?: number;
  register?: string;
  className?: string;
  /** Another face for the button (the article's share sheet draws it as a large choice). */
  children?: React.ReactNode;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className={className || 'inline-flex min-h-11 items-center gap-1.5 text-meta font-medium text-stamp hover:text-stamp-deep'}>
        {children ?? <><PictureIcon />{t('pages:share.picture')}</>}
      </button>
      {open ? <Picture path={path} answer={answer} register={register} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function Picture({ path, answer, register, onClose }: { path?: string; answer?: number; register?: string; onClose: () => void }) {
  const { t } = useTranslation();
  const [shape, setShape] = useState<Shape>('post');
  const [failed, setFailed] = useState(false);
  const query = new URLSearchParams({ shape, ...(answer ? { answer: String(answer) } : { path: path ?? '' }), ...(register ? { register } : {}) });
  const src = `/api/explain/card/?${query}`;
  const name = fileName(`${(path ?? `answer-${answer}`).replace(/[^\w-]+/g, '-').replace(/^-|-$/g, '')}-${shape}.png`);
  const share = async () => {
    try {
      const blob = await (await fetch(src)).blob();
      const file = new File([blob], name, { type: 'image/png' });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], text: `${window.location.origin}${answer ? '' : path ?? ''}` });
        return;
      }
    } catch (err) {
      if ((err as DOMException).name === 'AbortError') return;
    }
    setFailed(true);
  };
  return (
    <Sheet centered label={t('pages:share.picture')} onClose={onClose}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="m-0 text-lead font-bold">{t('pages:share.picture')}</h2>
          <div role="group" aria-label={t('pages:share.shape')} className="inline-flex rounded-full bg-paper p-0.5 text-meta">
            {(['post', 'story'] as Shape[]).map((s) => (
              <button key={s} type="button" aria-pressed={s === shape} onClick={() => setShape(s)}
                      className={`rounded-full px-3.5 py-1.5 ${s === shape ? 'bg-sheet font-semibold text-ink shadow-sm' : 'text-ink-soft'}`}>
                {t(`pages:share.${s}`)}
              </button>
            ))}
          </div>
        </div>
        <img src={src} alt={t('pages:share.alt')} width={1080} height={shape === 'post' ? 1350 : 1920}
             className={`mx-auto h-auto rounded-control ring-1 ring-rule ${shape === 'post' ? 'w-full max-w-[340px]' : 'w-[62%] max-w-[260px]'}`} />
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void share()}
                  className="inline-flex h-11 flex-1 items-center justify-center rounded-control bg-stamp px-5 font-semibold text-on-stamp hover:bg-stamp-deep">
            {t('pages:share.send')}
          </button>
          <a href={src} download={name} className="inline-flex h-11 flex-1 items-center justify-center rounded-control px-5 font-medium no-underline ring-1 ring-rule">
            {t('pages:share.keep')}
          </a>
        </div>
        {failed ? <p className="m-0 text-meta text-ink-soft">{t('pages:share.noShare')}</p> : null}
        <p className="m-0 text-meta text-ink-soft">{t('pages:share.note')}</p>
      </div>
    </Sheet>
  );
}

const PictureIcon = () => (
  <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="4" y="3" width="16" height="18" rx="2.5" /><path d="M8 8h8M8 12h8M8 16h5" />
  </svg>
);
