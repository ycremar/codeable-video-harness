// Injected by vch before any composition script runs.
// Makes time and randomness explicit, seeks the composition to an exact time and
// reports visible text as telemetry. It is a measurement aid, not a sandbox.
(() => {
  const config = __VCH_CONFIG__;
  let virtualMs = 0;

  // Seeded PRNG: libraries that call Math.random while initialising stay reproducible.
  // Calls made during seek(t) still depend on call order; the harness seek checks catch that.
  let state = (config.seed >>> 0) ^ 0x9e3779b9;
  Math.random = function seededRandom() {
    state = (state + 0x6d2b79f5) | 0;
    let x = Math.imul(state ^ (state >>> 15), 1 | state);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };

  // Every clock reads composition time, so time-driven shaders and libraries follow seek(t).
  const EPOCH_MS = Date.UTC(2026, 0, 1);
  const NativeDate = Date;
  class VirtualDate extends NativeDate {
    constructor(...args) { super(...(args.length ? args : [EPOCH_MS + virtualMs])); }
    static now() { return EPOCH_MS + virtualMs; }
  }
  window.Date = VirtualDate;
  Object.defineProperty(performance, 'now', { value: () => virtualMs });
  const nativeRaf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (callback) => nativeRaf(() => callback(virtualMs));

  function noise(key) {
    let h = 0x811c9dc5;
    const text = `${config.seed}:${key}`;
    for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193); }
    h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b); h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35); h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  }

  window.__vch = {
    harness: true, seed: config.seed, fps: config.fps, width: config.width,
    height: config.height, duration: config.duration, noise,
  };

  let probe = null;
  const colorCache = new Map();
  const fontCache = new Map();
  const round = (v, digits = 2) => Math.round(v * 10 ** digits) / 10 ** digits;
  const MIN_VISIBLE_FRACTION = 0.15;  // a masked word showing less than this is still hidden
  const SIZE_SNAP = 0.04;             // line boxes are pixel-snapped; within ±4% report the CSS size

  function probeContext() {
    if (!probe) {
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 1;
      probe = canvas.getContext('2d', { willReadFrequently: true });
    }
    return probe;
  }

  function rgba(color) {
    if (!color || color === 'transparent' || color === 'none' || color.startsWith('url(')) return null;
    if (colorCache.has(color)) return colorCache.get(color);
    const ctx = probeContext();
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = '#000';
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    const value = d[3] === 0 ? null : [d[0], d[1], d[2], round(d[3] / 255, 3)];
    colorCache.set(color, value);
    return value;
  }

  // Content-area height per 100px of the primary font: rendered size = line box height / ratio.
  // Works through CSS transforms, SVG viewBox scaling and zoom without parsing matrices.
  function contentRatio(style) {
    const font = `${style.fontStyle} ${style.fontWeight} 100px ${style.fontFamily}`;
    if (fontCache.has(font)) return fontCache.get(font);
    const ctx = probeContext();
    ctx.font = font;
    const m = ctx.measureText('Hg');
    const ratio = (m.fontBoundingBoxAscent + m.fontBoundingBoxDescent) / 100;
    const value = Number.isFinite(ratio) && ratio > 0 ? ratio : null;
    fontCache.set(font, value);
    return value;
  }

  function effectiveOpacity(el) {
    let opacity = 1;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const style = getComputedStyle(n);
      opacity *= parseFloat(style.opacity);
      if (n instanceof SVGElement && style.fillOpacity) opacity *= n === el ? parseFloat(style.fillOpacity) : 1;
    }
    return opacity;
  }

  function lengths(text, reference) {
    return text.trim().split(/\s+/).map((v) => (v.endsWith('%') ? parseFloat(v) / 100 * reference : parseFloat(v)));
  }

  // Bounding box of common clip-path shapes on `el`, in viewport pixels; null = unknown shape.
  function clipPathBox(el, style) {
    const value = style.clipPath;
    if (!value || value === 'none') return undefined;
    const r = el.getBoundingClientRect();
    const inset = value.match(/^inset\(([^)]*?)(?:\sround\s[^)]*)?\)$/);
    if (inset) {
      const v = inset[1].trim().split(/\s+/);
      const [t, ri, b, l] = [v[0], v[1] ?? v[0], v[2] ?? v[0], v[3] ?? v[1] ?? v[0]];
      const px = (x, ref) => (x.endsWith('%') ? parseFloat(x) / 100 * ref : parseFloat(x));
      return [r.left + px(l, r.width), r.top + px(t, r.height), r.right - px(ri, r.width), r.bottom - px(b, r.height)];
    }
    const circle = value.match(/^circle\(([^)]*?)\sat\s([^)]*)\)$/);
    if (circle) {
      const radius = lengths(circle[1], Math.hypot(r.width, r.height) / Math.SQRT2)[0];
      const [cx, cy] = [lengths(circle[2].split(/\s+/)[0], r.width)[0], lengths(circle[2].split(/\s+/)[1] ?? '50%', r.height)[0]];
      return [r.left + cx - radius, r.top + cy - radius, r.left + cx + radius, r.top + cy + radius];
    }
    const polygon = value.match(/^polygon\((?:[a-z]+,\s*)?([^)]*)\)$/);
    if (polygon) {
      const points = polygon[1].split(',').map((p) => p.trim().split(/\s+/));
      const xs = points.map((p) => lengths(p[0], r.width)[0]);
      const ys = points.map((p) => lengths(p[1], r.height)[0]);
      return [r.left + Math.min(...xs), r.top + Math.min(...ys), r.left + Math.max(...xs), r.top + Math.max(...ys)];
    }
    return null;
  }

  function intersect(a, b) {
    const c = [Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3])];
    return c[2] - c[0] > 0.5 && c[3] - c[1] > 0.5 ? c : null;
  }

  // Clip a text rectangle by overflow/clip-path masks on the element and its ancestors.
  function clip(el, rect) {
    let box = rect;
    for (let n = el; n && n.nodeType === 1 && box; n = n.parentElement) {
      const style = getComputedStyle(n);
      if (style.overflowX !== 'visible' || style.overflowY !== 'visible') {
        const r = n.getBoundingClientRect();
        box = intersect(box, [
          style.overflowX !== 'visible' ? r.left : -Infinity, style.overflowY !== 'visible' ? r.top : -Infinity,
          style.overflowX !== 'visible' ? r.right : Infinity, style.overflowY !== 'visible' ? r.bottom : Infinity]);
      }
      const shape = box && clipPathBox(n, style);
      if (shape) box = intersect(box, shape);
    }
    return box;
  }

  function elementId(el) {
    const path = [];
    for (let n = el; n && n.nodeType === 1 && n !== document.body; n = n.parentElement) {
      if (n.dataset && n.dataset.vchId) { path.unshift(n.dataset.vchId); break; }
      if (n.id) { path.unshift(`#${n.id}`); break; }
      const parent = n.parentElement;
      const index = parent ? Array.prototype.indexOf.call(parent.children, n) + 1 : 1;
      path.unshift(`${n.tagName.toLowerCase()}:${index}`);
    }
    return path.join('>') || 'body';
  }

  function displayed(text, style) {
    const t = text.replace(/\s+/g, ' ').trim();
    if (style.textTransform === 'uppercase') return t.toUpperCase();
    if (style.textTransform === 'lowercase') return t.toLowerCase();
    if (style.textTransform === 'capitalize') return t.replace(/\b\p{L}/gu, (c) => c.toUpperCase());
    return t;
  }

  function collect() {
    const W = config.width, H = config.height;
    const out = [];
    const counts = new Map();
    const range = document.createRange();
    const root = document.body || document.documentElement;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const visibleNodes = new Set();
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const el = node.parentElement;
      if (!el || !node.nodeValue.trim() || el.closest('script,style,noscript,template,title,[data-vch-ignore]')) continue;
      const style = getComputedStyle(el);
      if (style.visibility !== 'visible') continue;
      const opacity = effectiveOpacity(el);
      if (opacity < 0.05) continue;
      range.selectNodeContents(node);
      const rects = [];
      for (const r of range.getClientRects()) {
        if (r.width < 0.5 || r.height < 0.5) continue;
        const box = clip(el, [r.left, r.top, r.right, r.bottom]);
        if (!box || box[2] <= 0 || box[3] <= 0 || box[0] >= W || box[1] >= H) continue;
        const shownW = box[2] - box[0], shownH = box[3] - box[1];
        if (shownH < Math.max(2, MIN_VISIBLE_FRACTION * r.height) || shownW < Math.max(2, MIN_VISIBLE_FRACTION * r.width)) continue;
        rects.push([...box.map((v) => round(v)), r.height]);
      }
      if (!rects.length) continue;
      visibleNodes.add(node);
      const n = counts.get(el) || 0;
      counts.set(el, n + 1);
      const heights = rects.map((r) => r[4]).sort((a, b) => a - b);
      const ratio = contentRatio(style);
      const cssSize = parseFloat(style.fontSize);
      const scale = ratio ? heights[Math.floor(heights.length / 2)] / ratio / cssSize : 1;
      const size = Math.abs(scale - 1) < SIZE_SNAP ? cssSize : cssSize * scale;
      const boxes = rects.map((r) => r.slice(0, 4));
      out.push({
        id: elementId(el) + (n ? `#${n}` : ''), type: 'text', text: displayed(node.nodeValue, style),
        bbox: [Math.min(...boxes.map((b) => b[0])), Math.min(...boxes.map((b) => b[1])),
               Math.max(...boxes.map((b) => b[2])), Math.max(...boxes.map((b) => b[3]))],
        rects: boxes, size: round(size), color: rgba(el instanceof SVGElement ? style.fill : (style.webkitTextFillColor || style.color)),
        opacity: round(opacity, 3), source: 'dom',
      });
    }
    out.push(...groups(visibleNodes));
    const declared = Array.isArray(window.__vch?.elements) ? window.__vch.elements : [];
    for (const e of declared) out.push({ ...e, source: 'declared' });
    return out;
  }

  // Words split into separate spans (masked reveals) still read as one line: report the
  // visible text of each data-vch-id element as a 'text-group' for copy checks.
  function groups(visibleNodes) {
    const owners = new Map();
    for (const node of visibleNodes) {
      const owner = node.parentElement.closest('[data-vch-id]');
      if (owner) owners.set(owner, (owners.get(owner) || 0) + 1);
    }
    const result = [];
    for (const [owner, count] of owners) {
      if (count < 2) continue;
      const parts = [];
      const walker = document.createTreeWalker(owner, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (visibleNodes.has(node)) parts.push(displayed(node.nodeValue, getComputedStyle(node.parentElement)));
        else if (!node.nodeValue.trim()) parts.push(' ');
      }
      const text = parts.join('').replace(/\s+/g, ' ').trim();
      if (text) result.push({ id: owner.dataset.vchId, type: 'text-group', text, source: 'dom' });
    }
    return result;
  }

  async function frame(t) {
    virtualMs = t * 1000;
    const api = window.__vch || {};
    if (api.ready && typeof api.ready.then === 'function') await api.ready;
    const seek = typeof api.seek === 'function' ? api.seek : (typeof window.seek === 'function' ? window.seek : null);
    const timelines = window.__timelines && typeof window.__timelines === 'object' ? Object.values(window.__timelines) : [];
    if (!seek && !timelines.length && !document.getAnimations().length) {
      throw new Error('Composition must define window.__vch.seek(t) or window.seek(t), register paused timelines on window.__timelines, or use CSS/Web Animations');
    }
    if (seek) await seek(t);
    for (const tl of timelines) {
      if (tl && typeof tl.pause === 'function') tl.pause();
      if (tl && typeof tl.seek === 'function') tl.seek(t);
      else if (tl && typeof tl.totalTime === 'function') tl.totalTime(t);
    }
    for (const animation of document.getAnimations()) {
      animation.pause();
      if (typeof CSSTransition !== 'undefined' && animation instanceof CSSTransition) animation.finish();
      else animation.currentTime = t * 1000;
    }
    void document.documentElement.offsetHeight;  // flush layout so newly shown text requests its fonts
    await document.fonts.ready;
    await Promise.all([...document.images].filter((img) => !img.complete).map((img) => img.decode().catch(() => {})));
    return { elements: collect() };
  }

  // Composition-authored sound: window.__vch.audio({ sampleRate, duration, channels }) returns one or two
  // Float32Arrays of exactly round(sampleRate * duration) samples. They travel back as base64 float32 chunks.
  const AUDIO_CHUNK_BYTES = 3 * 262144;
  async function audio(sampleRate, duration) {
    const api = window.__vch || {};
    if (api.ready && typeof api.ready.then === 'function') await api.ready;
    if (typeof api.audio !== 'function') {
      throw new Error("audio.mode 'composition' needs window.__vch.audio({ sampleRate, duration, channels })");
    }
    const result = await api.audio({ sampleRate, duration, channels: 2 });
    const channels = Array.isArray(result) ? result : [result];
    const length = Math.round(sampleRate * duration);
    if (!channels.length || channels.length > 2 || !channels.every((c) => c instanceof Float32Array && c.length === length)) {
      throw new Error(`window.__vch.audio must return 1 or 2 Float32Arrays of ${length} samples`);
    }
    const interleaved = new Float32Array(length * channels.length);
    for (let i = 0; i < length; i++) {
      for (let c = 0; c < channels.length; c++) {
        const value = channels[c][i];
        if (!Number.isFinite(value)) throw new Error(`Non-finite audio sample at ${i}`);
        interleaved[i * channels.length + c] = value;
      }
    }
    const bytes = new Uint8Array(interleaved.buffer), chunks = [];
    for (let i = 0; i < bytes.length; i += AUDIO_CHUNK_BYTES) {
      const part = bytes.subarray(i, i + AUDIO_CHUNK_BYTES);
      let text = '';
      for (let j = 0; j < part.length; j += 0x8000) text += String.fromCharCode.apply(null, part.subarray(j, j + 0x8000));
      chunks.push(btoa(text));
    }
    return { channels: channels.length, chunks };
  }

  Object.defineProperty(window, '__vchHarness', { value: Object.freeze({ frame, collect, audio }), writable: false, configurable: false });
})();
