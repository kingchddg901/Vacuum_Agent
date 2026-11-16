/**
 * [CDN-*] THE DENSITY TOKENS INHERIT FROM THE PANEL.
 *
 * Chris's ruling, 2026-11-16: "key by the card it works on with inheritance setting
 * from the panel." That is a THREE-RUNG chain, written at every site as
 *
 *     var(--evcc-card-<thing>, var(--evcc-<panel equivalent>, <the card's literal>))
 *
 * and all three rungs have to be shown, because each one fails differently:
 *   - neither set   -> the card's own shipped pixel. Gets this wrong and every
 *                      existing install moves on upgrade.
 *   - panel set     -> the card FOLLOWS it. This is the rung the ruling is about, and
 *                      it is the one a default-only test cannot see at all.
 *   - card set      -> the card WINS. Without this the card token is decorative.
 *
 * A test that only checks the default proves the chain COMPILES, not that it inherits.
 * The first two rungs render identically in a screenshot when the middle one is broken,
 * because a broken middle rung just falls through to the same literal.
 *
 * WHY A BROWSER. This is CSS custom-property cascade resolution. A source assertion can
 * check the chain is spelled right; only a real mounted card can check it resolves right,
 * and the spelling is the part that was never in doubt.
 *
 * Coverage
 * --------
 * [CDN-1] neither token set  -> the card's own literal
 * [CDN-2] the PANEL token set -> the card follows it
 * [CDN-3] the CARD token set  -> it beats the panel
 * [CDN-4] the action glow reaches all three primary actions, not one card of three
 */
import { test, expect } from "@playwright/test";
import { mountHarness } from "../lib/mount-page.mjs";

/** Mount the real room card standalone and read its density through the chain. */
async function densityChain(page) {
  await mountHarness(page);
  return page.evaluate(async () => {
    await window.__evcc.mountCard("room", {});
    const card = document.querySelector("eufy-room-card");
    const read = () => ({
      header: getComputedStyle(card.shadowRoot.querySelector(".header")).padding,
      fieldGap: getComputedStyle(card.shadowRoot.querySelector(".field-group")).rowGap,
    });
    const out = { neither: read() };
    // rung 2 — the PANEL's own tokens, nothing card-specific
    card.style.setProperty("--evcc-card-padding", "30px");
    card.style.setProperty("--evcc-card-gap", "21px");
    out.panelOnly = read();
    // rung 3 — the card's tokens on top
    card.style.setProperty("--evcc-card-header-padding", "7px 9px");
    card.style.setProperty("--evcc-card-field-gap", "13px");
    out.cardWins = read();
    return out;
  });
}

test("[CDN-1] with neither token set the card keeps its own literal", async ({ page }) => {
  // THE RED INPUT: change any site's final fallback. EVERY existing install renders
  // from this rung, so it is the one that must not move on upgrade.
  const r = await densityChain(page);
  expect(r.neither.header).toBe("14px 16px 12px");
  expect(r.neither.fieldGap).toBe("6px");
});

test("[CDN-2] with only the PANEL token set the card follows it", async ({ page }) => {
  // THE RED INPUT: drop the MIDDLE var() -- read
  // `var(--evcc-card-header-padding, 14px 16px 12px)` with no panel rung.
  // [CDN-1] and [CDN-3] both still pass on that: the default still paints and the card
  // token still wins. This rung is the ruling itself ("inheritance setting from the
  // panel") and it is invisible to every other assertion here, which is why it is its
  // own test rather than a third expect() in a shared one.
  const r = await densityChain(page);
  expect(r.panelOnly.header, "must inherit --evcc-card-padding").toBe("30px");
  expect(r.panelOnly.fieldGap, "must inherit --evcc-card-gap").toBe("21px");
});

test("[CDN-3] the card token beats the panel token", async ({ page }) => {
  // THE RED INPUT: swap the chain's order, so the panel wins and the card-specific
  // control does nothing -- silently, because the panel value is a plausible render.
  const r = await densityChain(page);
  expect(r.cardWins.header).toBe("7px 9px");
  expect(r.cardWins.fieldGap).toBe("13px");
});

