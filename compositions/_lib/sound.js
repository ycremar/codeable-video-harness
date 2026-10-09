// Sound mechanics for compositions that synthesize their own audio (ES module; MIT, this repository).
// No instruments or presets live here: each film designs its own sounds. These helpers only hold samples,
// place a sound so its loudest sample lands on a cue, pan, filter, and duck a bed under cues.
// Everything is deterministic: use seeded() for noise, never Math.random.

export { seeded } from "/compositions/_lib/clip.js";

// A stereo buffer for the whole film.
export function stereo(sampleRate, duration) {
  const length = Math.round(sampleRate * duration);
  return { rate: sampleRate, length, left: new Float32Array(length), right: new Float32Array(length) };
}

// A mono clip of `seconds`, sample i computed by fn(t, i) with t in seconds from the clip start.
export function clip(sampleRate, seconds, fn) {
  const out = new Float32Array(Math.max(1, Math.round(sampleRate * seconds)));
  for (let i = 0; i < out.length; i++) out[i] = fn(i / sampleRate, i);
  return out;
}

export function peakIndex(samples) {
  let best = 0;
  for (let i = 1; i < samples.length; i++) if (Math.abs(samples[i]) > Math.abs(samples[best])) best = i;
  return best;
}

// Mix a mono clip into the buffer so its peak (or its start) lands on `at` seconds; equal-power pan -1..1.
export function place(buffer, samples, at, { align = "peak", gain = 1, pan = 0 } = {}) {
  const offset = align === "peak" ? peakIndex(samples) : 0;
  const start = Math.round(at * buffer.rate) - offset;
  const angle = (Math.max(-1, Math.min(1, pan)) + 1) * Math.PI / 4;
  const gl = Math.cos(angle) * gain, gr = Math.sin(angle) * gain;
  for (let i = Math.max(0, -start); i < samples.length && start + i < buffer.length; i++) {
    buffer.left[start + i] += samples[i] * gl;
    buffer.right[start + i] += samples[i] * gr;
  }
}

// One-pole low-pass in place (cutoff may be a number or a function of t); returns the array.
export function lowpass(samples, sampleRate, cutoff) {
  let y = 0;
  for (let i = 0; i < samples.length; i++) {
    const fc = typeof cutoff === "function" ? cutoff(i / sampleRate) : cutoff;
    const a = 1 - Math.exp(-2 * Math.PI * fc / sampleRate);
    y += a * (samples[i] - y);
    samples[i] = y;
  }
  return samples;
}

// Gain curve multiplied into a bed so each cue's own peak stays the loudest sample around it:
// fully dipped `lead` seconds before the cue, recovering over `release` seconds after it.
export function duck(samples, sampleRate, times, { depth = 0.7, attack = 0.06, lead = 0.05, release = 0.45 } = {}) {
  const gain = new Float32Array(samples.length).fill(1);
  for (const t of times) {
    const a = Math.round((t - lead - attack) * sampleRate), b = Math.round((t + release) * sampleRate);
    for (let i = Math.max(0, a); i < Math.min(samples.length, b); i++) {
      const s = i / sampleRate - t;
      let dip;
      if (s < -lead) dip = Math.sin(((s + lead + attack) / attack) * Math.PI / 2) ** 2;
      else if (s < 0) dip = 1;
      else dip = Math.cos((s / release) * Math.PI / 2) ** 2;
      gain[i] = Math.min(gain[i], 1 - depth * dip);
    }
  }
  for (let i = 0; i < samples.length; i++) samples[i] *= gain[i];
  return samples;
}

// Add a mono bed into both channels (optionally with a stereo width offset of `width` samples).
export function addBed(buffer, samples, { gain = 1, width = 0 } = {}) {
  for (let i = 0; i < buffer.length; i++) {
    buffer.left[i] += samples[i] * gain;
    buffer.right[i] += samples[Math.min(buffer.length - 1, i + width)] * gain;
  }
}
