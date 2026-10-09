// Pure-time helpers shared by short HTML/WebGL clips (ES module; MIT, this repository).
// Everything here is a function of t or of data loaded once; nothing keeps state between frames.

export const clamp = (x, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
export const lerp = (a, b, p) => a + (b - a) * p;
export const smooth = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
export const ease = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
export const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);
export const easeIn = (x) => Math.pow(clamp(x), 3);

// Closed-form step response of an underdamped spring, snapped to 1 once settled.
export function spring(tau, period = 0.45, zeta = 0.78) {
  if (tau <= 0) return 0;
  const w = 2 * Math.PI / period, wd = w * Math.sqrt(1 - zeta * zeta);
  const v = 1 - Math.exp(-zeta * w * tau) * (Math.cos(wd * tau) + (zeta * w / wd) * Math.sin(wd * tau));
  return tau > 2 * period && Math.abs(1 - v) < 2e-3 ? 1 : v;
}

// 0 outside [a, b); eases in over `fin` seconds and out over the last `fout` seconds.
export const windowed = (t, a, b, fin = 0.3, fout = 0.25) =>
  t < a || t >= b ? 0 : Math.min(easeOut((t - a) / fin), 1 - easeIn((t - (b - fout)) / fout));

// Stateless integer hash to [0, 1), and a seeded generator for building geometry once at load.
export function hash(n) {
  let x = (n | 0) + 0x9e3779b9;
  x = Math.imul(x ^ (x >>> 16), 0x85ebca6b);
  x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35);
  return ((x ^ (x >>> 16)) >>> 0) / 4294967296;
}
export function seeded(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// The contract served by the harness (or the example file when previewing), with cue lookup by name.
export async function loadContract(previewPath) {
  const harness = Boolean(window.__vch && window.__vch.harness);
  const contract = await fetch(harness ? "/contract.json" : previewPath).then((r) => r.json());
  const hits = (contract.timing?.hits || []).map((h) => (typeof h === "number" ? { t: h, kind: "tick" } : { kind: "tick", ...h }));
  const cues = new Map(hits.filter((h) => h.cue).map((h) => [h.cue, h.t]));
  const cue = (name) => {
    if (!cues.has(name)) throw new Error(`Missing cue in contract timing.hits: ${name}`);
    return cues.get(name);
  };
  return { contract, hits, cue, harness };
}

export function el(parent, cls, text, id) {
  const e = document.createElement("div");
  e.className = cls;
  if (text !== undefined) e.textContent = text;
  if (id) e.dataset.vchId = id;
  parent.appendChild(e);
  return e;
}

export function show(e, opacity) {
  e.style.opacity = opacity.toFixed(3);
  e.style.visibility = opacity > 0.002 ? "visible" : "hidden";
}

export function place(e, x, y, align, opacity) {
  const shift = align === "c" ? -50 : align === "r" ? -100 : 0;
  e.style.transform = `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) translateX(${shift}%)`;
  show(e, opacity);
}

// Words in overflow masks that rise into place; returns the word spans.
export function maskedWords(parent, text) {
  return text.split(" ").map((w, i, all) => {
    const mask = document.createElement("span"); mask.className = "mask";
    const word = document.createElement("span"); word.className = "word"; word.textContent = w;
    mask.appendChild(word); parent.appendChild(mask);
    if (i < all.length - 1) parent.appendChild(document.createTextNode(" "));
    return word;
  });
}
export function riseWords(words, t, start, stagger = 0.05) {
  words.forEach((w, k) => {
    w.style.transform = `translateY(${((1 - spring(t - start - stagger * k, 0.5, 0.82)) * 118).toFixed(2)}%)`;
  });
}

// Preview outside the harness: scale the stage to the window and loop on the wall clock.
export function preview(stage, width, height, duration, seek) {
  const fit = () => { stage.style.transform = `scale(${Math.min(innerWidth / width, innerHeight / height)})`; };
  fit(); addEventListener("resize", fit);
  const loop = (now) => { seek((now / 1000) % duration); requestAnimationFrame(loop); };
  requestAnimationFrame(loop);
}
