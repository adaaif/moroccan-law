import { useEffect, useState } from 'react';

/** The device's own voice for a language (call C6: nothing is sent anywhere), or null when it has none. */
export function useVoice(lang: 'ar' | 'fr'): SpeechSynthesisVoice | null {
  const [voice, setVoice] = useState<SpeechSynthesisVoice | null>(null);
  useEffect(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    const pick = () => {
      const voices = window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith(lang));
      // A Moroccan voice first, then any local one, then any.
      setVoice(voices.find((v) => /-MA$/i.test(v.lang)) ?? voices.find((v) => v.localService) ?? voices[0] ?? null);
    };
    pick();
    window.speechSynthesis.addEventListener('voiceschanged', pick);
    return () => window.speechSynthesis.removeEventListener('voiceschanged', pick);
  }, [lang]);
  return voice;
}

let current: { stop: () => void; id: string } | null = null;
const heard = new Set<() => void>();
const tell = () => heard.forEach((f) => f());

/** Which article the device is reading aloud, kept outside any button (PX21 of the where-it-trips review): the voice goes
 *  on when the phone's tool sheet closes or another article takes the row, and the button finds its state again. */
export function speaking(): string | null {
  return current?.id ?? null;
}
export function stopSpeaking(): void {
  current?.stop();
}
export function onSpeaking(f: () => void): () => void {
  heard.add(f);
  return () => { heard.delete(f); };
}

/** While the voice reads, a bar at the foot of the screen names the article and stops it: the button that started it
 *  may be gone (its sheet closed). Plain DOM, drawn once, with the theme's colours. */
function bar(title: string, stopLabel: string, stop: () => void): () => void {
  const el = document.createElement('div');
  el.setAttribute('role', 'status');
  el.setAttribute('data-noprint', '');
  el.style.cssText = 'position:fixed;inset-inline:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px));z-index:60;display:flex;'
    + 'align-items:center;gap:12px;max-width:28rem;margin-inline:auto;padding:6px 6px 6px 16px;border-radius:999px;'
    + 'background:var(--color-ink);color:var(--color-sheet);box-shadow:0 8px 24px -8px rgb(0 0 0/.4);font-size:15px';
  const name = document.createElement('span');
  name.textContent = title;
  name.style.cssText = 'flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = stopLabel;
  button.style.cssText = 'min-height:44px;padding:0 18px;border-radius:999px;background:var(--color-sheet);color:var(--color-ink);font-weight:600';
  button.addEventListener('click', stop);
  el.append(name, button);
  document.body.append(el);
  return () => el.remove();
}

/** Reads `text` aloud a sentence or so at a time (long utterances are cut short on Android), stopping any
 *  reading already under way. Returns the stop. `id` names what is read; `shown` titles its bar and its stop button. */
export function speak(text: string, voice: SpeechSynthesisVoice, onEnd: () => void, id = '',
                      shown?: { title: string; stop: string }): () => void {
  current?.stop();
  const synth = window.speechSynthesis;
  const parts = text.match(/[^.!?؟؛:\n]+[.!?؟؛:\n]*/g)?.flatMap((s) => s.length > 220 ? s.match(/.{1,220}(\s|$)/g) ?? [s] : [s])
    .map((s) => s.trim()).filter(Boolean) ?? [];
  let stopped = false;
  let unbar = () => {};
  const stop = () => {
    if (stopped) return;
    stopped = true;
    synth.cancel();
    unbar();
    if (current?.stop === stop) current = null;
    onEnd();
    tell();
  };
  parts.forEach((p, i) => {
    const u = new SpeechSynthesisUtterance(p);
    u.voice = voice;
    u.lang = voice.lang;
    u.rate = 0.95;
    if (i === parts.length - 1) u.onend = stop;
    u.onerror = stop;
    synth.speak(u);
  });
  current = { stop, id };
  if (shown) unbar = bar(shown.title, shown.stop, stop);
  tell();
  return stop;
}
