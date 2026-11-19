(function() {
  'use strict';

  const cvPrev = document.getElementById('canvas-prev');
  const cvCurr = document.getElementById('canvas-curr');
  const bgVideo = document.getElementById('bg-video');
  const bgImage = document.getElementById('bg-image');
  const debugEl = document.getElementById('debug-overlay');

  const ctxP = cvPrev.getContext('2d');
  const ctxC = cvCurr.getContext('2d');

  function resize() {
    cvPrev.width = cvCurr.width = window.innerWidth;
    cvPrev.height = cvCurr.height = window.innerHeight;
  }
  window.addEventListener('resize', () => { resize(); renderFrame(ctxC); });

  const state = {
    text: '', lines: [], format: {}, settings: {},
    metadata: {}, isBlack: false,
    tickerText: '', tickerActive: false,
    clockActive: false, timerEnd: null, timerActive: false,
    logoPath: null, projOff: false, frozen: false,
  };

  let transition = { active: false, type: 'fade', duration: 400, start: 0, progress: 1 };
  let tickerX = 0;
  let lastTickTs = 0;

  const tickerSettings = {
    speed: 3, font_size: 22, font_family: 'Arial',
    text_color: '#f9e2af', bg_color: 'rgba(0,0,0,0.85)',
    bar_height: 52, position: 'bottom',
  };

  let tickerAnim = { barY: null, targetY: null, animating: false, barOpacity: 1.0, slideDir: null, animStart: 0, animDur: 400, onDone: null };

  const logoCache = {};
  const gradientAnim = { time: 0, colors: ['#1a237e', '#6a1b9a', '#0d47a1'], speed: 0.5 };

  const dualState = { active: false, original: '', translated: '', layout: {} };

  // ── IPC ─────────────────────────────────────────────────────────────────────
  const { ipcRenderer } = require('electron');
  ipcRenderer.on('render', (_event, msg) => handleMessage(msg));
  window._handleRender = (msg) => handleMessage(msg);

  // ── Message handler ─────────────────────────────────────────────────────────
  function handleMessage(msg) {
    const type = msg.type || msg.cmd;
    if (state.frozen && type !== 'unfreeze' && type !== 'quit') return;

    switch (type) {
      case 'freeze': state.frozen = true; break;
      case 'unfreeze': state.frozen = false; renderFrame(ctxC); break;
      case 'clear_text':
        capturePrev();
        state.text = ''; state.lines = []; state.metadata = {}; state.isBlack = false;
        startTransition(state.settings.transition || 'fade', parseInt(state.settings.transition_duration || 350));
        break;
      case 'show_text':
        if (msg.settings) state.settings = { ...state.settings, ...msg.settings };
        if (msg.metadata) state.metadata = msg.metadata;
        capturePrev();
        state.text = msg.text || ''; state.lines = state.text.split('\n'); state.format = msg.format || {};
        state.isBlack = false; state.projOff = false; dualState.active = false;
        startTransition(msg.transition || state.settings.transition || 'fade', parseInt(msg.transition_duration || state.settings.transition_duration || 400));
        break;
      case 'black':
        capturePrev(); state.isBlack = true; state.text = ''; state.lines = []; dualState.active = false;
        startTransition(state.settings.transition || 'fade', parseInt(state.settings.transition_duration || 350));
        break;
      case 'projector_off':
        capturePrev(); state.projOff = true; state.isBlack = false; state.text = ''; state.lines = [];
        startTransition('fade', 300);
        break;
      case 'settings':
        state.settings = { ...state.settings, ...(msg.settings || {}) };
        applyBackground(state.settings);
        renderFrame(ctxC);
        break;
      case 'ticker':
        state.tickerText = msg.text || ''; state.tickerActive = true;
        tickerX = cvCurr.width;
        if (msg.settings) Object.assign(tickerSettings, msg.settings);
        tickerAnim.barY = null; tickerAnim.animating = false; tickerAnim.barOpacity = 1.0;
        break;
      case 'hide_ticker':
        state.tickerActive = false; state.tickerText = ''; tickerAnim.barY = null; tickerAnim.animating = false;
        renderFrame(ctxC);
        break;
      case 'ticker_advanced':
        state.tickerText = msg.text || ''; state.tickerActive = true;
        tickerX = cvCurr.width;
        if (msg.settings) Object.assign(tickerSettings, msg.settings);
        showTickerWithEffect((msg.settings && msg.settings.ticker_in_effect) || 'slide_up', parseInt(msg.settings && msg.settings.ticker_duration || 400));
        break;
      case 'hide_ticker_effect':
        hideTickerWithEffect((msg.settings && msg.settings.ticker_out_effect) || 'slide_down', parseInt(msg.settings && msg.settings.ticker_duration || 400));
        break;
      case 'timer':
        state.timerEnd = Date.now() + (msg.seconds || 0) * 1000;
        state.timerActive = (msg.seconds || 0) > 0;
        break;
      case 'stop_timer': state.timerActive = false; renderFrame(ctxC); break;
      case 'clock':
        state.clockActive = msg.active !== false;
        if (msg.settings) state.settings.clock = { ...(state.settings.clock || {}), ...msg.settings };
        renderFrame(ctxC);
        break;
      case 'logo':
        state.logoPath = msg.path || null;
        if (state.logoPath && !logoCache[state.logoPath]) {
          const img = new Image();
          img.onload = () => { logoCache[state.logoPath] = img; renderFrame(ctxC); };
          img.onerror = () => { logoCache[state.logoPath] = null; };
          img.src = state.logoPath.startsWith('file://') ? state.logoPath : 'file:///' + state.logoPath.replace(/\\/g, '/');
        } else renderFrame(ctxC);
        break;
      case 'show_dual':
        if (msg.settings) state.settings = { ...state.settings, ...msg.settings };
        capturePrev();
        dualState.active = true; dualState.original = msg.original || ''; dualState.translated = msg.translated || ''; dualState.layout = msg.layout || {};
        state.isBlack = false; state.projOff = false; state.text = ''; state.lines = [];
        startTransition(msg.transition || state.settings.transition || 'fade', parseInt(msg.transition_duration || state.settings.transition_duration || 400));
        break;
    }
  }

  // ── Background ─────────────────────────────────────────────────────────────
  function applyBackground(s) {
    if (!s) return;
    const bg = (s.bg_image || '').trim();
    const bgType = s.bg_type || 'color';
    const bgColor = s.bg_color || '#000000';
    const bgOpacity = parseFloat(s.bg_opacity || 1.0);
    document.body.style.backgroundColor = bgColor;

    function fixPath(p) {
      if (!p) return '';
      return 'file:///' + p.replace(/\\/g, '/').replace(/^file:\/{1,3}/, '');
    }

    if (!bg || bg === 'None' || bg === 'null') {
      if (bgVideo) { bgVideo.pause(); bgVideo.style.display = 'none'; bgVideo.src = ''; bgVideo.srcObject = null; }
      if (bgImage) { bgImage.style.display = 'none'; bgImage.src = ''; }
      return;
    }

    const ext = bg.split('.').pop().toLowerCase();
    const isVideo = ['mp4','mov','avi','mkv','webm','m4v'].includes(ext);

    if (bgType === 'camera') {
      if (bgImage) bgImage.style.display = 'none';
      if (bgVideo) { bgVideo.style.display = 'block'; bgVideo.style.opacity = bgOpacity; bgVideo.srcObject = null; bgVideo.src = ''; }
      const camIdx = parseInt(bg);
      navigator.mediaDevices.enumerateDevices()
        .then(devices => {
          const cameras = devices.filter(d => d.kind === 'videoinput');
          const cam = isNaN(camIdx) ? cameras.find(c => c.deviceId === bg) : cameras[camIdx];
          if (!cam) return Promise.reject('no camera');
          return navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: cam.deviceId } } });
        })
        .then(stream => { if (bgVideo) { bgVideo.srcObject = stream; bgVideo.play().catch(() => {}); } })
        .catch(() => {});
      return;
    }

    if (isVideo) {
      if (bgImage) bgImage.style.display = 'none';
      if (bgVideo) {
        bgVideo.style.display = 'block'; bgVideo.style.opacity = bgOpacity; bgVideo.srcObject = null;
        const fp = fixPath(bg);
        if (!bgVideo.src.includes(bg.replace(/\\/g, '/'))) { bgVideo.src = fp; bgVideo.load(); }
        bgVideo.play().catch(() => setTimeout(() => bgVideo.play().catch(() => {}), 500));
      }
      return;
    }

    if (bgVideo) { bgVideo.pause(); bgVideo.style.display = 'none'; bgVideo.src = ''; bgVideo.srcObject = null; }
    if (bgImage) { bgImage.src = fixPath(bg); bgImage.style.opacity = bgOpacity; bgImage.style.display = 'block'; }
  }

  // ── Transitions ────────────────────────────────────────────────────────────
  function capturePrev() { ctxP.clearRect(0, 0, cvPrev.width, cvPrev.height); ctxP.drawImage(cvCurr, 0, 0); }

  function startTransition(type, duration) {
    transition = { active: true, type, duration, start: performance.now(), progress: 0 };
    requestAnimationFrame(animLoop);
  }

  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

  function animLoop(ts) {
    if (!transition.active) return;
    const elapsed = ts - transition.start;
    transition.progress = Math.min(1, elapsed / Math.max(1, transition.duration));
    const p = easeOutCubic(transition.progress);
    applyTransitionFrame(transition.type, p);
    if (transition.progress < 1) requestAnimationFrame(animLoop);
    else { transition.active = false; ctxP.clearRect(0, 0, cvPrev.width, cvPrev.height); }
  }

  function applyTransitionFrame(type, p) {
    const W = cvCurr.width, H = cvCurr.height;
    switch (type) {
      case 'crossfade':
        ctxC.clearRect(0, 0, W, H); renderFrame(ctxC);
        ctxC.save(); ctxC.globalAlpha = 1 - p; ctxC.drawImage(cvPrev, 0, 0); ctxC.restore();
        break;
      case 'slide_left':
        { const o = Math.round(p * W); ctxC.clearRect(0, 0, W, H);
          ctxC.drawImage(cvPrev, -o, 0); ctxC.save(); ctxC.beginPath(); ctxC.rect(W - o, 0, o, H); ctxC.clip(); renderFrame(ctxC); ctxC.restore(); }
        break;
      case 'zoom_in':
        ctxC.clearRect(0, 0, W, H); ctxC.save(); ctxC.globalAlpha = 1 - p;
        { const sc = 1 + p * 0.12; ctxC.translate(W/2, H/2); ctxC.scale(sc, sc); ctxC.translate(-W/2, -H/2); }
        ctxC.drawImage(cvPrev, 0, 0); ctxC.restore();
        ctxC.save(); ctxC.globalAlpha = p; renderFrame(ctxC); ctxC.restore();
        break;
      default: // fade
        ctxC.clearRect(0, 0, W, H); ctxC.save(); ctxC.globalAlpha = 1 - p; ctxC.drawImage(cvPrev, 0, 0); ctxC.restore();
        ctxC.save(); ctxC.globalAlpha = p; renderFrame(ctxC); ctxC.restore();
    }
  }

  // ── Render frame ────────────────────────────────────────────────────────────
  function renderFrame(ctx) {
    if (!ctx) return;
    const W = ctx.canvas.width, H = ctx.canvas.height;
    const s = state.settings;

    if (state.projOff) {
      ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#333'; ctx.font = 'bold 28px sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('PROJECTOR OFF', W/2, H/2);
      return;
    }

    const bgType = s.bg_type || 'color';
    if (bgType === 'transparent') ctx.clearRect(0, 0, W, H);
    else if (bgType === 'gradient') {
      const c1 = s.bg_grad_c1 || s.bg_color || '#000033';
      const c2 = s.bg_grad_c2 || s.bg_gradient_end || '#000000';
      const dir = s.bg_grad_dir || 'Sus→Jos';
      let grad;
      if (dir === 'Stânga→Dreapta') grad = ctx.createLinearGradient(0, 0, W, 0);
      else if (dir === 'Diagonal') grad = ctx.createLinearGradient(0, 0, W, H);
      else if (dir === 'Radial') grad = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, Math.max(W, H)/2);
      else grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, c1); grad.addColorStop(1, c2);
      ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);
    } else if (bgType === 'color') {
      ctx.fillStyle = s.bg_color || '#000000'; ctx.fillRect(0, 0, W, H);
    } else if (bgType === 'animated_gradient') {
      renderAnimatedGradient(ctx, W, H, s);
    } else {
      ctx.clearRect(0, 0, W, H);
    }

    if (state.isBlack) { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); drawOverlays(ctx, W, H); return; }

    if (dualState.active) drawDualText();
    else if (state.text && state.text.trim().length > 0) drawText(state.text, 1, 0, 0);

    if (s.source === 'bible' || state.metadata?.source === 'bible') {
      const ref = state.metadata?.reference || s.bible_reference || '';
      if (ref) drawReference(ref, s, ctx, W, H);
    }

    drawOverlays(ctx, W, H);
    debugEl.textContent = `${W}×${H} | ${state.lines.length} lines | ${state.isBlack ? 'BLACK' : ''}`;
  }

  // ── Drawing helpers ─────────────────────────────────────────────────────────
  function smartWordWrap(rawLine, maxW, ctx) {
    if (!rawLine || !rawLine.trim()) return [rawLine || ''];
    const tokens = rawLine.match(/\S+/g) || [];
    if (tokens.length <= 1) return [rawLine];
    const full = tokens.join(' ');
    if (ctx.measureText(full).width <= maxW) return [full];
    let bestSplit = null, bestScore = Infinity;
    for (let i = 1; i < tokens.length; i++) {
      const l1 = tokens.slice(0, i).join(' '), l2 = tokens.slice(i).join(' ');
      const w1 = ctx.measureText(l1).width, w2 = ctx.measureText(l2).width;
      if (w1 > maxW) continue;
      let penalty = 0;
      if (i === 1 || tokens.length - i === 1) penalty += 2000;
      if (w2 > maxW) penalty += 1000;
      if (tokens[i-1].endsWith(',')) penalty -= 800;
      const score = Math.abs(w1 - w2) + penalty;
      if (score < bestScore) { bestScore = score; bestSplit = i; }
    }
    if (bestSplit === null) bestSplit = Math.max(1, Math.floor(tokens.length / 2));
    const l1 = tokens.slice(0, bestSplit).join(' ');
    const l2 = tokens.slice(bestSplit).join(' ');
    const result = [l1];
    if (ctx.measureText(l2).width > maxW) result.push(...smartWordWrap(l2, maxW, ctx));
    else result.push(l2);
    return result;
  }

  function drawText(text, opacity, dx, dy) {
    if (!text || opacity <= 0 || !ctxC) return;
    const s = state.settings;
    const W = cvCurr.width, H = cvCurr.height;
    const size = parseInt(s.font_size || 48);
    const bold = s.font_bold === 'true' || s.font_bold === true;
    const italic = s.font_italic === 'true' || s.font_italic === true;
    const family = s.font_family || 'Arial';
    const color = s.text_color || '#ffffff';
    const shadow = s.text_shadow !== 'false';
    const outW = parseInt(s.outline_width || 2);
    const outC = s.outline_color || '#000000';
    const lsp = parseFloat(s.line_spacing || 1.4);
    const rawMargin = parseFloat(s.margin || 0.06);
    const margin = rawMargin < 2 ? Math.round(Math.min(W, H) * rawMargin) : parseInt(rawMargin);
    const maxW = W - margin * 2;
    const maxH = H - margin * 2;

    let currentSize = size, lines = [], lineH = 0, totalH = 0;
    while (currentSize >= 10) {
      ctxC.font = `${italic ? 'italic ' : ''}${bold ? 'bold ' : ''}${currentSize}px "${family}"`;
      lines = [];
      text.split('\n').forEach(rawLine => {
        if (!rawLine.trim()) { lines.push(''); return; }
        smartWordWrap(rawLine, maxW, ctxC).forEach(wl => lines.push(wl));
      });
      lineH = currentSize * lsp;
      totalH = lineH * lines.length;
      const maxLineW = lines.length ? Math.max(...lines.map(l => ctxC.measureText(l).width)) : 0;
      if (totalH <= maxH && maxLineW <= maxW) break;
      currentSize -= 2;
    }

    const valign = s.text_valign || s.valign || 'center';
    let startY;
    if (valign === 'top') startY = margin + currentSize * 0.85;
    else if (valign === 'bottom') startY = H - margin - totalH + currentSize * 0.85;
    else startY = (H - totalH) / 2 + currentSize * 0.85;

    const align = s.text_align || 'center';
    ctxC.textAlign = align === 'left' ? 'left' : align === 'right' ? 'right' : 'center';
    ctxC.textBaseline = 'alphabetic';
    const baseX = align === 'left' ? margin : align === 'right' ? W - margin : W / 2;

    ctxC.save();
    ctxC.globalAlpha = Math.max(0, Math.min(1, opacity));
    if (dx) ctxC.translate(dx, 0);
    if (dy) ctxC.translate(0, dy);

    lines.forEach((line, i) => {
      if (!line) return;
      const y = startY + i * lineH;
      if (outW > 0) {
        ctxC.shadowColor = 'transparent'; ctxC.shadowBlur = 0;
        ctxC.strokeStyle = outC; ctxC.lineWidth = outW * 2; ctxC.lineJoin = 'round';
        ctxC.strokeText(line, baseX, y);
      }
      if (shadow) {
        ctxC.shadowColor = 'rgba(0,0,0,0.85)'; ctxC.shadowBlur = 8;
        ctxC.shadowOffsetX = 3; ctxC.shadowOffsetY = 3;
      } else { ctxC.shadowColor = 'transparent'; ctxC.shadowBlur = 0; ctxC.shadowOffsetX = 0; ctxC.shadowOffsetY = 0; }
      ctxC.fillStyle = color;
      ctxC.fillText(line, baseX, y);
    });
    ctxC.restore();
  }

  function drawReference(ref, s, ctx, W, H) {
    if (!ref || !ref.trim()) return;
    const family = s.font_family || 'Arial';
    const refSize = parseInt(s.ref_font_size || 24);
    const refColor = s.ref_color || '#aaaaaa';
    const rawMargin = parseFloat(s.margin || 0.06);
    const margin = rawMargin < 2 ? Math.round(Math.min(W, H) * rawMargin) : parseInt(rawMargin);
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.8)'; ctx.shadowBlur = 6; ctx.shadowOffsetX = 2; ctx.shadowOffsetY = 2;
    ctx.font = `${refSize}px "${family}"`;
    ctx.fillStyle = refColor;
    ctx.textAlign = 'right'; ctx.textBaseline = 'bottom';
    ctx.fillText(ref, W - margin, H - margin);
    ctx.restore();
  }

  function drawOverlays(ctx, W, H) {
    if (state.tickerActive && state.tickerText) drawTicker(ctx, W, H);
    if (state.clockActive) drawClock(ctx, W, H);
    if (state.timerActive) drawTimer(ctx, W, H);
    if (state.logoPath) drawLogo(ctx, W, H);
  }

  function drawTicker(ctx, W, H) {
    const ts = tickerSettings;
    const barH = parseInt(ts.bar_height) || Math.round(H * 0.08);
    const pos = ts.position || 'bottom';
    const finalY = pos === 'top' ? 0 : H - barH;
    const y = (tickerAnim.barY !== null) ? Math.round(tickerAnim.barY) : finalY;
    const bgCol = ts.bg_color || 'rgba(0,0,0,0.75)';
    const txtCol = ts.text_color || '#ffdd44';
    ctx.fillStyle = bgCol;
    ctx.fillRect(0, y, W, barH);
    ctx.save();
    ctx.strokeStyle = '#cba6f7'; ctx.lineWidth = 2;
    const lineY = pos === 'top' ? y + barH : y;
    ctx.beginPath(); ctx.moveTo(0, lineY); ctx.lineTo(W, lineY); ctx.stroke();
    ctx.restore();
    const fontSize = parseInt(ts.font_size) || Math.round(barH * 0.55);
    const fontFamily = ts.font_family || 'Arial, sans-serif';
    ctx.font = `bold ${fontSize}px "${fontFamily}"`;
    ctx.fillStyle = txtCol;
    ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 4;
    ctx.beginPath(); ctx.rect(0, y, W, barH); ctx.clip();
    ctx.fillText(state.tickerText, tickerX, y + barH / 2);
    ctx.restore();
  }

  function drawClock(ctx, W, H) {
    const clk = state.settings.clock || {};
    const fontSize = parseInt(clk.font_size || Math.round(H * 0.035));
    const fontFamily = clk.font_family || 'Consolas, monospace';
    const color = clk.color || '#ffffff';
    const position = clk.position || 'top_right';
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const sec = String(now.getSeconds()).padStart(2, '0');
    const timeStr = clk.show_seconds !== false ? `${h}:${m}:${sec}` : `${h}:${m}`;
    ctx.save();
    ctx.font = `bold ${fontSize}px ${fontFamily}`;
    const textW = ctx.measureText(timeStr).width;
    const pad = 10;
    let x, y;
    if (position === 'top_left') { x = pad; y = pad + fontSize; }
    else if (position === 'top_center') { x = (W - textW) / 2; y = pad + fontSize; }
    else if (position === 'bottom_right') { x = W - textW - pad; y = H - pad; }
    else if (position === 'bottom_left') { x = pad; y = H - pad; }
    else if (position === 'bottom_center') { x = (W - textW) / 2; y = H - pad; }
    else { x = W - textW - pad; y = pad + fontSize; }
    ctx.shadowColor = 'rgba(0,0,0,0.8)'; ctx.shadowBlur = 6; ctx.shadowOffsetX = 2; ctx.shadowOffsetY = 2;
    ctx.fillStyle = color; ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
    ctx.fillText(timeStr, x, y);
    ctx.restore();
  }

  function drawTimer(ctx, W, H) {
    if (!state.timerEnd) return;
    const remaining = Math.max(0, Math.ceil((state.timerEnd - Date.now()) / 1000));
    if (remaining === 0) { state.timerActive = false; return; }
    const mins = String(Math.floor(remaining / 60)).padStart(2, '0');
    const secs = String(remaining % 60).padStart(2, '0');
    const label = `${mins}:${secs}`;
    const fSize = Math.round(H * 0.06);
    const pad = Math.round(H * 0.015);
    ctx.font = `bold ${fSize}px "Courier New", monospace`;
    ctx.textBaseline = 'top'; ctx.textAlign = 'left';
    ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.fillText(label, pad + 1, pad + 1);
    ctx.fillStyle = '#00ff88'; ctx.fillText(label, pad, pad);
  }

  function drawLogo(ctx, W, H) {
    const img = logoCache[state.logoPath];
    if (!img) { const i2 = new Image(); i2.onload = () => { logoCache[state.logoPath] = i2; renderFrame(ctxC); }; i2.onerror = () => {}; i2.src = state.logoPath?.startsWith('file://') ? state.logoPath : 'file:///' + state.logoPath?.replace(/\\/g, '/'); return; }
    const maxW = Math.round(W * 0.15), maxH = Math.round(H * 0.12);
    const scale = Math.min(maxW / img.width, maxH / img.height);
    const dw = img.width * scale, dh = img.height * scale;
    const pad = Math.round(H * 0.02);
    ctx.globalAlpha = 0.85; ctx.drawImage(img, pad, pad, dw, dh); ctx.globalAlpha = 1;
  }

  function renderAnimatedGradient(ctx, W, H, s) {
    const colors = s.anim_grad_colors || gradientAnim.colors;
    const speed = parseFloat(s.anim_grad_speed || gradientAnim.speed || 0.5);
    const t = gradientAnim.time * speed;
    ctx.fillStyle = '#000000'; ctx.fillRect(0, 0, W, H);
    ctx.save(); ctx.globalCompositeOperation = 'screen';
    colors.forEach((color, idx) => {
      const phase = (t + idx * (Math.PI * 2 / colors.length));
      const cx = W * (0.3 + 0.4 * Math.sin(phase * 0.7));
      const cy = H * (0.3 + 0.4 * Math.cos(phase * 0.5));
      const radius = Math.max(W, H) * (0.4 + 0.2 * Math.sin(phase * 1.3));
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
      grad.addColorStop(0, color); grad.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);
    });
    ctx.restore();
  }

  function drawDualText() {
    if (!dualState.active || !ctxC) return;
    const W = cvCurr.width, H = cvCurr.height, s = state.settings, l = dualState.layout;
    const origZone = l.original || { x: 0.02, y: 0.05, width: 0.46, height: 0.90, font_size: parseInt(s.font_size || 60), color: s.text_color || '#ffffff', align: 'center', padding: 20 };
    const transZone = l.translated || { x: 0.52, y: 0.05, width: 0.46, height: 0.90, font_size: Math.floor(parseInt(s.font_size || 60) * 0.6), color: '#cccccc', align: 'center', padding: 20 };
    ctxC.save();
    ctxC.strokeStyle = 'rgba(255,255,255,0.2)'; ctxC.lineWidth = 1; ctxC.setLineDash([8, 4]);
    ctxC.beginPath(); ctxC.moveTo(W / 2, H * 0.05); ctxC.lineTo(W / 2, H * 0.95); ctxC.stroke();
    ctxC.setLineDash([]); ctxC.restore();
    drawTextInZone(dualState.original, origZone, W, H, s);
    drawTextInZone(dualState.translated, transZone, W, H, s);
  }

  function drawTextInZone(text, zone, W, H, s) {
    if (!text || !zone || !ctxC) return;
    const zx = zone.x * W, zy = zone.y * H, zw = zone.width * W, zh = zone.height * H, pad = zone.padding || 20;
    const family = s.font_family || 'Arial';
    const color = zone.color || s.text_color || '#ffffff';
    const align = zone.align || 'center';
    const bold = zone.bold !== undefined ? zone.bold : s.font_bold === 'true';
    let currentSize = zone.font_size || parseInt(s.font_size || 48);
    ctxC.font = `${bold ? 'bold ' : ''}${currentSize}px "${family}"`;
    const maxW = zw - pad * 2;
    let lines = [];
    text.split('\n').forEach(rawLine => {
      if (!rawLine.trim()) { lines.push(''); return; }
      lines.push(...smartWordWrap(rawLine, maxW, ctxC));
    });
    let lineH = currentSize * 1.35;
    let totalH = lineH * lines.length;
    while (totalH > zh - pad * 2 && currentSize > 12) {
      currentSize -= 2; ctxC.font = `${bold ? 'bold ' : ''}${currentSize}px "${family}"`;
      lineH = currentSize * 1.35; totalH = lineH * lines.length;
    }
    let startY = zy + (zh - totalH) / 2 + currentSize * 0.85;
    ctxC.save();
    lines.forEach((line, i) => {
      if (!line) return;
      const lw = ctxC.measureText(line).width;
      let lx; if (align === 'left') lx = zx + pad; else if (align === 'right') lx = zx + zw - pad - lw; else lx = zx + (zw - lw) / 2;
      ctxC.fillStyle = color; ctxC.fillText(line, lx, startY + i * lineH);
    });
    ctxC.restore();
  }

  // ── Ticker animations ──────────────────────────────────────────────────────
  function showTickerWithEffect(effect, duration) {
    const H = cvCurr.height;
    const barH = Math.round(H * 0.08), finalY = H - barH;
    if (effect === 'instant' || effect === 'none') { tickerAnim.barY = finalY; tickerAnim.barOpacity = 1.0; tickerAnim.animating = false; return; }
    if (effect === 'fade') { tickerAnim.barY = finalY; tickerAnim.barOpacity = 0; tickerAnim.animating = true; tickerAnim.slideDir = 'in'; tickerAnim.animStart = performance.now(); tickerAnim.animDur = duration; tickerAnim.onDone = null; tickerAnimLoop(performance.now()); return; }
    tickerAnim.barY = H; tickerAnim.targetY = finalY; tickerAnim.barOpacity = 1.0; tickerAnim.animating = true; tickerAnim.slideDir = 'in'; tickerAnim.animStart = performance.now(); tickerAnim.animDur = duration; tickerAnim.onDone = null; tickerAnimLoop(performance.now());
  }

  function hideTickerWithEffect(effect, duration) {
    const H = cvCurr.height;
    if (effect === 'instant' || effect === 'none') { state.tickerActive = false; state.tickerText = ''; tickerAnim.barY = null; tickerAnim.animating = false; renderFrame(ctxC); return; }
    if (effect === 'fade') { tickerAnim.animating = true; tickerAnim.slideDir = 'out'; tickerAnim.animStart = performance.now(); tickerAnim.animDur = duration; tickerAnim.onDone = () => { state.tickerActive = false; state.tickerText = ''; tickerAnim.barY = null; tickerAnim.animating = false; }; tickerAnimLoop(performance.now()); return; }
    tickerAnim.targetY = H; tickerAnim.animating = true; tickerAnim.slideDir = 'out'; tickerAnim.animStart = performance.now(); tickerAnim.animDur = duration; tickerAnim.onDone = () => { state.tickerActive = false; state.tickerText = ''; tickerAnim.barY = null; tickerAnim.animating = false; }; tickerAnimLoop(performance.now());
  }

  function tickerAnimLoop(ts) {
    if (!tickerAnim.animating) return;
    const elapsed = ts - tickerAnim.animStart;
    const progress = Math.min(1, elapsed / Math.max(1, tickerAnim.animDur));
    const p = easeOutCubic(progress);
    const H = cvCurr.height;
    const barH = Math.round(H * 0.08), finalY = H - barH;
    if (tickerAnim.slideDir === 'in') {
      if (tickerAnim.targetY !== null) tickerAnim.barY = H + (finalY - H) * p;
      else tickerAnim.barOpacity = p, tickerAnim.barY = finalY;
    } else {
      if (tickerAnim.targetY !== null) { const sY = tickerAnim.barY || finalY; tickerAnim.barY = finalY + (H - finalY) * p; }
      else tickerAnim.barOpacity = 1 - p, tickerAnim.barY = finalY;
    }
    if (progress < 1) requestAnimationFrame(tickerAnimLoop);
    else { tickerAnim.animating = false; if (tickerAnim.onDone) { tickerAnim.onDone(); tickerAnim.onDone = null; } if (tickerAnim.slideDir === 'in') { tickerAnim.barY = finalY; tickerAnim.targetY = null; } }
  }

  // ── Main loop ───────────────────────────────────────────────────────────────
  function mainLoop(ts) {
    const dt = ts - lastTickTs;
    gradientAnim.time += dt / 1000;
    if (state.tickerActive && state.tickerText && !tickerAnim.animating) {
      tickerX -= tickerSettings.speed;
      const textW = ctxC.measureText(state.tickerText).width;
      if (tickerX + textW < 0) tickerX = cvCurr.width;
    }
    if (state.clockActive || state.timerActive) renderFrame(ctxC);
    if (state.settings.bg_type === 'animated_gradient') renderFrame(ctxC);
    lastTickTs = ts;
    requestAnimationFrame(mainLoop);
  }

  // ── Init ─────────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    resize();
    requestAnimationFrame(mainLoop);
  });

  if (document.readyState !== 'loading') {
    resize();
    requestAnimationFrame(mainLoop);
  }
})();
