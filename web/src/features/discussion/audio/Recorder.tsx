import { useEffect, useState } from 'react';
import { upload, type Voice } from '../discussion.api';
import { errorText, clock, useT } from '../strings';
import { MAX_TAKE_MS, canRecord, useRecorder } from './recorder';
import { VoicePlayer } from './VoicePlayer';

/** Recording a voice for a contribution: record (two minutes at most), listen, then add it or start again. Laid out
 *  left to right like the player; the sentences around it follow the page. */
export function Recorder({ owner: form, onAttach, onClose }: {
  owner: string;
  onAttach: (voice: Voice) => void;
  onClose: () => void;
}) {
  const { t } = useT();
  const r = useRecorder();
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    r.claim(form);
    return () => useRecorder.getState().release(form);
    // The seat is claimed once per form.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form]);

  if (!canRecord()) {
    return <p className="m-0 rounded-control bg-paper px-4 py-3 text-body text-ink-soft">{t('recorder.unsupported')}</p>;
  }

  const send = async () => {
    if (!r.take) return;
    setSending(true);
    setError(null);
    const form = new FormData();
    form.append('voice', r.take.blob, r.take.blob.type.includes('mp4') ? 'take.m4a' : 'take.webm');
    form.append('peaks', JSON.stringify(r.take.peaks));
    try {
      const voice = await upload<Voice>('/discussion/voices/', form);
      useRecorder.getState().discard();
      onAttach(voice);
    } catch (e) {
      setError(e);
    } finally {
      setSending(false);
    }
  };

  const live = r.phase === 'recording' || r.phase === 'paused';
  return (
    <div className="flex flex-col gap-3 rounded-control border border-rule bg-paper p-4">
      {r.phase === 'reviewing' && r.take ? (
        <>
          <p className="m-0 text-body font-semibold">{t('recorder.listen')}</p>
          <VoicePlayer id="take" src={r.take.url} durationMs={r.take.durationMs} peaks={r.take.peaks} />
          <div dir="ltr" className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => { r.discard(); onClose(); }} disabled={sending}
                    className="h-10 rounded-full border border-rule bg-sheet px-4 text-meta text-repealed hover:bg-paper">{t('recorder.drop')}</button>
            <button type="button" onClick={() => { r.discard(); void useRecorder.getState().begin(); }} disabled={sending}
                    className="h-10 rounded-full border border-rule bg-sheet px-4 text-meta hover:bg-paper">{t('recorder.redo')}</button>
            <button type="button" onClick={() => void send()} disabled={sending}
                    className="h-10 rounded-full bg-stamp px-5 text-meta font-semibold text-on-stamp hover:bg-stamp-deep disabled:opacity-70">
              {sending ? t('recorder.uploading') : t('recorder.use')}
            </button>
          </div>
          <p className="m-0 text-meta text-ink-soft">{t('recorder.noEdit')}</p>
        </>
      ) : live || r.phase === 'arming' ? (
        <>
          <div dir="ltr" className="flex items-center gap-3">
            <span aria-hidden="true" className={`size-3 shrink-0 rounded-full bg-repealed ${r.phase === 'recording' ? 'motion-safe:animate-pulse' : 'opacity-40'}`} />
            <span className="text-meta font-semibold">{r.phase === 'paused' ? t('recorder.paused') : t('recorder.recording')}</span>
            <span className="ms-auto text-meta text-ink-soft">{t('recorder.limit')}</span>
          </div>
          <div dir="ltr" className="flex items-center gap-4">
            <span className="w-16 shrink-0 text-h2 font-semibold tabular-nums" aria-live="off">{clock(r.elapsedMs)}</span>
            <div aria-hidden="true" className="flex h-12 min-w-0 flex-1 items-center justify-end gap-[2px] overflow-hidden">
              {r.peaks.slice(-90).map((v, i) => (
                <span key={i} className="w-[3px] shrink-0 rounded-full bg-repealed/80" style={{ height: `${Math.max(8, Math.round(v * 100))}%` }} />
              ))}
            </div>
          </div>
          <div aria-hidden="true" className="h-1 overflow-hidden rounded-full bg-rule" dir="ltr">
            <div className="h-full bg-repealed/70" style={{ width: `${Math.min(100, (r.elapsedMs / MAX_TAKE_MS) * 100)}%` }} />
          </div>
          <div dir="ltr" className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => { r.discard(); onClose(); }}
                    className="h-10 rounded-full border border-rule bg-sheet px-4 text-meta hover:bg-paper">{t('recorder.cancel')}</button>
            <button type="button" onClick={r.phase === 'paused' ? r.resume : r.pause} disabled={r.phase === 'arming'}
                    className="h-10 rounded-full border border-rule bg-sheet px-4 text-meta hover:bg-paper">
              {r.phase === 'paused' ? t('recorder.resume') : t('recorder.pause')}
            </button>
            <button type="button" onClick={() => void r.finish()} disabled={r.phase === 'arming'}
                    className="h-10 rounded-full bg-stamp px-5 text-meta font-semibold text-on-stamp hover:bg-stamp-deep">{t('recorder.done')}</button>
          </div>
        </>
      ) : (
        <>
          <p className="m-0 text-body">{t('recorder.warning')}</p>
          <div dir="ltr" className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => void r.begin()}
                    className="inline-flex h-11 items-center gap-2 rounded-full bg-stamp px-5 text-body font-semibold text-on-stamp hover:bg-stamp-deep">
              <MicIcon />{t('recorder.start')}
            </button>
            <button type="button" onClick={onClose} className="h-11 rounded-full border border-rule bg-sheet px-4 text-meta hover:bg-paper">{t('recorder.cancel')}</button>
            <span className="text-meta text-ink-soft">{t('recorder.limit')}</span>
          </div>
          {r.failed && r.failed !== 'short' ? <p role="alert" className="m-0 text-meta text-repealed">{t(`recorder.${r.failed}`)}</p> : null}
        </>
      )}
      {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
    </div>
  );
}

export function MicIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  );
}
