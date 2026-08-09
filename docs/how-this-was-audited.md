# How this was audited

This integration controls a machine that moves around your home unsupervised, and it stores
things you cannot easily check — how long each room takes, which rooms were cleaned, what
settings were sent. If it gets those wrong, mostly nothing looks wrong. That is the problem
this page is about.

Over six days in mid-2026 the codebase was put through a **hostile audit**: not a review
looking for polish, but a deliberate attempt to break it, on the assumption that the docs
might be wrong, the code might be wrong, the tests might encode the wrong contract, or all
three might agree on the same flawed idea.

| | |
|---|---|
| findings verified | **484** — 18 critical, 88 high, 173 medium, 205 low |
| collapsed into | **33** repair families over 8 structural causes |
| shipped as | **60** repair packets |
| false leads killed | **22** |

Almost none of it came from bug reports. That is the point rather than a boast: the defects
that survive in software like this are the ones nothing surfaces.

---

## What it found: eight causes, not 484 bugs

The findings were not 484 unrelated mistakes. Deduplicated by root cause, they collapsed
into eight ways the code kept being wrong — the same error, made in different places by
different people at different times.

**Absence of evidence, consumed as evidence of absence.** An empty result from a device
that had simply not answered yet was treated as "there is nothing there" — so an empty room
list could wipe saved rooms, and a file that failed to read looked identical to a file that
was empty.

**Protected windows that don't cover their own gate.** Code that carefully guarded a
critical section, but finished the guard just before the step that actually mattered.

**Refusals nobody could see.** The system correctly decided *no*, wrote that decision into
a result… which the next layer dropped. You saw success.

**Identity carried by unstable keys.** Rooms tracked by numbers that change when a map is
re-segmented, or by names with no guarantee of uniqueness.

**Ownership decided by string matching.** "Which entities belong to this vacuum?" answered
by comparing name prefixes — which is fine until two vacuums share one.

**Stale data served as live.** Held or cached values handed to code that acted on them as
current.

**Vocabulary owned by the framework instead of the device.** The core held one brand's
words, so a second brand silently inherited settings its hardware does not accept — the
cause behind most of the "this setting did nothing" fixes in v2.0.0.

**Setup without teardown.** Things registered at startup that nothing removed on reload.

Read that list again and notice what it is not: a list of typos. Each one is a *way of
thinking* that produced many separate bugs, which is why fixing them one at a time would
never have finished.

---

## What it could not do

An audit that only reports what it found is marketing. This one also recorded what it
could not reach, and those limits are published rather than rounded off.

**Most findings were read, not run.** 36 of the 484 carry executed proof; the rest were
verified by two independent people reading the source. That is a real bound, and raising it
is named work for the next campaign rather than a claim already made.

**The image-analysis pipeline is excluded by design.** Whether a room outline is *correct*
is an empirical question about pictures, not a textual one about code. This method cannot
falsify it, so it did not pretend to.

**Some things need hardware nobody has.** A few findings stay open because closing them
requires a second vacuum of the same brand, or a specific model on a bench. They are listed
with exactly what would close them, not quietly aged out.

**Two fixes landed narrower than they were filed**, and are recorded that way rather than
as clean wins — because a ledger that says what actually happened is the only kind worth
keeping.

---

## What changed afterwards

The most durable result was not the fixes. It was learning that **counting is harder than
finding**.

A finding was marked fixed when only half of it was, and a hardware run caught it. Later,
at close-out, the opposite: of 27 items still listed open, 19 had been fixed and never
ticked. A stale ledger manufactures phantom work exactly the way an unaudited subsystem
manufactures false health.

So the rule became: **check the code, not the count** — and not the marker either, since
two of those fixes never named the finding they closed.

That habit is why v2.0.0's release notes can tell you which settings were silently doing
nothing, and why this page can tell you what the audit missed.

---

## Where the detail lives

This page is the short version. The full campaign record — what ran, what it found, what
landed, and the complete list of what remains open with the specific thing that would close
each item — is public:

- **[AUDIT-1 Closeout](https://github.com/kingchddg901/Vacuum_Agent/blob/master/.claude/notes/synthesis/AUDIT-1-CLOSEOUT.md)** — the campaign in full, with every number regenerated from the ledgers at close.
- **[The disaster-recovery standard](dev/00-disaster-recovery-standard.md)** — every backend subsystem graded, held to the rule that a precise-but-unverified statement is worse than silence.

A second campaign is chartered, and its target is this one's output: every repaired seam,
every fix, everything written since. The audit that tore the system down gets audited by
its successor.

---

> **"We found everywhere we can see it bleed and armored it."**

The bound is in the sentence. *Can see* is doing real work — and the exclusions, open
gates and deferrals above are that bound, printed rather than implied.
