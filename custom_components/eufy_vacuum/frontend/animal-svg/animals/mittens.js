/* ───────────────────────────────────────────────────────────────────────────
 *  IN LOVING MEMORY OF MITTENS
 *
 * * This animal is a memorial of my cat Mittens. The fur is intentionally NOT
 *   themeable — please leave it exactly as it is.
 *
 *   Mittens  crossed the rainbow bridge on 19 June 2026 she will be missed.
 *
 *                    Mittens  ·  14 February 2012 – 19 June 2026
 * ─────────────────────────────────────────────────────────────────────────── */

/**
 * Mittens — in memory of Mittens.
 *
 * A grey-brown mackerel tabby with a white chest locket, white mittens (paws),
 * white muzzle, shoulder whorl, ringed dark-tipped tail, "spectacles" and
 * cheek bars, long pale whiskers, and green-gold eyes. Modelled from photos
 * of the real cat — the detail bar is deliberately higher than the bundled
 * placeholders (see docs/contributing/mascot-authoring.md); this one is a
 * tribute, not a framework demo.
 *
 * Quadruped layout shared with cat/dog/raccoon. Reuses the `cat-*-lower`
 * lower-leg namespace on purpose: only one animal renders per <animal-svg>
 * element, so there is no class collision, and the knee-fold / knee-flex
 * walking + curling animations fire for free with no edit to animal-svg.js.
 *
 * Palette note: Mittens' coat, markings and white are BAKED IN as literal
 * hsl() values in the parts below — deliberately NON-themeable, so the tribute
 * stays true to the real cat regardless of the active theme. 
 * Both override layers are intentionally ignored: global (--evcc-animal-fur)
 * and per-animal (--evcc-animal-mittens-fur) alike.
 * The eye is the one exception: it stays on
 * the --animal-eye token because the battery-state system recolours it
 * (good / mid / warn / low / charging).
 *
 * Caveat: the theme editor still lists Mittens' palette tokens (fur, nose, …)
 * because that list is a fixed 14-suffix template in
 * src/theme-tokens/animals.js, not derived from this colors block. For Mittens
 * those baked entries are inert no-ops; only the eye tokens are live. To make
 * the editor omit them, drive PER_ANIMAL_SUFFIXES from the live colors block.
 */
