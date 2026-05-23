/**
 * <animal-svg> — Home Assistant friendly custom element.
 *
 * Attributes (reflected, observable):
 *   animal  — registered animal name (e.g. "cat", "dog", "raccoon", "parrot", "snake")
 *   pose    — one of: animating | standing | curled | alert | walking | warning
 *   width   — optional css width  (default 360px)
 *   height  — optional css height (default 240px)
 *
 * Methods:
 *   .setAnimal(name)
 *   .setPose(pose)
 *
 * Animals register themselves via:
 *   AnimalSVG.register(name, definition)
 *
 * See animals/*.js and README.md for the definition shape.
 */

(() => {
  if (window.AnimalSVG) return; // idempotent

  const POSES = ['animating', 'standing', 'curled', 'alert', 'walking', 'warning'];
  const REGISTRY = new Map();

  // === KEYFRAMES (shared) ====================================================
  // Pulled verbatim from the React version. Class names gate which keyframe set
  // is active for the current pose, so it is safe to ship them all in one block.
  const KEYFRAMES_CSS = `
    /* Curling (quadruped) */
    @keyframes headTuck         { 0% { transform: translate(0,0) rotate(0deg); }       100% { transform: translate(20px,10px) rotate(30deg); } }
    @keyframes bodyCompress     { 0% { transform: rotate(0deg); }                      100% { transform: rotate(15deg); } }
    @keyframes tailCurl         { 0% { transform: rotate(0deg) translate(0,0); }       100% { transform: rotate(40deg) translate(-20px,10px); } }
    @keyframes legsFade         { 0%,78% { opacity: 1; }                               100% { opacity: 0; } }
    @keyframes frontLeftLegCurl  { 0% { transform: translate(0,0) rotate(0deg) scaleY(1); }  55% { transform: translate(2px,-5px) rotate(-34deg) scaleY(0.88); }  100% { transform: translate(8px,-16px) rotate(-96deg) scaleY(0.38); } }
    @keyframes frontRightLegCurl { 0% { transform: translate(0,0) rotate(0deg) scaleY(1); }  55% { transform: translate(2px,-4px) rotate(-30deg) scaleY(0.88); }  100% { transform: translate(6px,-14px) rotate(-90deg) scaleY(0.38); } }
    @keyframes backLeftLegCurl   { 0% { transform: translate(0,0) rotate(0deg) scaleY(1); }  55% { transform: translate(-3px,-6px) rotate(36deg) scaleY(0.88); } 100% { transform: translate(-8px,-18px) rotate(104deg) scaleY(0.38); } }
    @keyframes backRightLegCurl  { 0% { transform: translate(0,0) rotate(0deg) scaleY(1); }  55% { transform: translate(-2px,-5px) rotate(34deg) scaleY(0.88); } 100% { transform: translate(-7px,-16px) rotate(100deg) scaleY(0.38); } }
    @keyframes eyeClose         { 0% { transform: scaleY(1); } 75% { transform: scaleY(1); } 100% { transform: scaleY(0.15); } }
    @keyframes kneeFold         { 0% { transform: rotate(0deg); } 60% { transform: rotate(-40deg); } 100% { transform: rotate(-75deg); } }

    /* Curling (parrot) */
    @keyframes pBodyPuff   { 0% { transform: rotate(0deg) scaleX(1); }       100% { transform: rotate(5deg) scaleX(1.05); } }
    @keyframes pHeadTuck   { 0% { transform: translate(0,0) rotate(0deg); }  100% { transform: translate(15px,12px) rotate(-25deg); } }
    @keyframes pTailDroop  { 0% { transform: rotate(0deg); }                 100% { transform: rotate(10deg); } }

    /* Walking (quadruped) */
    @keyframes wBounce    { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-2px); } }
    @keyframes wStepA     { 0% { transform: rotate(-10deg); } 25% { transform: rotate(10deg); }  50% { transform: rotate(10deg); }  75% { transform: rotate(-10deg); } 100% { transform: rotate(-10deg); } }
    @keyframes wStepB     { 0% { transform: rotate(10deg); }  25% { transform: rotate(-10deg); } 50% { transform: rotate(-10deg); } 75% { transform: rotate(10deg); }  100% { transform: rotate(10deg); } }
    @keyframes wTailSway  { 0% { transform: rotate(-10deg); } 100% { transform: rotate(10deg); } }
    @keyframes wHeadBob   { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-2px); } }
    @keyframes kneeFlexA  { 0%,100% { transform: rotate(0deg); } 25% { transform: rotate(-22deg); } 50% { transform: rotate(0deg); } }
    @keyframes kneeFlexB  { 0%,100% { transform: rotate(0deg); } 75% { transform: rotate(-22deg); } }

    /* Flight (parrot) */
    @keyframes fLift        { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-25px); } }
    @keyframes fBodyTilt    { 0%,100% { transform: rotate(0deg); } 25% { transform: rotate(-8deg); } 75% { transform: rotate(8deg); } }
    @keyframes fHeadBob     { 0%,100% { transform: translateY(0) rotate(0deg); } 50% { transform: translateY(-3px) rotate(-5deg); } }
    @keyframes fTailStream  { 0% { transform: rotate(-5deg); } 100% { transform: rotate(12deg); } }
    @keyframes fLegsTuck    { 0%,100% { transform: translateY(0) scaleY(1); } 50% { transform: translateY(-8px) scaleY(0.7); } }
    @keyframes fWingFlapL   { 0% { transform: rotate(25deg); } 100% { transform: rotate(-30deg); } }
    @keyframes fWingFlapR   { 0% { transform: rotate(-25deg); } 100% { transform: rotate(30deg); } }

    /* Alert */
    @keyframes alHeadScan   { 0%,100% { transform: translate(0,0) rotate(-6deg); } 50% { transform: translate(2px,-1px) rotate(6deg); } }
    @keyframes alTailFlick  { 0%,70%,100% { transform: rotate(40deg) translate(-20px,10px); } 80% { transform: rotate(55deg) translate(-22px,8px); } 90% { transform: rotate(30deg) translate(-18px,12px); } }
    @keyframes alPHeadScan  { 0%,100% { transform: translate(0,0) rotate(-8deg); } 50% { transform: translate(3px,-2px) rotate(10deg); } }
    @keyframes alPBodyShift { 0% { transform: rotate(0deg) scaleX(1.05); } 100% { transform: rotate(2deg) scaleX(1.06); } }

    /* Warning */
    @keyframes warnHeadBob    { 0% { transform: translate(-5px,-8px) rotate(-10deg); } 100% { transform: translate(-5px,-12px) rotate(-14deg); } }
    @keyframes warnTailFlick  { 0% { transform: rotate(-50deg) translate(5px,-10px); } 100% { transform: rotate(-58deg) translate(6px,-12px); } }
    @keyframes warnPBodyPulse { 0% { transform: rotate(0deg) scale(1.14); } 100% { transform: rotate(2deg) scale(1.18); } }
    @keyframes warnPHeadBob   { 0% { transform: translate(0,0) rotate(-5deg); } 100% { transform: translate(1px,-3px) rotate(-8deg); } }
  `;

  // === ANIMATION CLASS RULES =================================================
  // For each pose × class, attach the animation. Knee-fold inner classes are
  // namespaced by animal (cat-fl-lower, dog-fl-lower, rac-fl-lower) so each
  // animal can keep its lower-leg group classnames stable across poses.

  const ANIMATION_CSS = `
    .pose-animating .a-head { animation: headTuck 3s ease-in-out infinite alternate; transform-origin: 140px 140px; }
    .pose-animating .a-body { animation: bodyCompress 3s ease-in-out infinite alternate; transform-origin: 250px 200px; }
    .pose-animating .a-tail { animation: tailCurl 3s ease-in-out infinite alternate; transform-origin: 340px 180px; }
    .pose-animating .a-legs { animation: legsFade 3s ease-in-out infinite alternate; }
    .pose-animating .a-fl   { animation: frontLeftLegCurl 3s ease-in-out infinite alternate; transform-origin: 166px 198px; }
    .pose-animating .a-fr   { animation: frontRightLegCurl 3s ease-in-out infinite alternate; transform-origin: 194px 198px; }
    .pose-animating .a-bl   { animation: backLeftLegCurl 3s ease-in-out infinite alternate; transform-origin: 303px 198px; }
    .pose-animating .a-br   { animation: backRightLegCurl 3s ease-in-out infinite alternate; transform-origin: 332px 195px; }
    .pose-animating .a-eyes { animation: eyeClose 3s ease-in-out infinite alternate; transform-origin: 145px 117px; }
    .pose-animating .cat-fl-lower,.pose-animating .dog-fl-lower,.pose-animating .rac-fl-lower,
    .pose-animating .cat-fr-lower,.pose-animating .dog-fr-lower,.pose-animating .rac-fr-lower,
    .pose-animating .cat-bl-lower,.pose-animating .dog-bl-lower,.pose-animating .rac-bl-lower,
    .pose-animating .cat-br-lower,.pose-animating .dog-br-lower,.pose-animating .rac-br-lower {
      animation: kneeFold 3s ease-in-out infinite alternate;
    }

    .pose-animating .p-body { animation: pBodyPuff 3s ease-in-out infinite alternate; transform-origin: 258px 244px; }
    .pose-animating .p-head { animation: pHeadTuck 3s ease-in-out infinite alternate; transform-origin: 220px 140px; }
    .pose-animating .p-tail { animation: pTailDroop 3s ease-in-out infinite alternate; transform-origin: 320px 225px; }
    .pose-animating .p-eyes { animation: eyeClose 3s ease-in-out infinite alternate; transform-origin: 218px 108px; }

    .pose-walking .w-bounce { animation: wBounce 0.8s ease-in-out infinite; }
    .pose-walking .w-fl     { animation: wStepA 0.8s ease-in-out infinite; transform-origin: 162px 198px; }
    .pose-walking .w-fr     { animation: wStepB 0.8s ease-in-out infinite; transform-origin: 190px 198px; }
    .pose-walking .w-bl     { animation: wStepB 0.8s ease-in-out infinite; transform-origin: 300px 195px; }
    .pose-walking .w-br     { animation: wStepA 0.8s ease-in-out infinite; transform-origin: 325px 192px; }
    .pose-walking .w-tail   { animation: wTailSway 0.8s ease-in-out infinite alternate; transform-origin: 340px 180px; }
    .pose-walking .w-head   { animation: wHeadBob 0.8s ease-in-out infinite; transform-origin: 140px 160px; }
    .pose-walking .cat-fl-lower,.pose-walking .dog-fl-lower,.pose-walking .rac-fl-lower,
    .pose-walking .cat-br-lower,.pose-walking .dog-br-lower,.pose-walking .rac-br-lower {
      animation: kneeFlexA 0.8s ease-in-out infinite;
    }
    .pose-walking .cat-fr-lower,.pose-walking .dog-fr-lower,.pose-walking .rac-fr-lower,
    .pose-walking .cat-bl-lower,.pose-walking .dog-bl-lower,.pose-walking .rac-bl-lower {
      animation: kneeFlexB 0.8s ease-in-out infinite;
    }

    .pose-walking .f-whole  { animation: fLift 1.2s ease-in-out infinite; }
    .pose-walking .f-body   { animation: fBodyTilt 1.2s ease-in-out infinite; transform-origin: 258px 200px; }
    .pose-walking .f-head   { animation: fHeadBob 1.2s ease-in-out infinite; transform-origin: 220px 120px; }
    .pose-walking .f-tail   { animation: fTailStream 1.2s ease-in-out infinite alternate; transform-origin: 320px 225px; }
    .pose-walking .f-legs   { animation: fLegsTuck 1.2s ease-in-out infinite; transform-origin: 258px 244px; }
    .pose-walking .f-wing-l { animation: fWingFlapL 0.4s ease-in-out infinite alternate; transform-origin: 210px 155px; }
    .pose-walking .f-wing-r { animation: fWingFlapR 0.4s ease-in-out infinite alternate; transform-origin: 310px 155px; }

    .pose-alert .al-head    { animation: alHeadScan 2.4s ease-in-out infinite; transform-origin: 140px 140px; }
    .pose-alert .al-tail    { animation: alTailFlick 1.6s ease-in-out infinite; transform-origin: 340px 180px; }
    .pose-alert .al-p-head  { animation: alPHeadScan 2.4s ease-in-out infinite; transform-origin: 220px 140px; }
    .pose-alert .al-p-body  { animation: alPBodyShift 3s ease-in-out infinite alternate; transform-origin: 258px 244px; }

    .pose-warning .warn-head   { animation: warnHeadBob 0.5s ease-in-out infinite alternate; transform-origin: 140px 130px; }
    .pose-warning .warn-tail   { animation: warnTailFlick 0.3s ease-in-out infinite alternate; transform-origin: 340px 140px; }
    .pose-warning .warn-p-body { animation: warnPBodyPulse 0.6s ease-in-out infinite alternate; transform-origin: 258px 190px; }
    .pose-warning .warn-p-head { animation: warnPHeadBob 0.5s ease-in-out infinite alternate; transform-origin: 220px 130px; }
  `;

  // === POSE → INLINE STYLE TRANSFORMS (quadruped + parrot static frames) =====
  // These mirror headStyle/bodyStyle/etc. in the React version. They apply when
  // the pose is NOT a class-driven animation (i.e. the static held poses).

  const LEG_TRANSITION = 'transform 0.95s cubic-bezier(0.22, 1, 0.36, 1)';

  function quadrupedStyles(pose) {
    const isCurled   = pose === 'curled';
    const isAlert    = pose === 'alert';
    const isWalking  = pose === 'walking';
    const isStanding = pose === 'standing';
    const isWarning  = pose === 'warning';
    const isTucked   = isCurled || isAlert;

    const head = isCurled
      ? 'transform: translate(20px, 10px) rotate(30deg); transform-origin: 140px 140px; transition: transform 1s ease;'
      : (isStanding || isWalking || isAlert)
      ? 'transform: translate(0,0) rotate(0deg); transform-origin: 140px 140px; transition: transform 1s ease;'
      : isWarning
      ? 'transform: translate(-5px, -8px) rotate(-10deg); transform-origin: 140px 140px; transition: transform 0.5s ease;'
      : '';

    const body = isTucked
      ? 'transform: rotate(15deg); transform-origin: 250px 200px; transition: transform 1s ease;'
      : (isStanding || isWalking)
      ? 'transform: rotate(0deg); transform-origin: 250px 200px; transition: transform 1s ease;'
      : isWarning
      ? 'transform: rotate(-18deg) scaleY(1.08); transform-origin: 250px 185px; transition: transform 0.5s ease;'
      : '';

    const tail = isTucked
      ? 'transform: rotate(40deg) translate(-20px, 10px); transform-origin: 340px 180px; transition: transform 1s ease;'
      : (isStanding || isWalking)
      ? 'transform: rotate(0deg) translate(0,0); transform-origin: 340px 180px; transition: transform 1s ease;'
      : isWarning
      ? 'transform: rotate(-50deg) translate(5px, -10px); transform-origin: 340px 180px; transition: transform 0.5s ease;'
      : '';

    const legs = isTucked
      ? 'opacity: 0; transition: opacity 0.35s ease 0.45s;'
      : (isStanding || isWalking || isWarning)
      ? 'opacity: 1; transition: opacity 0.25s ease;'
      : '';

    const fl = isTucked
      ? `transform: translate(8px, -16px) rotate(-96deg) scaleY(0.38); transform-origin: 166px 198px; transition: ${LEG_TRANSITION};`
      : (isStanding || isWarning)
      ? `transform: translate(0, 0) rotate(0deg) scaleY(1); transform-origin: 166px 198px; transition: ${LEG_TRANSITION};`
      : '';

    const fr = isTucked
      ? `transform: translate(6px, -14px) rotate(-90deg) scaleY(0.38); transform-origin: 194px 198px; transition: ${LEG_TRANSITION};`
      : (isStanding || isWarning)
      ? `transform: translate(0, 0) rotate(0deg) scaleY(1); transform-origin: 194px 198px; transition: ${LEG_TRANSITION};`
      : '';

    const bl = isTucked
      ? `transform: translate(-8px, -18px) rotate(104deg) scaleY(0.38); transform-origin: 303px 198px; transition: ${LEG_TRANSITION};`
      : (isStanding || isWarning)
      ? `transform: translate(0, 0) rotate(0deg) scaleY(1); transform-origin: 303px 198px; transition: ${LEG_TRANSITION};`
      : '';

    const br = isTucked
      ? `transform: translate(-7px, -16px) rotate(100deg) scaleY(0.38); transform-origin: 332px 195px; transition: ${LEG_TRANSITION};`
      : (isStanding || isWarning)
      ? `transform: translate(0, 0) rotate(0deg) scaleY(1); transform-origin: 332px 195px; transition: ${LEG_TRANSITION};`
      : '';

    const eyes = isCurled
      ? 'transform: scaleY(0.15); transform-origin: 145px 117px; transition: transform 0.8s ease;'
      : isAlert
      ? 'transform: scaleY(1.15); transform-origin: 145px 117px; transition: transform 0.4s ease;'
      : isWarning
      ? 'transform: scaleY(1.2); transform-origin: 145px 117px; transition: transform 0.4s ease;'
      : (isStanding || isWalking)
      ? 'transform: scaleY(1); transform-origin: 145px 117px; transition: transform 0.8s ease;'
      : '';

    return { head, body, tail, legs, fl, fr, bl, br, eyes };
  }

  function parrotStyles(pose) {
    const isCurled   = pose === 'curled';
    const isAlert    = pose === 'alert';
    const isStanding = pose === 'standing';
    const isWarning  = pose === 'warning';

    const body = isCurled
      ? 'transform: rotate(5deg) scaleX(1.05); transform-origin: 258px 244px; transition: transform 1s ease;'
      : isAlert
      ? 'transform: rotate(0deg) scaleX(1.05); transform-origin: 258px 244px; transition: transform 1s ease;'
      : isStanding
      ? 'transform: rotate(0deg) scaleX(1); transform-origin: 258px 244px; transition: transform 1s ease;'
      : isWarning
      ? 'transform: rotate(0deg) scale(1.14); transform-origin: 258px 190px; transition: transform 0.5s ease;'
      : '';

    const tail = isCurled
      ? 'transform: rotate(10deg); transform-origin: 320px 225px; transition: transform 1s ease;'
      : isAlert
      ? 'transform: rotate(8deg); transform-origin: 320px 225px; transition: transform 1s ease;'
      : isWarning
      ? 'transform: rotate(15deg); transform-origin: 320px 225px; transition: transform 0.5s ease;'
      : isStanding
      ? 'transform: rotate(0deg); transform-origin: 320px 225px; transition: transform 1s ease;'
      : '';

    const head = isCurled
      ? 'transform: translate(15px,12px) rotate(-25deg); transform-origin: 220px 140px; transition: transform 1s ease;'
      : (isStanding || isAlert)
      ? 'transform: translate(0,0) rotate(0deg); transform-origin: 220px 140px; transition: transform 1s ease;'
      : isWarning
      ? 'transform: translate(0,0) rotate(-5deg); transform-origin: 220px 140px; transition: transform 0.5s ease;'
      : '';

    const eyes = isCurled
      ? 'transform: scaleY(0.15); transform-origin: 218px 108px; transition: transform 0.8s ease;'
      : (isAlert || isWarning)
      ? 'transform: scaleY(1.2); transform-origin: 218px 108px; transition: transform 0.4s ease;'
      : isStanding
      ? 'transform: scaleY(1); transform-origin: 218px 108px; transition: transform 0.8s ease;'
      : '';

    return { body, tail, head, eyes };
  }

  // === SVG STRING BUILDERS ===================================================

  function colorVarsStyle(colors) {
    return Object.entries(colors).map(([k, v]) => `${k}:${v};`).join('');
  }

  /**
   * Build the SVG inner markup for a quadruped (cat, dog, raccoon).
   * Layout mirrors the JSX in AnimalSVG.tsx, but uses inline style strings
   * derived from quadrupedStyles().
   */
  function renderQuadruped(def, pose) {
    const s = quadrupedStyles(pose);
    const isAnimating = pose === 'animating';
    const isWalking   = pose === 'walking';
    const isAlert     = pose === 'alert';
    const isWarning   = pose === 'warning';

    const bodyClass = isAnimating ? 'a-body' : isWalking ? 'w-bounce' : '';
    const legGroupCls = isAnimating ? 'a-legs' : '';
    const flCls = `${isAnimating ? 'a-fl' : ''} ${isWalking ? 'w-fl' : ''}`.trim();
    const frCls = `${isAnimating ? 'a-fr' : ''} ${isWalking ? 'w-fr' : ''}`.trim();
    const blCls = `${isAnimating ? 'a-bl' : ''} ${isWalking ? 'w-bl' : ''}`.trim();
    const brCls = `${isAnimating ? 'a-br' : ''} ${isWalking ? 'w-br' : ''}`.trim();
    const tailCls = isAnimating ? 'a-tail'
                  : isWalking   ? 'w-tail'
                  : isAlert     ? 'al-tail'
                  : isWarning   ? 'warn-tail' : '';
    const headCls = isAnimating ? 'a-head'
                  : isWalking   ? 'w-head'
                  : isAlert     ? 'al-head'
                  : isWarning   ? 'warn-head' : '';
    const eyesCls = isAnimating ? 'a-eyes' : '';

    const p = def.parts;
    const extra = p.extra ? p.extra : '';

    return `
      ${extra}
      <g class="${bodyClass}" style="${s.body}">
        ${p.body}

        <g class="${legGroupCls}" style="${s.legs}">
          <g class="${flCls}" style="${s.fl}">${p.frontLeftLeg}</g>
          <g class="${frCls}" style="${s.fr}">${p.frontRightLeg}</g>
        </g>
        <g class="${legGroupCls}" style="${s.legs}">
          <g class="${blCls}" style="${s.bl}">${p.backLeftLeg}</g>
          <g class="${brCls}" style="${s.br}">${p.backRightLeg}</g>
        </g>

        <g class="${tailCls}" style="${s.tail}">${p.tail}</g>

        <g class="${headCls}" style="${s.head}">
          ${p.head}
          <g class="${eyesCls}" style="${s.eyes}">${p.eyes}</g>
          ${p.face}
        </g>

        ${isWarning && p.warning ? p.warning : ''}
      </g>
    `;
  }

  /**
   * Parrot — legs anchor to perch, body/head/tail transform independently,
   * wings only show during flight.
   */
  function renderParrot(def, pose) {
    const s = parrotStyles(pose);
    const isAnimating = pose === 'animating';
    const isWalking   = pose === 'walking';
    const isAlert     = pose === 'alert';
    const isWarning   = pose === 'warning';

    const wholeCls = isWalking ? 'f-whole' : '';
    const legsCls  = isWalking ? 'f-legs'  : '';

    const bodyCls = isAnimating ? 'p-body'
                  : isWalking   ? 'f-body'
                  : isAlert     ? 'al-p-body'
                  : isWarning   ? 'warn-p-body' : '';

    const tailCls = isAnimating ? 'p-tail'
                  : isWalking   ? 'f-tail' : '';

    const headCls = isAnimating ? 'p-head'
                  : isWalking   ? 'f-head'
                  : isAlert     ? 'al-p-head'
                  : isWarning   ? 'warn-p-head' : '';

    const eyesCls = isAnimating ? 'p-eyes' : '';

    const p = def.parts;
    const extra = p.extra ? p.extra : '';
    const wings = isWalking ? `${def.wingLeft || ''}${def.wingRight || ''}` : '';

    return `
      ${extra}
      <g class="${wholeCls}">
        <g class="${legsCls}">
          ${p.frontLeftLeg}
          ${p.frontRightLeg}
        </g>

        <g class="${bodyCls}" style="${s.body}">
          ${p.body}
          ${wings}

          <g class="${tailCls}" style="${s.tail}">${p.tail}</g>

          <g class="${headCls}" style="${s.head}">
            ${p.head}
            <g class="${eyesCls}" style="${s.eyes}">${p.eyes}</g>
            ${p.face}
          </g>

          ${isWarning && p.warning ? p.warning : ''}
        </g>
      </g>
    `;
  }

  // === CUSTOM ELEMENT ========================================================

  class AnimalSVGElement extends HTMLElement {
    static get observedAttributes() { return ['animal', 'pose', 'width', 'height']; }

    constructor() {
      super();
      this._root = this.attachShadow({ mode: 'open' });
      this._customCleanup = null; // for animals with type:'custom' (snake)
    }

    connectedCallback() {
      this._render();
    }

    disconnectedCallback() {
      this._teardownCustom();
    }

    attributeChangedCallback() {
      if (this.isConnected) this._render();
    }

    setAnimal(name) { this.setAttribute('animal', name); }
    setPose(pose)   { this.setAttribute('pose', pose); }

    get animal() { return this.getAttribute('animal') || 'cat'; }
    get pose()   { return this.getAttribute('pose')   || 'standing'; }

    _teardownCustom() {
      if (typeof this._customCleanup === 'function') {
        try { this._customCleanup(); } catch (_) {}
      }
      this._customCleanup = null;
    }

    _render() {
      this._teardownCustom();

      const name = this.animal;
      const pose = POSES.includes(this.pose) ? this.pose : 'standing';
      const def  = REGISTRY.get(name);

      // Default host size if no external CSS sets it. Inside the shadow root
      // the SVG always fills the host (width/height 100%) so viewBox handles
      // scaling — this keeps the drawing inside whatever box the host is given.
      const width  = this.getAttribute('width')  || '360px';
      const height = this.getAttribute('height') || '240px';

      if (!def) {
        this._root.innerHTML = `
          <style>:host{display:inline-block;}</style>
          <div style="font:12px sans-serif;color:#888;padding:8px;">
            animal-svg: unknown animal "${escapeHtml(name)}".
            Registered: ${[...REGISTRY.keys()].map(escapeHtml).join(', ') || '(none)'}
          </div>
        `;
        return;
      }

      const colorStyle = colorVarsStyle(def.colors || {});

      let inner = '';
      if (def.type === 'parrot') {
        inner = renderParrot(def, pose);
      } else if (def.type === 'custom') {
        // custom render handled after innerHTML set, via def.render(svgEl, pose).
        inner = '';
      } else {
        inner = renderQuadruped(def, pose);
      }

      this._root.innerHTML = `
        <style>
          :host { display: inline-block; line-height: 0; width: ${width}; height: ${height}; }
          svg   { width: 100%; height: 100%; display: block; overflow: visible; }
          ${KEYFRAMES_CSS}
          ${ANIMATION_CSS}
        </style>
        <svg
          viewBox="-10 -10 500 340"
          preserveAspectRatio="xMidYMid meet"
          xmlns="http://www.w3.org/2000/svg"
          class="pose-${pose}"
          style="${colorStyle}"
        >${inner}</svg>
      `;

      if (def.type === 'custom' && typeof def.render === 'function') {
        const svg = this._root.querySelector('svg');
        try {
          this._customCleanup = def.render(svg, pose) || null;
        } catch (e) {
          console.error('animal-svg custom render failed:', e);
        }
      }
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    })[c]);
  }

  // === PUBLIC API ============================================================

  const AnimalSVG = {
    register(name, def) {
      if (!name || !def) throw new Error('AnimalSVG.register(name, def) — both required');
      REGISTRY.set(name, def);
      // If any element on the page is showing this animal, re-render it.
      document.querySelectorAll('animal-svg').forEach(el => {
        if (el.getAttribute('animal') === name && el._render) el._render();
      });
    },
    unregister(name) { REGISTRY.delete(name); },
    list() { return [...REGISTRY.keys()]; },
    get(name) { return REGISTRY.get(name); },
    POSES,
  };

  window.AnimalSVG = AnimalSVG;
  if (!customElements.get('animal-svg')) {
    customElements.define('animal-svg', AnimalSVGElement);
  }
})();