test("[CDN-4] the action glow reaches all three primary actions", async ({ page }) => {
  // THE RED INPUT: remove the box-shadow declaration from room-card or dashboard-card's
  // .btn-start. Only the profile card's Run shipped a halo; the other two had no
  // box-shadow at all, and a div's initial value is already `none` — so a fix that
  // edited only the card that HAS the glow would give a control moving one card of
  // three, with every existing test green. The same 1-declaration-plus-2-absences shape
  // as the frame shadow in docs/dev/00c-replicas.md RNA0TM68.
  await mountHarness(page);
  const seen = await page.evaluate(async () => {
    const out = {};
    for (const id of ["room", "dashboard", "profile"]) {
      await window.__evcc.mountCard(id, {});
      const el = document.querySelector(
        id === "room" ? "eufy-room-card"
          : id === "dashboard" ? "vacuum-agent-dashboard" : "vacuum-agent-profile-card");
      if (!el) { out[id] = "card did not mount"; continue; }
      el.style.setProperty("--evcc-card-action-glow", "0 0 11px rgb(0, 255, 0)");
      // SETTLE before reading. The dashboard card's .btn carries `transition: all`,
      // so box-shadow ANIMATES from `none` and reads as the transparent zero-shadow
      // `rgba(0,0,0,0) 0px 0px 0px 0px` on the first frame -- which looks exactly like
      // a token that never arrived. Read at t=0 and this test fails on the one card
      // whose button happens to transition, for a reason unrelated to the token.
      await new Promise((res) => setTimeout(res, 200));
      const btn = el.shadowRoot.querySelector(".btn-start, .evcc-pcard-run");
      out[id] = btn ? getComputedStyle(btn).boxShadow : "no primary action found";
    }
    return out;
  });
  for (const id of ["room", "dashboard", "profile"]) {
    expect(seen[id], `${id}: its primary action must read --evcc-card-action-glow`)
      .toContain("0, 255, 0");
  }
});

test("[CFS-1] font scale 1 is byte-identical, and the scale holds every ratio", async ({ page }) => {
  // HIS RULING: "i like the font sizes that are there but users may not ... per item
  // sizes seems excessive but a font scale to hold the diff between them may work well."
  //
  // So this asserts BOTH halves, and the second is the one that distinguishes a
  // multiplier from a step scale:
  //   at 1    -> every size is exactly what shipped. THE RED INPUT: change any literal.
  //   at 1.5  -> every size is x1.5 AND the ratio between any two is unchanged.
  //              THE RED INPUT: wire some sites and not others, or snap sizes onto a
  //              set of fixed steps. Either leaves scale 1 perfect and the spread
  //              non-zero, which is precisely what "holds the diff" rules out.
  //
  // A test that only checked scale 1 would pass on a token nobody wired.
  await mountHarness(page);
  const r = await page.evaluate(async () => {
    await window.__evcc.mountCard("room", {});
    const card = document.querySelector("eufy-room-card");
    const sel = [".room-name", ".chip", ".field-label", ".btn"];
    const read = () => Object.fromEntries(sel.map((s) => {
      const el = card.shadowRoot.querySelector(s);
      return [s, el ? parseFloat(getComputedStyle(el).fontSize) : null];
    }));
    const at1 = read();
    card.style.setProperty("--evcc-card-font-scale", "1.5");
    await new Promise((res) => setTimeout(res, 120));
    return { at1, at15: read() };
  });

  // the sizes that ship, in px at a 16px root -- 0.96/0.82/0.72/0.82 rem
  expect(r.at1[".room-name"]).toBeCloseTo(15.36, 2);
  expect(r.at1[".chip"]).toBeCloseTo(13.12, 2);
  expect(r.at1[".field-label"]).toBeCloseTo(11.52, 2);
  expect(r.at1[".btn"]).toBeCloseTo(13.12, 2);

  const ratios = Object.keys(r.at1)
    .filter((k) => r.at1[k] != null && r.at15[k] != null)
    .map((k) => r.at15[k] / r.at1[k]);
  expect(ratios.length, "no selector rendered -- the probe measured nothing").toBeGreaterThan(3);
  for (const x of ratios) expect(x).toBeCloseTo(1.5, 2);

  // THE DIFF-HOLDING CLAIM, as one number: every selector scaled by the SAME factor.
  const spread = Math.max(...ratios) - Math.min(...ratios);
  expect(spread,
    `every card text size must scale by the same factor; spread ${spread} means some ` +
    `sites are unwired or snapped to steps, which changes the type relationships`)
    .toBeLessThan(0.001);
});