(function () {
  // Baked, non-themeable identity palette (literal hsl — see header note).
  const FUR = 'hsl(32 24% 55%)';
  const FUR_S = 'hsl(28 22% 43%)';
  const FUR_H = 'hsl(36 28% 70%)';
  const STRIPE = 'hsl(22 30% 24%)';
  const PUP = 'hsl(25 35% 13%)';
  const NOSE = 'hsl(352 52% 73%)';
  const WHISK = 'hsl(42 24% 95%)';
  const EAR = 'hsl(14 38% 60%)';
  const WHITE = 'hsl(38 30% 95%)';
  // The eye stays dynamic so the battery-state system can recolour it.
  const EYE = 'hsl(var(--animal-eye))';

  AnimalSVG.register('mittens', {
    label: 'Mittens',
    type: 'quadruped',
    // Only the eye is declared here — everything else is baked into the parts
    // as literal hsl() and is intentionally not theme-overridable. The eye base
    // feeds the no-battery-attribute case; battery-state bands override it.
    colors: {
      '--animal-eye': '98 40% 42%',
    },
    parts: {
      body: `
        <path d="M145,160 C155,145 180,135 210,132 C240,130 280,130 310,135 C330,138 345,148 348,162 C350,175 345,190 335,198 C320,208 290,212 260,212 C230,212 190,210 170,205 C155,200 142,185 145,160 Z" fill="${FUR}"/>
        <path d="M180,140 C220,134 280,134 320,140 C335,144 342,152 344,162" stroke="${FUR_H}" stroke-width="3" fill="none" opacity="0.4"/>
        <path d="M178,143 C220,136 285,137 330,146" stroke="${STRIPE}" stroke-width="4" fill="none" opacity="0.45" stroke-linecap="round"/>
        <g fill="none" stroke="${STRIPE}" stroke-width="5" stroke-linecap="round" opacity="0.5">
          <path d="M178,172 C182,158 198,152 212,159"/>
          <path d="M180,186 C186,169 205,163 221,172"/>
        </g>
        <g opacity="0.6" stroke="${STRIPE}" stroke-width="6.5" fill="none" stroke-linecap="round">
          <path d="M234,137 Q233,166 240,191"/>
          <path d="M256,136 Q256,167 262,192"/>
          <path d="M278,137 Q279,166 285,190"/>
          <path d="M298,139 Q301,164 306,186"/>
        </g>
        <g opacity="0.45" stroke="${STRIPE}" stroke-width="5" fill="none" stroke-linecap="round">
          <path d="M316,148 Q319,165 318,180"/>
          <path d="M328,150 Q331,163 330,176"/>
        </g>
        <path d="M148,178 C140,191 142,208 158,213 C173,217 185,210 186,196 C186,185 177,176 165,174 C158,174 151,175 148,178 Z" fill="${WHITE}"/>
        <path d="M150,155 C148,152 146,150 144,149 C141,148 140,150 141,153 C142,156 146,160 150,162" fill="${FUR}"/>
      `,
      frontLeftLeg: `
        <g>
          <line x1="166" y1="200" x2="170" y2="236" stroke="${FUR}" stroke-width="13" stroke-linecap="round"/>
          <line x1="166" y1="212" x2="169" y2="215" stroke="${STRIPE}" stroke-width="13" opacity="0.28"/>
          <g class="cat-fl-lower" style="transform-origin: 170px 236px">
            <line x1="170" y1="236" x2="172" y2="270" stroke="${FUR}" stroke-width="11" stroke-linecap="round"/>
            <line x1="170" y1="250" x2="172" y2="276" stroke="${WHITE}" stroke-width="11" stroke-linecap="round"/>
            <ellipse cx="172" cy="278" rx="11" ry="5" fill="${WHITE}"/>
          </g>
          <circle cx="170" cy="236" r="6" fill="${FUR}"/>
        </g>
      `,
      frontRightLeg: `
        <g>
          <line x1="194" y1="200" x2="198" y2="236" stroke="${FUR_S}" stroke-width="13" stroke-linecap="round"/>
          <line x1="194" y1="212" x2="197" y2="215" stroke="${STRIPE}" stroke-width="13" opacity="0.28"/>
          <g class="cat-fr-lower" style="transform-origin: 198px 236px">
            <line x1="198" y1="236" x2="200" y2="270" stroke="${FUR_S}" stroke-width="11" stroke-linecap="round"/>
            <line x1="198" y1="250" x2="200" y2="276" stroke="${WHITE}" stroke-width="11" stroke-linecap="round"/>
            <ellipse cx="200" cy="278" rx="11" ry="5" fill="${WHITE}"/>
          </g>
          <circle cx="198" cy="236" r="6" fill="${FUR_S}"/>
        </g>
      `,
      backLeftLeg: `
        <g>
          <path d="M295,195 C290,205 290,220 298,235 L308,235 C310,220 308,205 305,195 Z" fill="${FUR}"/>
          <g class="cat-bl-lower" style="transform-origin: 303px 234px">
            <line x1="303" y1="234" x2="312" y2="270" stroke="${FUR}" stroke-width="11" stroke-linecap="round"/>
            <line x1="309" y1="258" x2="312" y2="276" stroke="${WHITE}" stroke-width="11" stroke-linecap="round"/>
            <ellipse cx="312" cy="278" rx="10.5" ry="4.5" fill="${WHITE}"/>
          </g>
          <circle cx="303" cy="234" r="6.5" fill="${FUR}"/>
        </g>
      `,
      backRightLeg: `
        <g>
          <path d="M322,192 C318,202 318,217 326,233 L336,233 C338,217 336,202 332,192 Z" fill="${FUR_S}"/>
          <g class="cat-br-lower" style="transform-origin: 330px 232px">
            <line x1="330" y1="232" x2="339" y2="270" stroke="${FUR_S}" stroke-width="11" stroke-linecap="round"/>
            <line x1="336" y1="258" x2="339" y2="276" stroke="${WHITE}" stroke-width="11" stroke-linecap="round"/>
            <ellipse cx="339" cy="278" rx="10.5" ry="4.5" fill="${WHITE}"/>
          </g>
          <circle cx="330" cy="232" r="6.5" fill="${FUR_S}"/>
        </g>
      `,
      tail: `
        <path d="M345,170 C355,160 368,140 375,118 C380,100 378,82 372,75 C368,70 364,72 363,78 C362,85 365,98 366,108" stroke="${FUR}" stroke-width="8" fill="none" stroke-linecap="round"/>
        <path d="M351,162 C354,157 356,152 357,148" stroke="${STRIPE}" stroke-width="8" fill="none" stroke-linecap="round" opacity="0.5"/>
        <path d="M369,140 C371,135 372,130 372,126" stroke="${STRIPE}" stroke-width="8" fill="none" stroke-linecap="round" opacity="0.55"/>
        <path d="M378,112 C379,106 379,100 377,96" stroke="${STRIPE}" stroke-width="8" fill="none" stroke-linecap="round" opacity="0.55"/>
        <path d="M372,75 C368,70 364,72 363,78 C362,85 364,93 365,99" stroke="${STRIPE}" stroke-width="8" fill="none" stroke-linecap="round"/>
      `,
      head: `
        <path d="M112,135 C107,120 112,100 124,93 C132,88 142,85 152,87 C162,89 170,95 174,105 C178,115 178,130 172,140 C167,148 160,153 150,155 C140,157 130,155 122,150 C117,147 113,142 112,135 Z" fill="${FUR}"/>
        <path d="M110,137 C106,145 108,153 116,155 C120,156 122,153 120,148 C118,143 112,140 110,137 Z" fill="${FUR}"/>
        <path d="M170,135 C174,141 174,149 168,153 C164,155 160,153 162,148 C164,143 168,139 170,135 Z" fill="${FUR}"/>
        <path d="M118,105 C114,87 108,65 107,53 C106,45 109,41 114,45 C120,51 126,69 128,87" fill="${FUR}"/>
        <path d="M108,56 C106,46 109,42 113,46 C117,50 119,58 118,66 Z" fill="${STRIPE}" opacity="0.6"/>
        <path d="M114,75 C112,65 110,55 112,49 C114,45 117,47 118,52 C120,59 120,69 120,79" fill="${EAR}"/>
        <path d="M160,87 C162,69 168,51 174,45 C179,41 182,45 181,53 C180,65 174,87 170,105" fill="${FUR}"/>
        <path d="M180,56 C182,46 179,42 175,46 C171,50 169,58 170,66 Z" fill="${STRIPE}" opacity="0.6"/>
        <path d="M166,79 C168,69 170,59 172,52 C173,47 176,45 177,49 C178,55 176,65 174,75" fill="${EAR}"/>
        <path d="M125,139 C122,150 132,159 144,160 C156,159 166,150 163,139 C156,151 132,151 125,139 Z" fill="${WHITE}" opacity="0.96"/>
        <g stroke="${STRIPE}" stroke-width="3" fill="none" stroke-linecap="round" opacity="0.72">
          <path d="M128,108 C129,98 129,90 127,82"/>
          <path d="M137,108 C137,97 136,88 135,80"/>
          <path d="M145,107 C146,97 147,89 148,81"/>
          <path d="M154,108 C155,99 156,91 158,84"/>
        </g>
        <path d="M122,116 C124,108 137,106 143,113" stroke="${FUR_H}" stroke-width="2" fill="none" opacity="0.55"/>
        <path d="M147,113 C153,106 166,108 168,116" stroke="${FUR_H}" stroke-width="2" fill="none" opacity="0.55"/>
        <path d="M122,113 C114,111 108,111 104,114" stroke="${STRIPE}" stroke-width="2.5" fill="none" stroke-linecap="round" opacity="0.55"/>
        <path d="M160,113 C168,111 174,111 178,114" stroke="${STRIPE}" stroke-width="2.5" fill="none" stroke-linecap="round" opacity="0.55"/>
        <path d="M118,127 C115,133 114,139 115,145" stroke="${STRIPE}" stroke-width="2.8" fill="none" stroke-linecap="round" opacity="0.5"/>
        <path d="M127,131 C125,137 124,143 126,149" stroke="${STRIPE}" stroke-width="2.8" fill="none" stroke-linecap="round" opacity="0.45"/>
        <path d="M164,127 C167,133 168,139 167,145" stroke="${STRIPE}" stroke-width="2.8" fill="none" stroke-linecap="round" opacity="0.5"/>
        <path d="M155,131 C157,137 158,143 156,149" stroke="${STRIPE}" stroke-width="2.8" fill="none" stroke-linecap="round" opacity="0.45"/>
      `,
      eyes: `
        <path d="M124,117 C128,110 138,110 142,117 C138,124 128,124 124,117 Z" fill="${EYE}"/>
        <ellipse cx="133" cy="117" rx="2.2" ry="5.5" fill="${PUP}"/>
        <circle cx="136" cy="115" r="1.8" fill="${WHITE}" opacity="0.85"/>
        <path d="M148,117 C152,110 162,110 166,117 C162,124 152,124 148,117 Z" fill="${EYE}"/>
        <ellipse cx="157" cy="117" rx="2.2" ry="5.5" fill="${PUP}"/>
        <circle cx="160" cy="115" r="1.8" fill="${WHITE}" opacity="0.85"/>
      `,
      face: `
        <path d="M145,120 L145,130" stroke="${STRIPE}" stroke-width="2" stroke-linecap="round" opacity="0.45"/>
        <path d="M139,130 L151,130 L145,138 Z" fill="${NOSE}"/>
        <path d="M145,138 C145,142 142,144 138,144" stroke="${STRIPE}" stroke-width="1" fill="none" opacity="0.6"/>
        <path d="M145,138 C145,142 148,144 152,144" stroke="${STRIPE}" stroke-width="1" fill="none" opacity="0.6"/>
        <line x1="120" y1="127" x2="78" y2="119" stroke="${WHISK}" stroke-width="0.9" opacity="0.8"/>
        <line x1="120" y1="131" x2="74" y2="131" stroke="${WHISK}" stroke-width="0.9" opacity="0.8"/>
        <line x1="120" y1="135" x2="78" y2="144" stroke="${WHISK}" stroke-width="0.9" opacity="0.8"/>
        <line x1="168" y1="127" x2="210" y2="119" stroke="${WHISK}" stroke-width="0.9" opacity="0.8"/>
        <line x1="168" y1="131" x2="214" y2="131" stroke="${WHISK}" stroke-width="0.9" opacity="0.8"/>
        <line x1="168" y1="135" x2="210" y2="144" stroke="${WHISK}" stroke-width="0.9" opacity="0.8"/>
      `,
      warning: `
        <g>
          <line x1="155" y1="152" x2="150" y2="134" stroke="${FUR}" stroke-width="2.5" stroke-linecap="round"/>
          <line x1="170" y1="142" x2="166" y2="123" stroke="${FUR}" stroke-width="2.5" stroke-linecap="round"/>
          <line x1="188" y1="135" x2="185" y2="116" stroke="${FUR}" stroke-width="2.5" stroke-linecap="round"/>
          <line x1="208" y1="131" x2="206" y2="112" stroke="${FUR}" stroke-width="2.5" stroke-linecap="round"/>
          <line x1="230" y1="130" x2="229" y2="111" stroke="${FUR}" stroke-width="2.5" stroke-linecap="round"/>
          <line x1="252" y1="130" x2="252" y2="111" stroke="${FUR}" stroke-width="2.5" stroke-linecap="round"/>
          <line x1="274" y1="131" x2="275" y2="112" stroke="${FUR}" stroke-width="2.5" stroke-linecap="round"/>
          <line x1="295" y1="133" x2="298" y2="115" stroke="${FUR}" stroke-width="2.5" stroke-linecap="round"/>
          <line x1="314" y1="138" x2="319" y2="120" stroke="${FUR}" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M107,53 C106,45 109,41 114,45 C117,48 119,54 118,62 Z" fill="${FUR_S}" opacity="0.7"/>
          <path d="M181,53 C182,45 179,41 174,45 C171,48 170,54 171,62 Z" fill="${FUR_S}" opacity="0.7"/>
          <circle cx="133" cy="117" r="5" fill="${PUP}"/>
          <circle cx="157" cy="117" r="5" fill="${PUP}"/>
        </g>
      `,
    },
  });
})();
