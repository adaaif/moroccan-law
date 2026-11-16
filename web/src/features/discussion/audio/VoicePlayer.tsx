import { useEffect, useRef, useState } from 'react';
import { clock, useT } from '../strings';
import { heardAt } from './heard';

/** One sound at a time across the page: a player that starts silences the one before. */
let playing: HTMLAudioElement | null = null;

const SPEEDS = [1, 1.5, 2];
const KEY = 'law.voice.';

function remembered(id: string): number {
  try {
    return Number(localStorage.getItem(KEY + id)) || 0;
  } catch {
    return 0;
  }
}

/**
 * A voice, played. Laid out left to right in every language (the choice of 19 Oct 2026): the button on the
 * left, the waveform filling from the left, the time in Western digits. 1×, 1.5× or 2×, and where the listener
 * stopped is kept on the device (R5). A link that ran out (30 minutes) is asked for again once. `jump` (a moment in
 * ms) moves there and plays: a reviewer's reported moment (F6).
 */
export function VoicePlayer({ id, src, durationMs, peaks, refresh, compact = false, jump }: {
  id: string;
  src: string;
  durationMs: number;
  peaks: number[];
  refresh?: () => Promise<string>;
  compact?: boolean;
  jump?: { ms: number; at: number } | null;
}) {
  const { t } = useT();
  const audio = useRef<HTMLAudioElement>(null);
  const [url, setUrl] = useState(src);
  const [on, setOn] = useState(false);
  const [at, setAt] = useState(() => remembered(id));
  const [speed, setSpeed] = useState(1);
  const retried = useRef(false);

  useEffect(() => setUrl(src), [src]);
  useEffect(() => () => {
    if (playing === audio.current) playing = null;
  }, []);
  useEffect(() => {
    const el = audio.current;
    if (!el || !jump) return;
    el.currentTime = jump.ms / 1000;
    setAt(jump.ms);
    void el.play();
  }, [jump]);

  const bars = peaks.length ? peaks : Array.from({ length: 48 }, () => 0.35);
  const total = durationMs || 1;
  const progress = Math.min(1, at / total);

  const toggle = () => {
    const el = audio.current;
    if (!el) return;
    if (el.paused) void el.play();
    else el.pause();
  };
  const seekTo = (fraction: number) => {
    const el = audio.current;
    if (!el) return;
    el.currentTime = (Math.max(0, Math.min(1, fraction)) * total) / 1000;
    setAt(el.currentTime * 1000);
  };

  return (
    <div dir="ltr" className={`flex w-full items-center gap-3 rounded-full border border-rule bg-sheet py-1.5 pe-4 ps-1.5 ${compact ? 'max-w-xs' : 'max-w-md'}`}>
      <button type="button" onClick={toggle} aria-label={on ? t('recorder.pausePlay') : t('recorder.play')}
              className="grid size-10 shrink-0 place-items-center rounded-full bg-stamp text-on-stamp hover:bg-stamp-deep">
        {on ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5Z" /></svg>
        )}
      </button>
      <div role="slider" tabIndex={0} aria-label={t('recorder.seek')} aria-valuemin={0} aria-valuemax={Math.round(total / 1000)}
           aria-valuenow={Math.round(at / 1000)} aria-valuetext={`${clock(at)} / ${clock(total)}`}
           onClick={(e) => {
             const r = e.currentTarget.getBoundingClientRect();
             seekTo((e.clientX - r.left) / r.width);
           }}
           onKeyDown={(e) => {
             if (e.key === 'ArrowRight') seekTo(progress + 5000 / total);
             if (e.key === 'ArrowLeft') seekTo(progress - 5000 / total);
             if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggle(); }
           }}
           className="flex h-10 min-w-0 flex-1 cursor-pointer items-center gap-[2px] overflow-hidden">
        {bars.map((v, i) => (
          <span key={i} aria-hidden="true"
                className={`w-[3px] shrink-0 rounded-full ${i / bars.length < progress ? 'bg-stamp' : 'bg-stamp/35'}`}
                style={{ height: `${Math.max(12, Math.round(v * 100))}%` }} />
        ))}
      </div>
      <span className="shrink-0 text-meta tabular-nums text-ink-soft">{on || at > 0 ? clock(at) : clock(total)}</span>
      <button type="button" aria-label={`${t('speed')} ${speed}×`}
              onClick={() => {
                const next = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length];
                setSpeed(next);
                if (audio.current) audio.current.playbackRate = next;
              }}
              className="h-10 min-w-10 shrink-0 rounded-full border border-rule px-2 text-meta font-semibold tabular-nums text-ink-soft hover:border-stamp hover:text-stamp">
        {speed}×
      </button>
      <audio ref={audio} src={url} preload="none"
             onLoadedMetadata={(e) => {
               // Back where the listener stopped, unless they had heard it to the end.
               if (at > 0 && at < total - 1000) e.currentTarget.currentTime = at / 1000;
               e.currentTarget.playbackRate = speed;
             }}
             onPlay={(e) => {
               if (playing && playing !== e.currentTarget) playing.pause();
               playing = e.currentTarget;
               e.currentTarget.playbackRate = speed;
               setOn(true);
             }}
             onPause={() => setOn(false)}
             onEnded={() => {
               setOn(false);
               setAt(0);
               try { localStorage.removeItem(KEY + id); } catch { /* private mode */ }
             }}
             onTimeUpdate={(e) => {
               const ms = Math.round(e.currentTarget.currentTime * 1000);
               setAt(ms);
               heardAt.set(id, ms);
               try { localStorage.setItem(KEY + id, String(ms)); } catch { /* private mode */ }
             }}
             onError={() => {
               if (!refresh || retried.current) return;
               retried.current = true;
               void refresh().then((fresh) => setUrl(fresh));
             }} />
    </div>
  );
}
