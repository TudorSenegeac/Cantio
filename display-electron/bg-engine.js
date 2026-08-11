/**
 * Cantio — Background Engine (shared)
 * ------------------------------------------------------------------
 * Pure rendering engine for animated backgrounds. Used by BOTH the
 * background editor window AND the live display (display.js), so a
 * background designed in the editor renders byte-identically live.
 *
 * A "background" is a plain JSON object:
 *   { name, format:{w,h}, transition:{in,out,duration}, layers:[ ... ] }
 *
 * Layer types: gradient | particles | shape | text | image | video
 *
 * Exposed as the global `BgEngine` (no ES modules, so a plain
 * <script src="bg-engine.js"> works under Electron nodeIntegration).
 */
(function (global) {
  'use strict';

  // ── Live audio reactivity (driven by display.js Web Audio analyser) ─────────
  // _audio holds normalised 0..1 energy bands of the currently playing track;
  // layers with a `react` block pulse/glow/burst with it. _reveal (0..1) drives
  // word-by-word lyric reveal for layers flagged `reveal:true`.
  let _audio  = { level: 0, bass: 0, mid: 0, treble: 0 };
  let _reveal = 1;

  // ── Defaults / factories ────────────────────────────────────────────────────

  function uid() {
    return 'l' + Math.random().toString(36).slice(2, 9);
  }

  function defaultBackground() {
    return {
      name: 'Fundal nou',
      format: { w: 1920, h: 1080 },
      transition: { in: 'fade', out: 'fade', duration: 600 },
      layers: [ newLayer('gradient') ],
    };
  }

  function newLayer(type) {
    const base = {
      id: uid(), type, name: type, visible: true, opacity: 1,
      x: 0.5, y: 0.5,          // normalised centre (0..1)
      w: 0.4, h: 0.25,         // normalised size (0..1 of canvas)
      rotation: 0,
      shadow: { enabled: false, color: '#000000', blur: 18, x: 0, y: 8 },
      blur: 0,
      anim: {
        pulse:  { enabled: false, speed: 1.0, min: 0.85, max: 1.0 }, // opacity pulse
        scale:  { enabled: false, speed: 1.0, min: 0.96, max: 1.04 }, // size pulse
        float:  { enabled: false, speed: 1.0, amp: 0.02 },           // gentle drift
        spin:   { enabled: false, speed: 0.2 },                      // rotation
        glow:   { enabled: false, speed: 1.0, min: 6, max: 28 },     // shadow-blur pulse
        chaos:  { enabled: false, speed: 1.0, amp: 0.04 },           // chaotic drift (wow)
      },
      // Entrance (when the background appears) / exit (when it is replaced)
      entrance: { type: 'fade', duration: 700, delay: 0 },
      exit:     { type: 'fade', duration: 500, delay: 0 },
    };

    if (type === 'gradient') {
      Object.assign(base, {
        name: 'Gradient', x: 0.5, y: 0.5, w: 1, h: 1,
        gradientType: 'linear',          // linear | radial | conic
        angle: 135,
        stops: [
          { pos: 0,   color: '#1a237e' },
          { pos: 0.5, color: '#3949ab' },
          { pos: 1,   color: '#0d47a1' },
        ],
        animate: { mode: 'none', speed: 0.4 }, // none | rotate | shift | cycle
      });
    } else if (type === 'particles') {
      Object.assign(base, {
        name: 'Particule', x: 0.5, y: 0.5, w: 1, h: 1,
        preset: 'sparks',                // sparks | snow | fog | bokeh | embers
        count: 140,
        color: '#ffd27f',
        color2: '#ff7043',
        speed: 1.0,
        size: 1.0,
      });
    } else if (type === 'shape') {
      Object.assign(base, {
        name: 'Formă', shape: 'circle',  // rect | circle | triangle | line
        fillType: 'solid',               // solid | gradient | none
        color: '#5294e2',
        gradFrom: '#5294e2', gradTo: '#1a1a5a', gradAngle: 90,
        strokeColor: '#ffffff', strokeWidth: 0,
        radius: 0,                       // rounded-rect corner radius (px @1080)
      });
    } else if (type === 'text') {
      Object.assign(base, {
        name: 'Text', text: 'Text', font: 'Montserrat', size: 96,
        bold: true, italic: false, align: 'center',
        colorType: 'solid',              // solid | gradient | animated
        color: '#ffffff',
        gradFrom: '#ffffff', gradTo: '#9ec5ff', gradAngle: 90,
        letterSpacing: 0, lineHeight: 1.15, uppercase: false,
        echo: { enabled: false, scale: 2.4, opacity: 0.14, blur: 2 }, // big faint text behind
        w: 0.7, h: 0.3,
      });
    } else if (type === 'image') {
      Object.assign(base, {
        name: 'Imagine', src: '', fit: 'cover', // cover | contain | stretch
        w: 1, h: 1, x: 0.5, y: 0.5,
      });
    } else if (type === 'video') {
      Object.assign(base, {
        name: 'Video', src: '', fit: 'cover',
        loop: true, muted: true, w: 1, h: 1, x: 0.5, y: 0.5,
      });
    } else if (type === 'clock') {
      Object.assign(base, {
        name: 'Ceas', clockMode: 'clock',   // clock | date | stopwatch | countdown
        font: 'Montserrat', size: 140, bold: true, italic: false, align: 'center',
        colorType: 'solid',                  // solid | gradient | animated
        color: '#ffffff',
        gradFrom: '#ffffff', gradTo: '#9ec5ff', gradAngle: 90,
        letterSpacing: 0, uppercase: false,
        format24: true, showSeconds: false,  // clock
        duration: 300,                       // countdown seconds
        prefix: '', suffix: '',
        w: 0.6, h: 0.25,
      });
    } else if (type === 'lyrics') {
      Object.assign(base, {
        name: 'Versuri', font: 'Montserrat', size: 64, bold: true,
        align: 'center', w: 0.8, h: 0.7,
        color: '#ffffff',           // current line
        dimColor: '#ffffff', dimOpacity: 0.35,
        visibleLines: 5, lineGap: 1.7, scrollSpeed: 8,
        hlScale: 1.18, hlGlow: true, hlColor: '#ffffff',
        uppercase: true,
      });
    }
    return base;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function osc(tSec, speed) { return (Math.sin(tSec * speed * Math.PI * 2) + 1) / 2; } // 0..1

  function hexToRgb(hex) {
    const n = parseInt(String(hex).replace('#', ''), 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }
  function mixHex(a, b, t) {
    const A = hexToRgb(a), B = hexToRgb(b);
    const r = Math.round(lerp(A.r, B.r, t));
    const g = Math.round(lerp(A.g, B.g, t));
    const bl = Math.round(lerp(A.b, B.b, t));
    return `rgb(${r},${g},${bl})`;
  }

  function roundRectPath(ctx, x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // ── Master render ───────────────────────────────────────────────────────────

  /**
   * Render an entire background.
   * @param ctx        Canvas 2D context
   * @param W,H        canvas pixel size
   * @param bg         background JSON
   * @param tMs        animation clock in ms
   * @param alpha      master opacity 0..1 (used for in/out transitions)
   */
  function render(ctx, W, H, bg, tMs, opts) {
    if (!bg) return;
    let alpha = 1, intro = null, outro = null;
    if (typeof opts === 'number') alpha = opts;
    else if (opts) {
      alpha = (opts.alpha != null ? opts.alpha : 1);
      intro = opts.intro; outro = opts.outro;
    }
    const t = (tMs || 0) / 1000;
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    ctx.globalAlpha = clamp(alpha, 0, 1);

    const phase = {
      intro, outro,
      seq: !!(bg && bg.intro_sequence),
      stagger: (bg && bg.intro_stagger) || 350,
    };
    const layers = bg.layers || [];
    for (let i = 0; i < layers.length; i++) {
      const L = layers[i];
      if (!L || L.visible === false) continue;
      phase._i = i;
      drawLayer(ctx, W, H, L, t, phase, bg);
    }
    ctx.restore();
  }

  // Returns a transform for an entrance/exit at factor k (1 = in place, 0 = away)
  function phaseTransform(type, k, W, H) {
    const m = { op: 1, dx: 0, dy: 0, scale: 1, blur: 0, rot: 0 };
    const e = easeOutCubic(k);
    switch (type) {
      case 'fade':        m.op = e; break;
      case 'slide_left':  m.dx = -(1 - e) * W * 0.6; m.op = e; break;
      case 'slide_right': m.dx =  (1 - e) * W * 0.6; m.op = e; break;
      case 'slide_up':    m.dy =  (1 - e) * H * 0.6; m.op = e; break;
      case 'slide_down':  m.dy = -(1 - e) * H * 0.6; m.op = e; break;
      case 'rise':        m.dy =  (1 - e) * H * 0.25; m.op = e; break;
      case 'drop':        m.dy = -(1 - e) * H * 0.25; m.op = e; break;
      case 'zoom_in':     m.scale = 0.6 + 0.4 * e; m.op = e; break;
      case 'zoom_out':    m.scale = 1.4 - 0.4 * e; m.op = e; break;
      case 'blur':        m.blur = (1 - e) * 22; m.op = e; break;
      case 'pop': {
        const b = k < 1 ? 1 - Math.pow(1 - k, 3) : 1;
        m.scale = 0.4 + 0.6 * b + Math.sin(k * Math.PI) * 0.12; m.op = Math.min(1, k * 2);
        break;
      }
      // ── Concert-grade entrances/exits ─────────────────────────────────────
      case 'zoom_blur':     // dramatic punch-in reveal
        m.scale = 1.6 - 0.6 * e; m.blur = (1 - e) * 30; m.op = Math.min(1, k * 1.6); break;
      case 'slide_blur_left':
        m.dx = -(1 - e) * W * 0.7; m.blur = (1 - e) * 16; m.op = e; break;
      case 'slide_blur_right':
        m.dx =  (1 - e) * W * 0.7; m.blur = (1 - e) * 16; m.op = e; break;
      case 'rotate_in':
        m.rot = (1 - e) * Math.PI; m.scale = 0.5 + 0.5 * e; m.op = e; break;
      case 'swing': {        // rotate in with a settling overshoot
        const ov = Math.sin(k * Math.PI) * 0.18;
        m.rot = (1 - e) * 0.6 - ov; m.op = Math.min(1, k * 1.5); break;
      }
      case 'bounce': {       // drop in and bounce on landing
        const b = easeOutBounce(k);
        m.dy = -(1 - b) * H * 0.5; m.op = Math.min(1, k * 2.5); break;
      }
      case 'flip_x':         // fake vertical flip via squash on one axis
        m.scale = Math.abs(Math.sin(k * Math.PI / 2)) * 0.5 + 0.5; m.op = e; break;
      case 'glitch': {       // jittery digital reveal (first ~60%), then settle
        if (k < 0.6) {
          const j = (Math.random() - 0.5);
          m.dx = j * W * 0.05 * (1 - k); m.dy = (Math.random() - 0.5) * H * 0.03 * (1 - k);
          m.op = (Math.random() > 0.3) ? k : k * 0.3;
        } else { m.op = e; }
        break;
      }
      default: break; // 'none'
    }
    return m;
  }

  function easeOutBounce(t) {
    const n1 = 7.5625, d1 = 2.75;
    if (t < 1 / d1) return n1 * t * t;
    if (t < 2 / d1) { t -= 1.5 / d1; return n1 * t * t + 0.75; }
    if (t < 2.5 / d1) { t -= 2.25 / d1; return n1 * t * t + 0.9375; }
    t -= 2.625 / d1; return n1 * t * t + 0.984375;
  }

  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

  function computePhaseMod(L, phase) {
    if (!phase) return null;
    if (phase.intro != null) {
      const e = L.entrance || { type: 'none' };
      if (!e.type || e.type === 'none') return null;
      // Sequential entrance: stagger each layer by its stacking order so they
      // come in one after another (bottom layer first).
      const extra = phase.seq ? (phase._i || 0) * (phase.stagger || 350) : 0;
      const delay = (e.delay || 0) + extra, dur = e.duration || 600;
      const k = (phase.intro - delay) / dur;
      if (k >= 1) return null;
      if (k <= 0) return { op: 0, dx: 0, dy: 0, scale: 1, blur: 0 }; // not entered yet
      return phaseTransform(e.type, k, phase._W, phase._H);
    }
    if (phase.outro != null) {
      const e = L.exit || { type: 'none' };
      if (!e.type || e.type === 'none') return null;
      const delay = e.delay || 0, dur = e.duration || 600;
      const g = (phase.outro - delay) / dur;       // 0 = in place, 1 = gone
      if (g <= 0) return null;
      if (g >= 1) return { op: 0, dx: 0, dy: 0, scale: 1, blur: 0 };
      return phaseTransform(e.type, 1 - g, phase._W, phase._H);
    }
    return null;
  }

  function drawLayer(ctx, W, H, L, t, phase, bg) {
    if (phase) { phase._W = W; phase._H = H; }
    const pm = computePhaseMod(L, phase);
    if (pm && pm.op <= 0) return;   // fully hidden during entrance/exit
    ctx.save();
    if (pm) ctx.globalAlpha *= clamp(pm.op, 0, 1);

    // ── Animated modifiers (pulse / scale / float / spin / glow) ──────────────
    const a = L.anim || {};
    let opacity = (L.opacity != null ? L.opacity : 1);
    if (a.pulse && a.pulse.enabled)
      opacity *= lerp(a.pulse.min, a.pulse.max, osc(t, a.pulse.speed));
    ctx.globalAlpha *= clamp(opacity, 0, 1);

    let scale = 1;
    if (a.scale && a.scale.enabled)
      scale = lerp(a.scale.min, a.scale.max, osc(t, a.scale.speed));

    let rot = (L.rotation || 0) * Math.PI / 180;
    if (a.spin && a.spin.enabled) rot += t * a.spin.speed * Math.PI * 2;
    if (pm && pm.rot) rot += pm.rot;   // entrance/exit rotation (rotate_in/swing)

    let driftY = 0, driftX = 0;
    if (a.float && a.float.enabled)
      driftY = (osc(t, a.float.speed) - 0.5) * a.float.amp * H;
    // Chaotic drift — layered sines for an organic, unpredictable motion ("wow")
    if (a.chaos && a.chaos.enabled) {
      if (L._seed == null) L._seed = Math.random() * 100;
      const cs = a.chaos.speed || 1, amp = (a.chaos.amp || 0.04) * Math.min(W, H);
      driftX += (Math.sin(t * cs * 1.7 + L._seed) + Math.sin(t * cs * 3.3 + L._seed)) * amp * 0.5;
      driftY += (Math.cos(t * cs * 1.3 + L._seed) + Math.sin(t * cs * 2.1)) * amp * 0.5;
      rot    += Math.sin(t * cs * 0.9 + L._seed) * 0.18;
    }

    // ── Audio reactivity — pulse / glow / fade / vibrate with the track ───────
    let reactGlow = 0;
    const rc = L.react;
    if (rc && rc.enabled) {
      const v = (_audio[rc.src] != null ? _audio[rc.src] : _audio.level) || 0;
      const amt = (rc.amount != null ? rc.amount : 0.5);
      const tgt = rc.target || 'scale';
      if (tgt === 'scale')        scale *= 1 + amt * v;
      else if (tgt === 'opacity') ctx.globalAlpha *= clamp(1 - amt * 0.7 + amt * v, 0, 1);
      else if (tgt === 'glow')    reactGlow = amt * 80 * v;
      // Vibration on intense moments (quadratic so it kicks in on peaks only).
      if (rc.shake) {
        const amp = (rc.shakeAmt != null ? rc.shakeAmt : 16) * v * v;
        driftX += (Math.random() - 0.5) * amp;
        driftY += (Math.random() - 0.5) * amp;
      }
    }

    // Shadow
    const sh = L.shadow;
    if (sh && sh.enabled) {
      let blur = sh.blur;
      if (a.glow && a.glow.enabled)
        blur = lerp(a.glow.min, a.glow.max, osc(t, a.glow.speed));
      ctx.shadowColor   = sh.color || '#000';
      ctx.shadowBlur    = blur;
      ctx.shadowOffsetX = sh.x || 0;
      ctx.shadowOffsetY = sh.y || 0;
    }
    if (reactGlow > 0) {              // beat glow even without a base shadow
      ctx.shadowColor = (L.color || L.hlColor || '#ffffff');
      ctx.shadowBlur  = (ctx.shadowBlur || 0) + reactGlow;
    }
    const totalBlur = (L.blur || 0) + (pm ? pm.blur : 0);
    if (totalBlur > 0) {
      try { ctx.filter = `blur(${totalBlur}px)`; } catch (e) {}
    }

    // Apply entrance/exit scale to the animated scale
    if (pm) scale *= pm.scale;

    // Full-canvas layers (gradient/particles ignore positional transform)
    const fullBleed = (L.type === 'gradient' || L.type === 'particles');

    if (!fullBleed) {
      const cx = (L.x != null ? L.x : 0.5) * W + driftX + (pm ? pm.dx : 0);
      const cy = (L.y != null ? L.y : 0.5) * H + driftY + (pm ? pm.dy : 0);
      ctx.translate(cx, cy);
      if (rot) ctx.rotate(rot);
      if (scale !== 1) ctx.scale(scale, scale);
    }

    switch (L.type) {
      case 'gradient':  drawGradient(ctx, W, H, L, t); break;
      case 'particles': drawParticles(ctx, W, H, L, t); break;
      case 'shape':     drawShape(ctx, W, H, L, t); break;
      case 'text':      drawText(ctx, W, H, L, t); break;
      case 'clock':     drawClock(ctx, W, H, L, t); break;
      case 'image':     drawImageLayer(ctx, W, H, L, t); break;
      case 'video':     drawVideoLayer(ctx, W, H, L, t); break;
      case 'lyrics':    drawLyrics(ctx, W, H, L, t, bg); break;
    }
    ctx.restore();
  }

  // ── Gradient ──────────────────────────────────────────────────────────────

  function drawGradient(ctx, W, H, L, t) {
    const anim = L.animate || { mode: 'none' };
    const mode = anim.mode || 'none';
    const sp = anim.speed || 0.4;
    const baseStops = (L.stops && L.stops.length) ? L.stops.slice()
      : [{ pos: 0, color: '#1a237e' }, { pos: 1, color: '#0d47a1' }];

    // ── "mesh" / "aurora": moving blended radial blobs (GPU-friendly) ─────────
    if (mode === 'mesh' || mode === 'aurora') {
      ctx.fillStyle = baseStops[0].color || '#000';
      ctx.fillRect(0, 0, W, H);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      const n = baseStops.length;
      for (let i = 0; i < n; i++) {
        const ph = t * sp + i * (Math.PI * 2 / n);
        const cx = W * (0.5 + 0.32 * Math.sin(ph * 0.8 + i));
        const cy = H * (0.5 + 0.32 * Math.cos(ph * 0.6 + i * 1.3));
        const r = Math.max(W, H) * (0.45 + 0.18 * Math.sin(ph * 1.1));
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        g.addColorStop(0, baseStops[i].color);
        g.addColorStop(1, withAlpha(baseStops[i].color, 0));
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, W, H);
      }
      ctx.restore();
      return;
    }

    // ── colour-cycle (shift hues through the stop list) ───────────────────────
    let stops = baseStops;
    if (mode === 'cycle' && stops.length > 1) {
      const shift = (t * sp) % 1;
      stops = stops.map((s, i) => {
        const j = (i + 1) % stops.length;
        return { pos: s.pos, color: mixHex(s.color, stops[j].color, shift) };
      });
    }
    // ── flow (scroll stop positions) ──────────────────────────────────────────
    if (mode === 'flow' && stops.length > 1) {
      const off = (t * sp) % 1;
      stops = stops.map(s => ({ pos: (s.pos + off) % 1, color: s.color }))
                   .sort((a, b) => a.pos - b.pos);
    }

    let angle = L.angle || 0;
    if (mode === 'rotate') angle = (angle + t * sp * 60) % 360;
    if (mode === 'waves')  angle = (L.angle || 0) + Math.sin(t * sp * Math.PI) * 35;

    let grad;
    if (L.gradientType === 'radial' || mode === 'pulse') {
      const r = Math.max(W, H) * ((mode === 'shift' || mode === 'pulse')
        ? 0.55 + 0.18 * Math.sin(t * sp * Math.PI) : 0.62);
      grad = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, r);
    } else if (L.gradientType === 'conic' && ctx.createConicGradient) {
      grad = ctx.createConicGradient(angle * Math.PI / 180, W / 2, H / 2);
    } else {
      const rad = angle * Math.PI / 180;
      const dx = Math.cos(rad) * W / 2, dy = Math.sin(rad) * H / 2;
      grad = ctx.createLinearGradient(W / 2 - dx, H / 2 - dy, W / 2 + dx, H / 2 + dy);
    }
    stops.forEach(s => { try { grad.addColorStop(clamp(s.pos, 0, 1), s.color); } catch (e) {} });
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);
  }

  // ── Gradient presets (20+) ──────────────────────────────────────────────────
  // Each: { type, angle, mode, speed, colors:[...] }
  const GRADIENT_PRESETS = {
    'Ocean':        { type:'linear', angle:135, mode:'mesh',  speed:0.25, colors:['#0d3b66','#1b6ca8','#3aafd6','#9ad9e8'] },
    'Fum':          { type:'linear', angle:90,  mode:'mesh',  speed:0.18, colors:['#1a1a1a','#3a3a40','#5a5a66','#2a2a30'] },
    'Apus':         { type:'linear', angle:120, mode:'flow',  speed:0.3,  colors:['#ff7e5f','#feb47b','#ffcb80','#ff5e62'] },
    'Aurora':       { type:'linear', angle:90,  mode:'aurora',speed:0.3,  colors:['#001b2e','#13ce66','#1fa2ff','#a44cff'] },
    'Lavă':         { type:'linear', angle:90,  mode:'mesh',  speed:0.4,  colors:['#200122','#6f0000','#ff512f','#f09819'] },
    'Pădure':       { type:'linear', angle:135, mode:'flow',  speed:0.2,  colors:['#0b3d2e','#1e6f43','#3cb371','#aaf0c0'] },
    'Regal':        { type:'linear', angle:135, mode:'cycle', speed:0.2,  colors:['#1a237e','#4a148c','#6a1b9a','#283593'] },
    'Foc':          { type:'radial', angle:90,  mode:'pulse', speed:0.5,  colors:['#fff3b0','#ffae00','#ff5400','#7a1500'] },
    'Gheață':       { type:'linear', angle:135, mode:'flow',  speed:0.2,  colors:['#e0f7ff','#a0e9ff','#5bc0eb','#2a6f97'] },
    'Nebuloasă':    { type:'linear', angle:120, mode:'aurora',speed:0.25, colors:['#0d0221','#3a0ca3','#7209b7','#f72585'] },
    'Curcubeu':     { type:'linear', angle:90,  mode:'cycle', speed:0.4,  colors:['#ff0040','#ff8c00','#ffe000','#00d084','#0099ff','#8a2be2'] },
    'Auriu':        { type:'linear', angle:135, mode:'flow',  speed:0.25, colors:['#3a2c00','#a67c00','#ffd700','#fff3b0'] },
    'Miezul nopții':{ type:'linear', angle:135, mode:'mesh',  speed:0.15, colors:['#020111','#0a1a3f','#16336b','#3a4f7a'] },
    'Smarald':      { type:'linear', angle:135, mode:'flow',  speed:0.22, colors:['#02231c','#0b6e4f','#08a045','#9be564'] },
    'Zori':         { type:'linear', angle:90,  mode:'flow',  speed:0.2,  colors:['#2c3e50','#fd746c','#ff9068','#ffd194'] },
    'Furtună':      { type:'linear', angle:120, mode:'mesh',  speed:0.35, colors:['#0f2027','#203a43','#2c5364','#5a6f7a'] },
    'Neon':         { type:'linear', angle:135, mode:'cycle', speed:0.5,  colors:['#ff00cc','#3333ff','#00ffcc','#ff00cc'] },
    'Pastel':       { type:'linear', angle:135, mode:'flow',  speed:0.15, colors:['#ffd3e0','#d3f8e2','#e4c1f9','#a9def9'] },
    'Trandafir':    { type:'linear', angle:120, mode:'flow',  speed:0.2,  colors:['#3d0814','#a4133c','#ff4d6d','#ffb3c1'] },
    'Cer senin':    { type:'linear', angle:90,  mode:'flow',  speed:0.18, colors:['#0b486b','#2a79b6','#74b9e0','#cfeefb'] },
    'Mentă':        { type:'linear', angle:135, mode:'flow',  speed:0.2,  colors:['#0f3d3e','#1f8a70','#5fd6b0','#d6fff2'] },
    'Strugure':     { type:'linear', angle:135, mode:'cycle', speed:0.25, colors:['#2b0a3d','#5a189a','#9d4edd','#e0aaff'] },
    'Cărbune & Aur':{ type:'linear', angle:120, mode:'flow',  speed:0.22, colors:['#101010','#2a2a2a','#5a4a10','#d4af37'] },
    'Divin':        { type:'radial', angle:90,  mode:'pulse', speed:0.3,  colors:['#fff8e1','#ffe082','#ffb300','#4e342e'] },
    'Cosmos':       { type:'linear', angle:120, mode:'aurora',speed:0.22, colors:['#000000','#1b1b3a','#5b2a86','#b14aed'] },
    'Tropical':     { type:'linear', angle:135, mode:'flow',  speed:0.25, colors:['#00b09b','#96c93d','#f7ff00','#ff6a00'] },
    'Coral':        { type:'linear', angle:120, mode:'flow',  speed:0.22, colors:['#ff6f61','#ff9a8b','#ffd1c1','#ffe9e3'] },
    'Indigo':       { type:'linear', angle:135, mode:'mesh',  speed:0.2,  colors:['#0b1a3a','#1a2a6c','#3a4ea8','#6a7fd8'] },
    'Toamnă':       { type:'linear', angle:120, mode:'flow',  speed:0.2,  colors:['#3a1c00','#8a3b00','#d35400','#f0a04b'] },
    'Iarnă':        { type:'linear', angle:135, mode:'flow',  speed:0.15, colors:['#0b2545','#13315c','#8da9c4','#eef4ed'] },
    'Lime':         { type:'linear', angle:135, mode:'flow',  speed:0.22, colors:['#0a2e0a','#2e7d32','#7cb342','#cddc39'] },
    'Magenta':      { type:'linear', angle:135, mode:'cycle', speed:0.3,  colors:['#3a0033','#a4008a','#ff2db0','#ff9ee0'] },
    'Cobalt':       { type:'linear', angle:135, mode:'mesh',  speed:0.25, colors:['#001f54','#034078','#1282a2','#5fa8d3'] },
    'Cireș':        { type:'linear', angle:120, mode:'flow',  speed:0.2,  colors:['#2b0a0a','#7a1f2b','#c9184a','#ff8fa3'] },
    'Mango':        { type:'linear', angle:120, mode:'flow',  speed:0.24, colors:['#7a2e00','#e85d04','#ffba08','#fff2b2'] },
    'Petrol':       { type:'linear', angle:135, mode:'mesh',  speed:0.2,  colors:['#012a36','#024450','#02788e','#27a4b8'] },
    'Lila vis':     { type:'linear', angle:135, mode:'aurora',speed:0.22, colors:['#1a0b2e','#4b1d8f','#9b5de5','#f1c0ff'] },
    'Verde smarald':{ type:'radial', angle:90,  mode:'pulse', speed:0.3,  colors:['#d8f3dc','#74c69d','#2d6a4f','#081c15'] },
    'Soare':        { type:'radial', angle:90,  mode:'pulse', speed:0.4,  colors:['#fff7d6','#ffd60a','#ff9e00','#ff5400'] },
    'Galaxie':      { type:'linear', angle:120, mode:'aurora',speed:0.28, colors:['#03001e','#7303c0','#ec38bc','#fdeff9'] },
  };

  function applyGradientPreset(L, name) {
    const p = GRADIENT_PRESETS[name];
    if (!p) return;
    L.gradientType = p.type;
    L.angle = p.angle;
    L.stops = p.colors.map((c, i) => ({ pos: i / (p.colors.length - 1), color: c }));
    L.animate = { mode: p.mode, speed: p.speed };
    L.preset = name;
  }

  // ── Particles (sparks / snow / fog / bokeh / embers) ────────────────────────

  function ensureParticles(L, W, H) {
    const count = L.count || 100;
    if (!L._p || L._p.length !== count || L._pw !== W || L._ph !== H) {
      L._p = [];
      L._pw = W; L._ph = H;
      for (let i = 0; i < count; i++) L._p.push(spawnParticle(L, W, H, true));
    }
    return L._p;
  }

  function spawnParticle(L, W, H, initial) {
    const r = Math.random;
    return {
      x: r() * W,
      y: initial ? r() * H : (L.preset === 'snow' || L.preset === 'fog' ? -10 : H + 10),
      vx: (r() - 0.5),
      vy: (r() - 0.5),
      sz: (0.6 + r() * 1.8) * (L.size || 1),
      life: r(),
      seed: r() * 1000,
    };
  }

  function drawParticles(ctx, W, H, L, t) {
    const ps = ensureParticles(L, W, H);
    // Audio-reactive: bass surges speed it up (music-visualiser burst feel).
    let sp = (L.speed || 1);
    if (L.react && L.react.enabled) {
      const v = (_audio[L.react.src] != null ? _audio[L.react.src] : _audio.bass) || 0;
      sp *= 1 + (L.react.amount != null ? L.react.amount : 0.8) * v * 2;
    }
    const preset = L.preset || 'sparks';
    ctx.save();
    for (let i = 0; i < ps.length; i++) {
      const p = ps[i];
      if (preset === 'snow') {
        p.y += (0.4 + p.sz * 0.4) * sp;
        p.x += Math.sin((t + p.seed) * 0.8) * 0.6 * sp;
        if (p.y > H + 10) { p.y = -10; p.x = Math.random() * W; }
        ctx.globalAlpha = 0.85;
        ctx.fillStyle = L.color || '#ffffff';
        ctx.beginPath(); ctx.arc(p.x, p.y, p.sz * 2.2, 0, 7); ctx.fill();
      } else if (preset === 'fog') {
        p.x += (0.2 + p.sz * 0.1) * sp;
        if (p.x > W + 120) p.x = -120;
        const r = 120 * p.sz;
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r);
        g.addColorStop(0, withAlpha(L.color || '#ffffff', 0.06));
        g.addColorStop(1, withAlpha(L.color || '#ffffff', 0));
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, 7); ctx.fill();
      } else if (preset === 'embers' || preset === 'sparks') {
        p.y -= (0.6 + p.sz) * sp;
        p.x += Math.sin((t + p.seed) * 1.5) * 0.8;
        p.life -= 0.004 * sp;
        if (p.y < -10 || p.life <= 0) { p.y = H + 10; p.x = Math.random() * W; p.life = 1; }
        const col = mixHex(L.color || '#ffd27f', L.color2 || '#ff7043', 1 - p.life);
        ctx.globalAlpha = clamp(p.life, 0, 1) * (preset === 'sparks' ? 1 : 0.9);
        ctx.fillStyle = col;
        ctx.shadowColor = col; ctx.shadowBlur = 8 * p.sz;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.sz * (preset === 'sparks' ? 1.4 : 2), 0, 7); ctx.fill();
      } else if (preset === 'rain') {
        p.y += (10 + p.sz * 4) * sp;
        p.x += 1.2 * sp;                       // slight wind slant
        if (p.y > H + 20) { p.y = -20; p.x = Math.random() * W; }
        ctx.globalAlpha = 0.45;
        ctx.strokeStyle = L.color || '#9ec5ff';
        ctx.lineWidth = Math.max(1, p.sz);
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x - 2 * sp, p.y - (12 + p.sz * 6));
        ctx.stroke();
      } else if (preset === 'stars') {
        const tw = (Math.sin((t * 2 + p.seed) * 1.3) + 1) / 2;   // twinkle
        ctx.globalAlpha = 0.25 + tw * 0.75;
        ctx.fillStyle = L.color || '#ffffff';
        ctx.beginPath(); ctx.arc(p.x, p.y, Math.max(0.6, p.sz * 0.9), 0, 7); ctx.fill();
      } else if (preset === 'ocean') {
        p.y -= (0.5 + p.sz * 0.5) * sp;                          // bubbles rise
        p.x += Math.sin((t + p.seed) * 0.6) * 0.8;
        if (p.y < -10) { p.y = H + 10; p.x = Math.random() * W; }
        ctx.globalAlpha = 0.18;
        ctx.strokeStyle = L.color || '#7fd4ff';
        ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.sz * 6, 0, 7); ctx.stroke();
      } else { // bokeh
        const a = (Math.sin((t + p.seed) * 0.5) + 1) / 2;
        ctx.globalAlpha = 0.10 + a * 0.18;
        ctx.fillStyle = L.color || '#ffffff';
        ctx.beginPath(); ctx.arc(p.x, p.y, p.sz * 9, 0, 7); ctx.fill();
      }
    }
    ctx.restore();
  }

  function withAlpha(hex, a) {
    const c = hexToRgb(hex);
    return `rgba(${c.r},${c.g},${c.b},${a})`;
  }

  // ── Shape ───────────────────────────────────────────────────────────────────

  function shapeFill(ctx, L, w, h) {
    if (L.fillType === 'none') return null;
    if (L.fillType === 'gradient') {
      const rad = (L.gradAngle || 0) * Math.PI / 180;
      const dx = Math.cos(rad) * w / 2, dy = Math.sin(rad) * h / 2;
      const g = ctx.createLinearGradient(-dx, -dy, dx, dy);
      g.addColorStop(0, L.gradFrom || '#fff');
      g.addColorStop(1, L.gradTo || '#000');
      return g;
    }
    return L.color || '#5294e2';
  }

  // ── Shape path builders (origin-centred, within [-w/2,w/2]×[-h/2,h/2]) ───────

  function polyPath(ctx, w, h, n, rot) {
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const a = rot + i * 2 * Math.PI / n;
      const x = Math.cos(a) * w / 2, y = Math.sin(a) * h / 2;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
  }
  function starPath(ctx, w, h, points, inner) {
    ctx.beginPath();
    for (let i = 0; i < points * 2; i++) {
      const r = (i % 2 === 0) ? 1 : inner;
      const a = -Math.PI / 2 + i * Math.PI / points;
      const x = Math.cos(a) * (w / 2) * r, y = Math.sin(a) * (h / 2) * r;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
  }

  const EVENODD = { ring: 1, crescent: 1, fish: 0 };

  const SHAPE_BUILDERS = {
    rect:    (c, w, h, L) => roundRectPath(c, -w/2, -h/2, w, h, L.radius || 0),
    rounded: (c, w, h)    => roundRectPath(c, -w/2, -h/2, w, h, Math.min(w, h) * 0.18),
    circle:  (c, w, h)    => { c.beginPath(); c.ellipse(0, 0, w/2, h/2, 0, 0, 7); },
    triangle:(c, w, h)    => { c.beginPath(); c.moveTo(0,-h/2); c.lineTo(w/2,h/2); c.lineTo(-w/2,h/2); c.closePath(); },
    diamond: (c, w, h)    => { c.beginPath(); c.moveTo(0,-h/2); c.lineTo(w/2,0); c.lineTo(0,h/2); c.lineTo(-w/2,0); c.closePath(); },
    pentagon:(c, w, h)    => polyPath(c, w, h, 5, -Math.PI/2),
    hexagon: (c, w, h)    => polyPath(c, w, h, 6, -Math.PI/2),
    octagon: (c, w, h)    => polyPath(c, w, h, 8, -Math.PI/8),
    star:    (c, w, h)    => starPath(c, w, h, 5, 0.42),
    star6:   (c, w, h)    => starPath(c, w, h, 6, 0.55),
    burst:   (c, w, h)    => starPath(c, w, h, 12, 0.7),
    sparkle: (c, w, h)    => starPath(c, w, h, 4, 0.28),
    plus:    (c, w, h)    => { const a=w/3,b=h/3; c.beginPath();
      c.moveTo(-a/1,-h/2); c.lineTo(a/1,-h/2); c.lineTo(a/1,-b/1); c.lineTo(w/2,-b/1);
      c.lineTo(w/2,b/1); c.lineTo(a/1,b/1); c.lineTo(a/1,h/2); c.lineTo(-a/1,h/2);
      c.lineTo(-a/1,b/1); c.lineTo(-w/2,b/1); c.lineTo(-w/2,-b/1); c.lineTo(-a/1,-b/1); c.closePath(); },
    cross:   (c, w, h)    => { const aw=w*0.30, top=h*0.16; c.beginPath();
      c.moveTo(-aw/2,-h/2); c.lineTo(aw/2,-h/2); c.lineTo(aw/2,-h/2+top); c.lineTo(w/2,-h/2+top);
      c.lineTo(w/2,-h/2+top+aw); c.lineTo(aw/2,-h/2+top+aw); c.lineTo(aw/2,h/2); c.lineTo(-aw/2,h/2);
      c.lineTo(-aw/2,-h/2+top+aw); c.lineTo(-w/2,-h/2+top+aw); c.lineTo(-w/2,-h/2+top); c.lineTo(-aw/2,-h/2+top); c.closePath(); },
    heart:   (c, w, h)    => { c.beginPath(); const x=w/2, y=h/2;
      c.moveTo(0, y*0.85);
      c.bezierCurveTo(x*1.4, y*0.1, x*0.7, -y*0.9, 0, -y*0.25);
      c.bezierCurveTo(-x*0.7, -y*0.9, -x*1.4, y*0.1, 0, y*0.85); c.closePath(); },
    arrow:   (c, w, h)    => { const sh=h*0.5, nw=w*0.45; c.beginPath();
      c.moveTo(-w/2,-sh/2); c.lineTo(w/2-nw,-sh/2); c.lineTo(w/2-nw,-h/2); c.lineTo(w/2,0);
      c.lineTo(w/2-nw,h/2); c.lineTo(w/2-nw,sh/2); c.lineTo(-w/2,sh/2); c.closePath(); },
    chevron: (c, w, h)    => { const t=w*0.32; c.beginPath();
      c.moveTo(-w/2,-h/2); c.lineTo(-w/2+t,-h/2); c.lineTo(w/2,0); c.lineTo(-w/2+t,h/2);
      c.lineTo(-w/2,h/2); c.lineTo(w/2-t,0); c.closePath(); },
    ring:    (c, w, h)    => { c.beginPath(); c.ellipse(0,0,w/2,h/2,0,0,7);
      c.ellipse(0,0,w/2*0.6,h/2*0.6,0,0,7); },
    crescent:(c, w, h)    => { c.beginPath(); c.ellipse(0,0,w/2,h/2,0,0,7);
      c.ellipse(w*0.18,0,w/2*0.82,h/2*0.82,0,0,7); },
    drop:    (c, w, h)    => { c.beginPath(); c.moveTo(0,-h/2);
      c.bezierCurveTo(w/2,-h*0.1, w/2,h/2, 0,h/2);
      c.bezierCurveTo(-w/2,h/2, -w/2,-h*0.1, 0,-h/2); c.closePath(); },
    shield:  (c, w, h)    => { c.beginPath(); c.moveTo(-w/2,-h/2); c.lineTo(w/2,-h/2);
      c.lineTo(w/2,h*0.1); c.quadraticCurveTo(w/2,h*0.42, 0,h/2);
      c.quadraticCurveTo(-w/2,h*0.42, -w/2,h*0.1); c.closePath(); },
    flame:   (c, w, h)    => { c.beginPath(); c.moveTo(0,-h/2);
      c.bezierCurveTo(w*0.55,-h*0.1, w*0.2,h*0.2, w*0.28,h*0.34);
      c.bezierCurveTo(w*0.34,h*0.5, 0,h*0.52, 0,h/2);
      c.bezierCurveTo(0,h*0.52, -w*0.34,h*0.5, -w*0.28,h*0.34);
      c.bezierCurveTo(-w*0.2,h*0.2, -w*0.55,-h*0.1, 0,-h/2); c.closePath(); },
    fish:    (c, w, h)    => { c.beginPath(); c.moveTo(-w*0.30,0);
      c.quadraticCurveTo(0,-h*0.6, w/2,0); c.quadraticCurveTo(0,h*0.6, -w*0.30,0);
      c.moveTo(-w*0.30,0); c.lineTo(-w/2,-h*0.34); c.moveTo(-w*0.30,0); c.lineTo(-w/2,h*0.34); },
    crown:   (c, w, h)    => { c.beginPath(); c.moveTo(-w/2,h/2); c.lineTo(-w/2,-h*0.2);
      c.lineTo(-w*0.25,h*0.05); c.lineTo(0,-h/2); c.lineTo(w*0.25,h*0.05); c.lineTo(w/2,-h*0.2);
      c.lineTo(w/2,h/2); c.closePath(); },
    lightning:(c, w, h)   => { c.beginPath(); c.moveTo(w*0.1,-h/2); c.lineTo(-w*0.35,h*0.1);
      c.lineTo(0,h*0.1); c.lineTo(-w*0.1,h/2); c.lineTo(w*0.4,-h*0.12); c.lineTo(w*0.05,-h*0.12); c.closePath(); },
    parallelogram:(c,w,h) => { const s=w*0.22; c.beginPath(); c.moveTo(-w/2+s,-h/2);
      c.lineTo(w/2,-h/2); c.lineTo(w/2-s,h/2); c.lineTo(-w/2,h/2); c.closePath(); },
    trapezoid:(c, w, h)   => { const s=w*0.2; c.beginPath(); c.moveTo(-w/2+s,-h/2);
      c.lineTo(w/2-s,-h/2); c.lineTo(w/2,h/2); c.lineTo(-w/2,h/2); c.closePath(); },
    semicircle:(c, w, h)  => { c.beginPath(); c.moveTo(-w/2,h/2); c.lineTo(w/2,h/2);
      c.arc(0,h/2,w/2,0,Math.PI,true); c.closePath(); },
    cloud:   (c, w, h)    => { c.beginPath();
      c.arc(-w*0.22,h*0.05,h*0.32,0,7); c.arc(0,-h*0.12,h*0.40,0,7);
      c.arc(w*0.24,h*0.05,h*0.34,0,7); c.rect(-w*0.42,h*0.02,w*0.84,h*0.34); },
    pin:     (c, w, h)    => { c.beginPath(); c.arc(0,-h*0.18,w*0.42,Math.PI*0.85,Math.PI*0.15);
      c.lineTo(0,h/2); c.closePath(); },
  };

  const SHAPE_LIST = Object.keys(SHAPE_BUILDERS).concat(['line']);

  // Draw a small shape icon centred in a boxW×boxH area (for the editor picker).
  function drawShapeIcon(ctx, shape, boxW, boxH, color) {
    const w = boxW * 0.64, h = boxH * 0.64;
    ctx.save();
    ctx.translate(boxW / 2, boxH / 2);
    ctx.fillStyle = color || '#5294e2';
    ctx.strokeStyle = '#9ec5ff';
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    if (shape === 'line') {
      ctx.lineWidth = Math.max(2, h * 0.18);
      ctx.strokeStyle = color || '#5294e2';
      ctx.beginPath(); ctx.moveTo(-w / 2, 0); ctx.lineTo(w / 2, 0); ctx.stroke();
      ctx.restore(); return;
    }
    const builder = SHAPE_BUILDERS[shape] || SHAPE_BUILDERS.rect;
    builder(ctx, w, h, { radius: w * 0.15, points: 5 });
    ctx.fill(EVENODD[shape] ? 'evenodd' : 'nonzero');
    ctx.restore();
  }

  function drawShape(ctx, W, H, L) {
    const w = (L.w || 0.3) * W, h = (L.h || 0.3) * H;

    if (L.shape === 'line') {
      ctx.lineWidth = (L.strokeWidth || 6);
      ctx.strokeStyle = L.color || '#fff';
      ctx.beginPath(); ctx.moveTo(-w / 2, 0); ctx.lineTo(w / 2, 0); ctx.stroke();
      return;
    }

    const builder = SHAPE_BUILDERS[L.shape] || SHAPE_BUILDERS.rect;
    const fill = shapeFill(ctx, L, w, h);
    ctx.fillStyle = fill || 'transparent';
    ctx.strokeStyle = L.strokeColor || '#fff';
    ctx.lineWidth = (L.strokeWidth || 0);
    ctx.lineJoin = 'round';

    builder(ctx, w, h, L);
    if (fill) ctx.fill(EVENODD[L.shape] ? 'evenodd' : 'nonzero');
    if (L.strokeWidth) ctx.stroke();
  }

  // ── Text ──────────────────────────────────────────────────────────────────

  function buildFont(L, sizePx) {
    return `${L.italic ? 'italic ' : ''}${L.bold ? '700 ' : '400 '}${sizePx}px "${L.font || 'Montserrat'}", Arial, sans-serif`;
  }

  function textFill(ctx, L, sizePx, t) {
    if (L.colorType === 'gradient' || L.colorType === 'animated') {
      let from = L.gradFrom || '#fff', to = L.gradTo || '#9ec5ff';
      if (L.colorType === 'animated') {
        const k = osc(t, 0.4);
        from = mixHex(L.gradFrom || '#fff', L.gradTo || '#9ec5ff', k);
        to   = mixHex(L.gradTo || '#9ec5ff', L.gradFrom || '#fff', k);
      }
      const g = ctx.createLinearGradient(0, -sizePx, 0, sizePx);
      g.addColorStop(0, from); g.addColorStop(1, to);
      return g;
    }
    return L.color || '#ffffff';
  }

  function wrapLines(ctx, text, maxW) {
    const out = [];
    String(text).split('\n').forEach(raw => {
      if (!raw.trim()) { out.push(''); return; }
      const words = raw.split(/\s+/);
      let line = '';
      words.forEach(word => {
        const test = line ? line + ' ' + word : word;
        if (ctx.measureText(test).width > maxW && line) { out.push(line); line = word; }
        else line = test;
      });
      if (line) out.push(line);
    });
    return out;
  }

  function drawText(ctx, W, H, L, t) {
    const sizePx = (L.size || 96);
    let str = L.text || '';
    // Word-by-word reveal (dynamic presentations): show only the first
    // ceil(words * _reveal) words of this layer when flagged `reveal:true`.
    if (L.reveal && _reveal < 1) {
      const words = String(str).split(/(\s+)/);   // keep separators
      const wordIdx = words.filter(w => w.trim()).length;
      const show = Math.max(0, Math.ceil(wordIdx * _reveal));
      let seen = 0, out = '';
      for (const tok of words) {
        if (tok.trim()) { if (seen >= show) break; seen++; }
        out += tok;
      }
      str = out;
    }
    if (L.uppercase) str = str.toUpperCase();
    const maxW = (L.w || 0.7) * W;
    ctx.textAlign = L.align || 'center';
    ctx.textBaseline = 'middle';

    // ── Echo: big faint copy behind (concert "ghost lyric" look) ──────────────
    if (L.echo && L.echo.enabled) {
      ctx.save();
      const es = sizePx * (L.echo.scale || 2.4);
      ctx.font = buildFont(L, es);
      ctx.globalAlpha *= (L.echo.opacity != null ? L.echo.opacity : 0.14);
      ctx.fillStyle = (L.colorType === 'solid') ? (L.color || '#fff') : '#ffffff';
      if (L.echo.blur) { try { ctx.filter = `blur(${L.echo.blur}px)`; } catch (e) {} }
      const elines = wrapLines(ctx, str, maxW * 1.6);
      const elh = es * (L.lineHeight || 1.15);
      const ey0 = -((elines.length - 1) * elh) / 2;
      elines.forEach((ln, i) => ctx.fillText(ln, 0, ey0 + i * elh));
      ctx.restore();
    }

    ctx.font = buildFont(L, sizePx);
    ctx.fillStyle = textFill(ctx, L, sizePx, t);
    const lines = wrapLines(ctx, str, maxW);
    const lh = sizePx * (L.lineHeight || 1.15);
    const y0 = -((lines.length - 1) * lh) / 2;
    lines.forEach((ln, i) => {
      if (L.letterSpacing) ctx.letterSpacing = (L.letterSpacing + 'px');
      ctx.fillText(ln, 0, y0 + i * lh);
    });
  }

  // ── Clock / timer ───────────────────────────────────────────────────────────
  // Reuses the text-layer font/colour machinery; gets position, transitions and
  // animations for free from drawLayer. `t` is ms elapsed since the bg appeared,
  // so stopwatch counts up from 0 and countdown counts down from `duration`.
  function _pad2(n) { return (n < 10 ? '0' : '') + n; }

  function clockString(L, t) {
    const mode = L.clockMode || 'clock';
    if (mode === 'stopwatch' || mode === 'countdown') {
      // `t` is already in SECONDS here (render() divides ms by 1000).
      let secs = (mode === 'stopwatch')
        ? Math.floor(t)
        : Math.max(0, Math.ceil((L.duration || 300) - t));
      const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
      return (h > 0 ? h + ':' + _pad2(m) : m) + ':' + _pad2(s);
    }
    const now = new Date();
    if (mode === 'date') {
      try { return now.toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' }); }
      catch (e) { return now.toLocaleDateString(); }
    }
    // clock
    let hh = now.getHours(), ampm = '';
    if (!L.format24) { ampm = hh >= 12 ? ' PM' : ' AM'; hh = hh % 12 || 12; }
    let str = (L.format24 ? _pad2(hh) : hh) + ':' + _pad2(now.getMinutes());
    if (L.showSeconds) str += ':' + _pad2(now.getSeconds());
    return str + ampm;
  }

  function drawClock(ctx, W, H, L, t) {
    let str = clockString(L, t);
    if (L.prefix) str = L.prefix + str;
    if (L.suffix) str = str + L.suffix;
    if (L.uppercase) str = String(str).toUpperCase();
    const sizePx = L.size || 140;
    ctx.textAlign = L.align || 'center';
    ctx.textBaseline = 'middle';
    ctx.font = buildFont(L, sizePx);
    ctx.fillStyle = textFill(ctx, L, sizePx, t);
    if (L.letterSpacing) { try { ctx.letterSpacing = (L.letterSpacing + 'px'); } catch (e) {} }
    ctx.fillText(str, 0, 0);
  }

  // ── Lyrics cascade (current line highlighted, neighbours dimmed) ─────────────

  const DEMO_LYRICS = [
    'Slăvit să fie Domnul', 'În veci nemărginit',
    'O, cât de bun', 'O, cât de bun', 'Isuse, Tu ne-ai dat viață',
    'Și toate Ție-Ți datorăm',
  ];

  function drawLyrics(ctx, W, H, L, t, bg) {
    const live = bg && bg._lyrics;
    const lines = (live && live.lines && live.lines.length) ? live.lines : DEMO_LYRICS;
    let index = (live && typeof live.index === 'number')
      ? live.index : Math.floor(t / 2.5) % lines.length;
    index = clamp(index, 0, lines.length - 1);

    // Smooth scroll toward the current line index
    if (L._scroll == null) L._scroll = index;
    L._scroll += (index - L._scroll) * Math.min(1, (L.scrollSpeed || 8) * 0.016);
    const curr = L._scroll;

    const size = L.size || 64;
    const lineH = size * (L.lineGap || 1.7);
    const half = Math.floor((L.visibleLines || 5) / 2);
    ctx.textAlign = L.align || 'center';
    ctx.textBaseline = 'middle';
    const fontStr = (b, sz) =>
      `${b ? '700 ' : '400 '}${Math.max(8, sz)}px "${L.font || 'Montserrat'}", Arial, sans-serif`;
    const baseAlpha = ctx.globalAlpha;

    for (let off = -half - 1; off <= half + 1; off++) {
      const li = Math.round(curr) + off;
      if (li < 0 || li >= lines.length) continue;
      const dist = Math.abs(li - curr);
      const y = (li - curr) * lineH;
      if (Math.abs(y) > H * 0.62) continue;
      const isCurr = dist < 0.5;
      const fade = clamp(1 - dist / (half + 0.8), 0, 1);
      ctx.save();
      ctx.globalAlpha = baseAlpha * (isCurr ? 1 : fade * (L.dimOpacity != null ? L.dimOpacity : 0.35));
      const sc = isCurr ? (L.hlScale || 1.18) : (1 - dist * 0.05);
      ctx.font = fontStr(L.bold, size * sc);
      ctx.fillStyle = isCurr ? (L.hlColor || L.color || '#fff') : (L.dimColor || '#fff');
      if (isCurr && L.hlGlow) { ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = size * 0.4; }
      let txt = lines[li] || '';
      if (L.uppercase) txt = txt.toUpperCase();
      ctx.fillText(txt, 0, y);
      ctx.restore();
    }
  }

  // ── Image / Video (cover-fit) ───────────────────────────────────────────────

  // Caller supplies a media element via bg._media[L.id] (HTMLImageElement /
  // HTMLVideoElement). The engine never loads files itself (host decides paths).
  function _blitMedia(ctx, W, H, L, el) {
    if (!el) return;
    const iw = el.videoWidth || el.naturalWidth || el.width;
    const ih = el.videoHeight || el.naturalHeight || el.height;
    if (!iw || !ih) return;
    const tw = (L.w || 1) * W, th = (L.h || 1) * H;
    let dw = tw, dh = th;
    if (L.fit === 'contain') {
      const s = Math.min(tw / iw, th / ih); dw = iw * s; dh = ih * s;
    } else if (L.fit !== 'stretch') { // cover
      const s = Math.max(tw / iw, th / ih); dw = iw * s; dh = ih * s;
    }
    ctx.drawImage(el, -dw / 2, -dh / 2, dw, dh);
  }

  function drawImageLayer(ctx, W, H, L) {
    const reg = (drawImageLayer._reg || {});
    _blitMedia(ctx, W, H, L, reg[L.id]);
  }
  function drawVideoLayer(ctx, W, H, L) {
    const reg = (drawVideoLayer._reg || {});
    _blitMedia(ctx, W, H, L, reg[L.id]);
  }

  // Host registers loaded media elements here (editor + display.js).
  function registerMedia(layerId, el, kind) {
    const fn = kind === 'video' ? drawVideoLayer : drawImageLayer;
    fn._reg = fn._reg || {};
    fn._reg[layerId] = el;
  }

  // ── Public API ──────────────────────────────────────────────────────────────

  const BgEngine = {
    uid, defaultBackground, newLayer, render, registerMedia,
    SHAPE_LIST, GRADIENT_PRESETS, applyGradientPreset, drawShapeIcon,
    GRADIENT_MODES: ['none','rotate','shift','cycle','flow','mesh','aurora','waves','pulse'],
    // Live audio reactivity + lyric reveal (set each frame by display.js).
    setAudio(a) { if (a) _audio = { level: a.level || 0, bass: a.bass || 0, mid: a.mid || 0, treble: a.treble || 0 }; },
    setReveal(p) { _reveal = (p == null) ? 1 : Math.max(0, Math.min(1, p)); },
    getAudio() { return _audio; },
    // expose helpers for the editor UI
    _helpers: { hexToRgb, mixHex, clamp },
  };

  global.BgEngine = BgEngine;
  if (typeof module !== 'undefined' && module.exports) module.exports = BgEngine;

})(typeof window !== 'undefined' ? window : globalThis);
