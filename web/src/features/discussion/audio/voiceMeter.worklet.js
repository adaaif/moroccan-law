/**
 * «مقياس الصوت» — the meter that rides the microphone.
 *
 * It runs on the AUDIO thread, not the page's, for one reason that decides
 * the whole file: a `requestAnimationFrame` meter stops when the tab is
 * hidden, and a woman who switches to WhatsApp mid-tale would come back to a
 * waveform with a hole in it and a speech map that says she was silent for
 * four minutes. The audio thread keeps counting.
 *
 * It emits ONE number per 100 ms hop: the mean square of that hop. That is
 * deliberately the raw material rather than a finished bar — the same number
 * feeds the waveform (√ then gain) and «خريطة الكلام» (the energy gate), and
 * the phone's `loudness.ts` measures both from exactly this. Sending anything
 * more cooked would make the two surfaces disagree.
 *
 * The node is connected through a silent gain into the destination, because
 * a worklet nothing pulls from is a worklet that never runs — it is metering
 * her voice, never playing it back.
 */

/* global AudioWorkletProcessor, registerProcessor, sampleRate */

const HOP_MS = 100;

class VoiceMeter extends AudioWorkletProcessor {
  constructor() {
    super();
    this.perHop = Math.max(1, Math.round((sampleRate * HOP_MS) / 1000));
    this.sumSquares = 0;
    this.count = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) {
      for (let i = 0; i < channel.length; i += 1) {
        const x = channel[i];
        this.sumSquares += x * x;
        this.count += 1;
        if (this.count >= this.perHop) {
          this.port.postMessage(this.sumSquares / this.count);
          this.sumSquares = 0;
          this.count = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor('voice-meter', VoiceMeter);
