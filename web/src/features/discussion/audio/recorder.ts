import { create } from 'zustand';

/**
 * The microphone: a store and module singletons, since a MediaRecorder and a live
 * microphone never live in React state. One microphone, one take: the form that claims it last holds it.
 *
 * WebM/Opus where the browser makes it (Chrome, Edge, Firefox, Android, recent Safari), AAC in MP4 where it does
 * not (older Safari). The plain «audio/mp4» spelling is never asked for: in Chromium it means Opus inside MP4, which
 * plays nowhere on an iPhone and which the site's door refuses. The server turns every take into AAC.
 *
 * A meter on the audio thread (voiceMeter.worklet.js) draws the waveform while recording, and keeps counting when
 * the tab is hidden. Two minutes at most (D4); the take stops itself there.
 */

export const MAX_TAKE_MS = 120_000;
const MIN_TAKE_MS = 1_000;
const BIT_RATE = 48_000;
const HOP_MS = 100;
const CONTAINERS = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4;codecs=mp4a.40.2'];
const UPLOAD_PEAKS = 200;

export type Phase = 'idle' | 'arming' | 'recording' | 'paused' | 'reviewing';
export type Take = { blob: Blob; url: string; durationMs: number; peaks: number[] };

type State = {
  owner: string | null;
  phase: Phase;
  elapsedMs: number;
  peaks: number[];
  failed: '' | 'micDenied' | 'failed' | 'short';
  take: Take | null;
  claim: (owner: string) => void;
  release: (owner: string) => void;
  begin: () => Promise<void>;
  pause: () => void;
  resume: () => void;
  finish: () => Promise<void>;
  discard: () => void;
};

export function canRecord(): boolean {
  return typeof window !== 'undefined' && typeof MediaRecorder !== 'undefined' &&
    typeof AudioWorkletNode !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia) &&
    CONTAINERS.some((type) => MediaRecorder.isTypeSupported(type));
}

/** Hop power → a bar of 0..1; ×3 spreads a speaking voice across the bar's height. */
const peakOf = (power: number) => Math.min(1, Math.sqrt(power) * 3);

export function stride(peaks: number[], max = UPLOAD_PEAKS): number[] {
  if (peaks.length <= max) return [...peaks];
  const step = peaks.length / max;
  return Array.from({ length: max }, (_, i) => peaks[Math.floor(i * step)]);
}

let stream: MediaStream | null = null;
let recorder: MediaRecorder | null = null;
let ctx: AudioContext | null = null;
let chunks: Blob[] = [];
let hops: number[] = [];

function releaseMic() {
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
  void ctx?.close();
  ctx = null;
}

export const useRecorder = create<State>((set, get) => ({
  owner: null,
  phase: 'idle',
  elapsedMs: 0,
  peaks: [],
  failed: '',
  take: null,

  claim: (form) => {
    if (get().owner === form) return;
    get().discard();
    set({ owner: form });
  },

  release: (form) => {
    if (get().owner !== form) return;
    get().discard();
    set({ owner: null });
  },

  begin: async () => {
    if (get().phase !== 'idle') return;
    set({ phase: 'arming', failed: '', peaks: [], elapsedMs: 0 });
    chunks = [];
    hops = [];
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, autoGainControl: true, echoCancellation: true, noiseSuppression: true },
      });
    } catch (err) {
      set({ phase: 'idle', failed: err instanceof DOMException && err.name === 'NotAllowedError' ? 'micDenied' : 'failed' });
      return;
    }
    try {
      ctx = new AudioContext();
      await ctx.audioWorklet.addModule(new URL('./voiceMeter.worklet.js', import.meta.url));
      await ctx.resume();
      const meter = new AudioWorkletNode(ctx, 'voice-meter');
      meter.port.onmessage = (event: MessageEvent<number>) => {
        if (get().phase !== 'recording') return;
        hops.push(event.data);
        set({ peaks: [...get().peaks, peakOf(event.data)], elapsedMs: hops.length * HOP_MS });
        if (hops.length * HOP_MS >= MAX_TAKE_MS) void get().finish();
      };
      // An unpulled worklet never runs: it reaches the speakers through a gain of zero.
      const silence = ctx.createGain();
      silence.gain.value = 0;
      ctx.createMediaStreamSource(stream).connect(meter).connect(silence).connect(ctx.destination);
      const mimeType = CONTAINERS.find((type) => MediaRecorder.isTypeSupported(type));
      recorder = new MediaRecorder(stream, { mimeType, audioBitsPerSecond: BIT_RATE });
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      recorder.start(1000);
      set({ phase: 'recording' });
    } catch {
      releaseMic();
      set({ phase: 'idle', failed: 'failed' });
    }
  },

  pause: () => {
    if (get().phase !== 'recording') return;
    recorder?.pause();
    set({ phase: 'paused' });
  },

  resume: () => {
    if (get().phase !== 'paused') return;
    recorder?.resume();
    set({ phase: 'recording' });
  },

  finish: async () => {
    const phase = get().phase;
    if ((phase !== 'recording' && phase !== 'paused') || !recorder) return;
    const active = recorder;
    recorder = null;
    const blob = await new Promise<Blob>((resolve) => {
      active.onstop = () => resolve(new Blob(chunks, { type: active.mimeType }));
      active.stop();
    });
    releaseMic();
    const durationMs = hops.length * HOP_MS;
    if (durationMs < MIN_TAKE_MS) {
      chunks = [];
      hops = [];
      set({ phase: 'idle', elapsedMs: 0, peaks: [], failed: 'short', take: null });
      return;
    }
    set({ phase: 'reviewing', take: { blob, url: URL.createObjectURL(blob), durationMs,
                                      peaks: stride(hops.map(peakOf)) } });
  },

  discard: () => {
    const active = recorder;
    recorder = null;
    if (active && active.state !== 'inactive') {
      active.onstop = null;
      active.stop();
    }
    releaseMic();
    const url = get().take?.url;
    // The review's player still holds the address until React redraws it: let it go a moment later.
    if (url) window.setTimeout(() => URL.revokeObjectURL(url), 2000);
    chunks = [];
    hops = [];
    set({ phase: 'idle', elapsedMs: 0, peaks: [], failed: '', take: null });
  },
}));
