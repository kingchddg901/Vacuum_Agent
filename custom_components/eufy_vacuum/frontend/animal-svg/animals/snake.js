/**
 * Snake — procedural renderer.
 *
 * type: 'custom' — does not use the parts/quadruped/parrot pipeline. Instead
 * it provides a `render(svg, pose)` callback that builds DOM directly into the
 * passed-in <svg> root and returns a cleanup function. The host element calls
 * cleanup on pose change / disconnect.
 *
 * Pose mapping:
 *   AnimalSVG pose   → snake mode
 *   animating        → curling
 *   standing         → standing
 *   curled           → resting
 *   alert            → alert
 *   walking          → moving
 *   warning          → warning
 */
(function () {
  const SVGNS = 'http://www.w3.org/2000/svg';

  const HEAD_X = 90;
  const HEAD_Y = 170;
  const SEGMENTS = 70;
  const SEG_LEN = 5;
  const BODY_WIDTH_HEAD = 22;
  const BODY_WIDTH_TAIL = 4;
  const TANGENT_SAMPLES = 5;
  const WAVE_AMP = 22;
  const RATTLE_SEGMENTS = 5;
  const RATTLE_SEG_W = 7;
  const RATTLE_SEG_H = 5;

  const POSE_TO_MODE = {
    animating: 'curling',
    standing:  'standing',
    curled:    'resting',
    alert:     'alert',
    walking:   'moving',
    warning:   'warning',
  };

  function buildMovingPoints(t) {
    const pts = [];
    for (let i = 0; i < SEGMENTS; i++) {
      const x = i * 0.18;
      const wave =
              Math.sin(x * 0.8  - t) +
        0.30 * Math.sin(x * 1.7  - t * 1.3) +
        0.15 * Math.sin(x * 2.5  - t * 0.7);
      pts.push([HEAD_X + i * SEG_LEN, HEAD_Y + wave * WAVE_AMP]);
    }
    return pts;
  }

  function buildCoilPoints() {
    const cx = 240, cy = 160, turns = 2.4;
    const pts = [];
    for (let i = 0; i < SEGMENTS; i++) {
      const f = i / (SEGMENTS - 1);
      const r = 70 - f * 60;
      const angle = Math.PI + f * turns * Math.PI * 2;
      pts.push([cx + Math.cos(angle) * r, cy + Math.sin(angle) * r * 0.55]);
    }
    return pts;
  }

  function buildWarningCoilPoints() {
    const cx = 240, cy = 160, turns = 2.0;
    const pts = [];
    for (let i = 0; i < SEGMENTS; i++) {
      const f = i / (SEGMENTS - 1);
      const r = 55 * (1 - f * 0.80);
      const angle = Math.PI + f * turns * Math.PI * 2;
      const tailLift = f > 0.85 ? (f - 0.85) / 0.15 * 60 : 0;
      pts.push([cx + Math.cos(angle) * r, cy + Math.sin(angle) * r * 0.52 - tailLift]);
    }
    return pts;
  }

  function pointsToPath(pts) {
    if (pts.length === 0) return '';
    let d = `M ${pts[0][0]} ${pts[0][1]}`;
    for (let i = 1; i < pts.length - 1; i++) {
      const [x0, y0] = pts[i];
      const [x1, y1] = pts[i + 1];
      d += ` Q ${x0} ${y0} ${(x0 + x1) / 2} ${(y0 + y1) / 2}`;
    }
    const last = pts[pts.length - 1];
    d += ` T ${last[0]} ${last[1]}`;
    return d;
  }

  function computeHeadAngleDeg(pts) {
    const count = Math.min(TANGENT_SAMPLES, pts.length - 1);
    let dx = 0, dy = 0;
    for (let i = 0; i < count; i++) {
      dx += pts[i + 1][0] - pts[i][0];
      dy += pts[i + 1][1] - pts[i][1];
    }
    return (Math.atan2(dy, dx) * 180) / Math.PI;
  }

  function el(name, attrs) {
    const e = document.createElementNS(SVGNS, name);
    if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function buildPointsForFrame(mode, t) {
    if (mode === 'warning') return buildWarningCoilPoints();
    if (mode === 'alert' || mode === 'resting' || mode === 'standing') return buildCoilPoints();
    if (mode === 'curling') {
      // Curl in place at the coil's natural centre (240, 160). The original
      // React version offset the coil so the stretched tail stayed pinned;
      // that pulled the finished coil out past the right of the viewbox.
      const CURL_DURATION = 1.56;
      const raw = Math.min(1, t / CURL_DURATION);
      const stretched = buildMovingPoints(t);
      const coiled = buildCoilPoints();

      return stretched.map(([sx, sy], i) => {
        const f = i / (SEGMENTS - 1);
        const segmentStart = (1 - f) * 0.55;
        const segmentRaw = Math.max(0, Math.min(1, (raw - segmentStart) / (1 - segmentStart)));
        const k = segmentRaw < 0.5
          ? 2 * segmentRaw * segmentRaw
          : 1 - Math.pow(-2 * segmentRaw + 2, 2) / 2;
        const [cx, cy] = coiled[i];
        return [sx + (cx - sx) * k, sy + (cy - sy) * k];
      });
    }
    return buildMovingPoints(t);
  }

  function headPoseFor(mode) {
    if (mode === 'alert')    return { angle: 75,   lift: 30 };
    if (mode === 'resting')  return { angle: -20,  lift: 6  };
    if (mode === 'warning')  return { angle: 100,  lift: 34 };
    if (mode === 'standing') return { angle: 30,   lift: 20 };
    return null; // moving / curling: follow body tangent
  }

  AnimalSVG.register('snake', {
    label: 'Snake',
    type: 'custom',
    colors: {
      '--animal-fur': '95 45% 32%',
      '--animal-fur-shadow': '95 50% 18%',
      '--animal-fur-highlight': '60 70% 55%',
      '--animal-eye': '45 95% 55%',
      '--animal-pupil': '0 0% 5%',
      '--animal-nose': '0 0% 10%',
      '--animal-whisker': '0 0% 30%',
      '--animal-ear-inner': '95 40% 25%',
      '--animal-white-tip': '60 50% 85%',
    },
    /**
     * Render directly into the host <svg>. Returns a cleanup fn.
     */
    render(svg, pose) {
      const mode = POSE_TO_MODE[pose] || 'standing';
      const animating = mode === 'moving' || mode === 'curling';
      const showWarning = mode === 'warning';
      const showCoiled  = mode === 'alert' || mode === 'resting' || mode === 'standing';
      const showTongue  = mode === 'alert' || mode === 'moving' || mode === 'curling' || mode === 'warning';

      const root = el('g');
      svg.appendChild(root);

      // Body shadow + main + dorsal stripe + tail taper
      const shadow = el('path', {
        fill: 'none',
        stroke: 'hsl(var(--animal-fur-shadow))',
        'stroke-width': BODY_WIDTH_HEAD + 2,
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        opacity: '0.5',
      });
      const body = el('path', {
        fill: 'none',
        stroke: 'hsl(var(--animal-fur))',
        'stroke-width': BODY_WIDTH_HEAD,
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
      });
      const stripe = el('path', {
        fill: 'none',
        stroke: 'hsl(var(--animal-fur-highlight))',
        'stroke-width': '3',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'stroke-dasharray': '6 8',
        opacity: '0.55',
      });
      const tail = el('path', {
        fill: 'none',
        stroke: 'hsl(var(--animal-fur))',
        'stroke-width': BODY_WIDTH_TAIL + 4,
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
      });
      if (showCoiled || showWarning) {
        const trans = 'd 0.6s ease';
        shadow.style.transition = trans;
        body.style.transition   = trans;
        stripe.style.transition = trans;
        tail.style.transition   = trans;
      }
      root.append(shadow, body, stripe, tail);

      // Rattle group (warning only)
      let rattleGroup = null;
      if (showWarning) {
        rattleGroup = el('g', { class: 'sn-rattle' });
        root.appendChild(rattleGroup);
      }

      // Head transform group
      const headTransform = el('g');
      if (showCoiled || showWarning) headTransform.style.transition = 'transform 0.6s ease';
      root.appendChild(headTransform);

      // Sway group nested inside the placement transform — used in warning mode
      // so the head can sway without overriding its translate/rotate.
      const headSway = el('g');
      headTransform.appendChild(headSway);

      const headEll  = el('ellipse', { cx: 0, cy: 0, rx: 26, ry: 16, fill: 'hsl(var(--animal-fur))' });
      const headHl   = el('ellipse', { cx: -6, cy: -2, rx: 22, ry: 13, fill: 'hsl(var(--animal-fur-highlight))', opacity: '0.35' });
      const eyeUp    = el('circle', { cx: -6, cy: -6, r: showWarning ? 4 : 3.2, fill: 'hsl(var(--animal-eye))' });
      const pupUp    = el('circle', { cx: -6, cy: -6, r: showWarning ? 2 : 1.4, fill: 'hsl(var(--animal-pupil))' });
      const eyeDn    = el('circle', { cx: -6, cy: 6,  r: showWarning ? 4 : 3.2, fill: 'hsl(var(--animal-eye))' });
      const pupDn    = el('circle', { cx: -6, cy: 6,  r: showWarning ? 2 : 1.4, fill: 'hsl(var(--animal-pupil))' });
      const nostrilU = el('circle', { cx: -22, cy: -3, r: 1, fill: 'hsl(var(--animal-nose))' });
      const nostrilL = el('circle', { cx: -22, cy: 3,  r: 1, fill: 'hsl(var(--animal-nose))' });
      headSway.append(headEll, headHl, eyeUp, pupUp, eyeDn, pupDn, nostrilU, nostrilL);

      let tongue = null;
      if (showTongue) {
        const g = el('g');
        const path = el('path', {
          d: 'M -26 0 Q -36 -1 -42 -4 M -26 0 Q -36 1 -42 4 M -26 0 L -38 0',
          stroke: 'hsl(0 70% 50%)',
          'stroke-width': showWarning ? 2 : 1.4,
          fill: 'none',
          'stroke-linecap': 'round',
        });
        const anim = el('animate', {
          attributeName: 'opacity',
          values: '1;1;0;0;1',
          dur: showWarning ? '0.4s' : '1.2s',
          repeatCount: 'indefinite',
        });
        path.appendChild(anim);
        g.appendChild(path);
        headSway.appendChild(g);
        tongue = g;
      }

      if (showWarning) {
        const sway = el('animateTransform', {
          attributeName: 'transform',
          type: 'rotate',
          values: '-8 0 0; 8 0 0; -8 0 0',
          dur: '0.7s',
          repeatCount: 'indefinite',
        });
        headSway.appendChild(sway);
      }

      // === Frame update ======================================================
      function update(t) {
        const pts = buildPointsForFrame(mode, t);
        const d = pointsToPath(pts);
        shadow.setAttribute('d', d);
        body.setAttribute('d', d);
        stripe.setAttribute('d', d);

        const tailStart = Math.floor(SEGMENTS * 0.75);
        tail.setAttribute('d', pointsToPath(pts.slice(tailStart)));

        const neckX = pts[0][0];
        const neckY = pts[0][1];
        const tangent = computeHeadAngleDeg(pts);
        const pose = headPoseFor(mode);
        const angle = pose ? pose.angle : tangent;
        const lift  = pose ? pose.lift  : 0;
        const rad = (angle * Math.PI) / 180;
        const x = neckX - Math.cos(rad) * lift;
        const y = neckY - Math.sin(rad) * lift;
        headTransform.setAttribute('transform', `translate(${x} ${y}) rotate(${angle})`);

        if (rattleGroup) {
          // Rebuild beads relative to the new tail position.
          while (rattleGroup.firstChild) rattleGroup.removeChild(rattleGroup.firstChild);
          const tailPt = pts[pts.length - 1];
          const prev = pts[pts.length - 2] || tailPt;
          const dx = tailPt[0] - prev[0];
          const dy = tailPt[1] - prev[1];
          const len = Math.sqrt(dx * dx + dy * dy) || 1;
          const ux = dx / len, uy = dy / len;
          for (let k = 0; k < RATTLE_SEGMENTS; k++) {
            const ox = tailPt[0] + ux * k * (RATTLE_SEG_W - 2);
            const oy = tailPt[1] + uy * k * (RATTLE_SEG_W - 2);
            const scale = 1 - k * 0.1;
            const dark = k % 2 === 0;
            rattleGroup.appendChild(el('ellipse', {
              cx: ox, cy: oy,
              rx: RATTLE_SEG_W * scale, ry: RATTLE_SEG_H * scale,
              fill: dark ? 'hsl(var(--animal-fur-shadow))' : 'hsl(var(--animal-fur-highlight))',
              opacity: '0.9',
            }));
          }
          // Inject the shake keyframe scoped to the current tail anchor.
          let shakeStyle = svg.querySelector('style[data-rattle]');
          if (!shakeStyle) {
            shakeStyle = el('style');
            shakeStyle.setAttribute('data-rattle', '1');
            svg.insertBefore(shakeStyle, svg.firstChild);
          }
          shakeStyle.textContent = `
            .sn-rattle { animation: snRattleShake 0.08s linear infinite alternate; transform-origin: ${tailPt[0]}px ${tailPt[1]}px; }
            @keyframes snRattleShake { 0% { transform: translateX(-3px) rotate(-5deg); } 100% { transform: translateX(3px) rotate(5deg); } }
          `;
        }
      }

      // Static initial frame
      update(0);

      // Animation loop
      let raf = null;
      let start = null;
      function tick(ts) {
        if (start == null) start = ts;
        update((ts - start) / 1000);
        raf = requestAnimationFrame(tick);
      }
      if (animating) raf = requestAnimationFrame(tick);

      return () => {
        if (raf != null) cancelAnimationFrame(raf);
        if (root.parentNode) root.parentNode.removeChild(root);
        const s = svg.querySelector('style[data-rattle]');
        if (s) s.remove();
      };
    },
  });
})();
