# Voice Assist — guided clean wizard (DESIGN)

> **Status: DESIGN — not yet implemented.** This is the design-first artifact for the
> room-level voice feature. No code exists yet; nothing here is wired. Decisions and
> file/symbol references must be **re-confirmed against current code at implementation
> time** (verify-vs-code rule). Authored 2026-06-28.

## 1. Goal

Drive the existing "configure a clean" flow over **Home Assistant Assist voice** as a
**guided, multi-turn dialog** — and, as a complementary quick path, a one-shot
"clean the kitchen" command.

**The end-goal transcript:**

```
User: Configure vacuum.
VA:   Which vacuum?
User: Alfred.
VA:   Which room?
User: Kitchen.
VA:   What mode?
User: Vacuum and mop.
VA:   What suction?
User: Heavy.
VA:   What water level?
User: Low.
VA:   How many passes?
User: Two.
VA:   Clean kitchen with heavy suction, low water, two passes?
User: Yes.
→ executes the existing room-clean dispatch.
```

**Two complementary paths (ship both, independently):**

| | Path A — **Guided wizard** (this doc's focus) | Path B — **One-shot** |
|---|---|---|
| Phrase | "Configure vacuum" → walked through | "Clean the kitchen" |
| Mechanism | custom `ConversationEntity` + `continue_conversation` | native `vacuum.clean_area` segments |
| LLM | **none required** (fully deterministic) | none required |
| Needs a vacuum entity? | **No** — it's a conversation entity calling the existing service | **Yes** — `CLEAN_AREA` rides a `VacuumEntity` |
| Status | design (here) | separate; see §10 |

Path A is the differentiator and has **no upstream blocker**, so it leads.

## 2. Why this is deterministic (no LLM)

Verified against the installed HA core **2026.5.3**. The entire multi-turn loop is carried
by **two fields** on what a conversation agent returns each turn
(`conversation.ConversationResult`):

- **`continue_conversation=True`** — the assist pipeline keeps the satellite mic open
  **and** pins `continue_conversation_agent = <our agent_id>`. On the next turn,
  `prepare_recognize_intent` sets `_intent_agent_only=True` and **routes the utterance
  straight back to our `async_process`** — bypassing the default/hassil agent, intent
  matching, and any LLM. (`assist_pipeline/pipeline.py`.)
- **`conversation_id`** — echoed back so the turns correlate into one session.

So once the wizard engages, every answer ("Alfred", "Kitchen", "Heavy", "Two", "Yes")
lands in **our** code, and **we** choose the next question. No LLM anywhere in the loop.

**Why it must be a custom agent:** the built-in hassil agent cannot slot-fill — an
unmatched slot returns a terminal `NO_VALID_TARGETS` error, never a follow-up question
(`conversation/default_agent.py`). `IntentResponse.async_set_reprompt` is legacy Almond
plumbing and is **not** consumed by the pipeline. A wizard therefore *must* be a custom
conversation agent — which is exactly what gives us full control of the flow.

**Version floor:** `continue_conversation` + pipeline mic-reopen landed in HA **2025.4**
(present in 2026.5.3). The mic auto-reopens only on **voice satellites** (ESPHome Voice PE
etc.); over plain `conversation.process` REST/WS there is no mic and the caller re-prompts
with the same `conversation_id`.

## 3. Architecture

A single new **`ConversationEntity`** exposed by the integration, acting as a **transparent
wrapper**:

- It is selected as the user's Assist **pipeline conversation agent**.
- Anything that is **not** our entry phrase and **not** a mid-wizard answer is delegated
  straight to the default HA agent (`conversation.async_converse(..., agent_id=
  conversation.HOME_ASSISTANT_AGENT)`), so the same pipeline still answers "turn off the
  lights". The wrapper is invisible except while configuring a clean.
- The entry phrase ("configure vacuum"/…) starts a wizard; from then on
  `continue_conversation` force-routes every follow-up to us until the final "Yes"/"No".

In-progress state lives in **our own dict keyed by `conversation_id`** —
`self._wizards: dict[str, WizardState]` — **not** in `ChatLog` (ChatLog derives
`continue_conversation` from a trailing "?", which we want to control explicitly). HA's
`ChatSession` TTL is **5 minutes**; we register `session.async_on_cleanup(...)` to drop an
abandoned wizard and mirror that TTL on our dict.

### 3.1 The one wiring decision

How the **first** "Configure vacuum" reaches our agent (follow-ups are auto-pinned; the
entry utterance is not):

- **Recommended — transparent wrapper as the pipeline agent.** User picks our entity as
  the pipeline's conversation agent; it delegates non-wizard utterances to the default
  agent. One pipeline does everything.
- **Alternative — dedicated wizard pipeline** whose agent is our entity (no delegation
  needed, but a separate pipeline the user must switch to).

We document the wrapper pattern as default. (See §14 Q1.)

## 4. The state machine

The wizard's steps map **1:1** to the panel's existing configure-a-clean flow. The slot
sequence and the valid values per slot are **data-driven by the adapter config** (so each
brand asks for its own vocabulary), not hard-coded:

```
ENTRY → ASK_VACUUM → ASK_ROOM → ASK_MODE → ASK_SUCTION → ASK_WATER → ASK_PASSES → CONFIRM
            │            │           │            │            │            │          │
         (skip if     (canonical  (adapter    (adapter     (skip if     (skip if    yes→EXECUTE
          single       room key)   modes)      suction)     mode has     vacuum      no →CANCEL
          vacuum)                                            no mop)      lacks       /EDIT)
                                                                          passes)
```

- **Conditional slots.** Water level is asked only when the chosen mode involves mopping;
  passes only when the vacuum supports it. The adapter declares which slots apply.
- **Per-slot vocabulary + parsing.** The valid answers for each slot come from the
  **adapter's `vocabulary`** for the chosen vacuum. Each spoken answer is normalized with
  the **existing brand-vocab normalization** (the alias maps already used by the card —
  see [25-eufy-adapter](25-eufy-adapter.md) and the `vocabulary` block in
  [22-adapter-config-reference](22-adapter-config-reference.md)). "heavy" → the adapter's
  max-suction code; "two" → `2` (number-word parse); "vacuum and mop" → the mop mode code.
- **Re-prompt on miss.** If an answer doesn't normalize to a valid slot value, re-ask with
  the options ("I didn't catch that — what suction? You can say quiet, standard, turbo,
  or max."). No silent guessing.
- **Cancel anywhere.** "cancel"/"stop"/"never mind" → abort, drop the wizard, return
  `continue_conversation=False`.

### 4.1 `WizardState`

```python
@dataclass
class WizardState:
    step: Step                      # current slot being asked
    vacuum_id: str | None = None    # VA-managed vacuum identity
    room: str | None = None         # canonical room key (not a display name)
    mode: str | None = None         # canonical mode code
    suction: str | None = None      # canonical suction code
    water: str | None = None        # canonical water code (None if no mop)
    passes: int | None = None
    language: str = "en"
```

Slots are stored as **canonical codes**, never display strings — consistent with the
no-fabricated-display-name contract (see [frontend/i18n-system](frontend/i18n-system.md) and the
standing "no string without i18n" rule). The read-back composes localized labels from
those codes via the existing `tVocab`-equivalent on the server side.

## 5. Code sketch (skeleton only)

```python
# custom_components/eufy_vacuum/conversation.py   (DESIGN sketch — not final)
from __future__ import annotations
from typing import Literal
from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL, Platform
from homeassistant.helpers import intent
from homeassistant.helpers.chat_session import async_get_chat_session

ENTRY_PHRASES = {"configure vacuum", "configure the vacuum", "configure a clean"}

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([VacuumWizardConversationEntity(hass, entry)])

class VacuumWizardConversationEntity(conversation.ConversationEntity):
    _attr_has_entity_name = True
    _attr_name = "Vacuum wizard"

    def __init__(self, hass, entry):
        self.hass = hass
        self._entry = entry
        self._wizards: dict[str, WizardState] = {}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def async_process(self, user_input: conversation.ConversationInput
                            ) -> conversation.ConversationResult:
        with async_get_chat_session(self.hass, user_input.conversation_id) as session:
            cid = session.conversation_id
            text = user_input.text.strip()
            wiz = self._wizards.get(cid)

            # transparent wrapper: not our wizard, not our entry phrase → default agent
            if wiz is None and text.lower() not in ENTRY_PHRASES:
                return await conversation.async_converse(
                    hass=self.hass, text=user_input.text, conversation_id=cid,
                    context=user_input.context, language=user_input.language,
                    agent_id=conversation.HOME_ASSISTANT_AGENT,
                    device_id=user_input.device_id, satellite_id=user_input.satellite_id,
                )

            if wiz is None:                                  # start wizard
                wiz = self._wizards[cid] = self._new_wizard(user_input)
                session.async_on_cleanup(lambda: self._wizards.pop(cid, None))
                prompt, done = self._first_prompt(wiz)
            else:                                            # advance one step
                prompt, done = self._advance(wiz, text)      # ← existing state machine
                if done:
                    if wiz.confirmed:
                        await self._execute(wiz)             # ← existing room_clean dispatch
                    self._wizards.pop(cid, None)

            resp = intent.IntentResponse(language=user_input.language)
            resp.async_set_speech(prompt)                    # ← localized (i18n)
            return conversation.ConversationResult(
                response=resp, conversation_id=cid, continue_conversation=not done,
            )
```

`_advance`, `_first_prompt`, `_execute`, and the prompt strings are the only real work —
and each maps onto something that already exists (§7).

## 6. Wiring / file layout

- `custom_components/eufy_vacuum/conversation.py` — the entity + `async_setup_entry`.
- `manifest.json` — add `"dependencies": ["conversation"]`.
- main `async_setup_entry` — `await hass.config_entries.async_forward_entry_setups(entry,
  [Platform.CONVERSATION])`.
- The dialog logic should live in a small `voice/` module (state machine + answer parsing
  + prompt building), keeping `conversation.py` thin — consistent with the
  bundled-subsystem pattern used elsewhere in the codebase.

## 7. What already exists (the reason this is ~80% built)

| Wizard need | Reuses |
|---|---|
| Dialog steps (vacuum→room→mode→suction→water→passes→confirm) | the panel's existing configure-a-clean state machine |
| Answer parsing ("heavy"→suction code, "two"→2, "vacuum and mop"→mode code) | the **brand-vocab normalization / alias maps** already used by the card |
| Per-slot valid values | the adapter `vocabulary` block (brand-agnostic) |
| Prompts + read-back in the user's language | the **i18n contract** — every prompt is a key; the wizard speaks all 7 locales for free |
| Execute on "Yes" | the existing `send_command` room-clean dispatch |

## 8. i18n — new keys

All prompts are user-facing strings → keyed at creation (no-string-without-i18n). Proposed
namespace `voice.wizard.*` (dot-keyed per convention), with placeholders:

```
voice.wizard.ask_vacuum        "Which vacuum?"
voice.wizard.ask_room          "Which room?"
voice.wizard.ask_mode          "What mode?"
voice.wizard.ask_suction       "What suction?"
voice.wizard.ask_water         "What water level?"
voice.wizard.ask_passes        "How many passes?"
voice.wizard.confirm           "Clean {room} with {suction} suction, {water} water, {passes} passes?"   // plural on passes
voice.wizard.confirm_no_water  "Clean {room} with {suction} suction, {passes} passes?"                  // mop-less
voice.wizard.starting          "Starting now."
voice.wizard.cancelled         "Okay, cancelled."
voice.wizard.didnt_catch       "I didn't catch that. {prompt} You can say {options}."
voice.wizard.no_rooms          "I don't have any rooms set up for {vacuum} yet."
voice.wizard.which_vacuum_unknown "I don't have a vacuum called {name}."
```

These are **+7 locales** under the standing i18n contract; ship English at creation, the
rest AI-drafted + native-reviewable as usual. The slot *values* (suction/mode/water) reuse
the existing `vocab.*` keys — no new value keys.

## 9. Edge cases / gotchas

- **5-minute session TTL** — a user who pauses mid-wizard past 5 min loses the
  `conversation_id`; drop the `WizardState` on `session.async_on_cleanup` and keep prompts
  snappy.
- **Voice-satellite requirement** — mic auto-reopen needs a satellite/pipeline (2025.4+);
  text/REST callers must re-prompt. Document this.
- **Single vs multi vacuum** — skip `ASK_VACUUM` when only one VA-managed vacuum exists;
  otherwise match the spoken name against managed vacuums (re-prompt on unknown).
- **No rooms configured** — abort early with `voice.wizard.no_rooms`.
- **Invalid answer** — re-prompt with options; never silently default.
- **Concurrency** — wizards are isolated by `conversation_id`; multiple satellites can run
  independent wizards.
- **Interruptions / overlap with Path B** — keep entry phrases for the wizard ("configure
  …") distinct from the one-shot ("clean …") so they never collide.

## 10. Path B — one-shot `clean_area` (complementary, separate)

The native HA 2026.3 segment API (`VacuumEntityFeature.CLEAN_AREA` + `Segment` +
`async_get_segments` / `async_clean_segments`) gives "clean the kitchen" with defaults on
**free offline Assist and any LLM**, no custom sentences. **But** it rides a `VacuumEntity`,
which we don't own (we're a supervisory `service` integration). Open decision for Path B
(does **not** block Path A): add `CLEAN_AREA` upstream to the now-mainline eufy-clean
entity (a contribution) **or** expose a thin proxy vacuum entity that delegates to our
dispatch. Roborock may get it nearly free upstream. Eufy `clean_area` is global-only, so
`async_clean_segments` routes through the per-room `send_command` path. Full notes in the
reference memory (see §15).

## 11. Phasing (waves — not a rewrite)

- **Wave 0** — this design + approval pause.
- **Wave 1 (MVP, Eufy, English).** Transparent-wrapper `ConversationEntity`; core slots
  (room→mode→suction→water→passes→confirm→execute) for the **default/single vacuum**;
  conditional water-skip; re-prompt on miss; cancel; `voice.wizard.*` keys (English at
  creation). Unit-tested by simulating turns. *No multi-vacuum, no LLM, no Path B.*
- **Wave 2.** Multi-vacuum selection; fully adapter-driven slots/vocab so **Roborock**
  works; edit-on-"No"; the 7-locale translation pass.
- **Wave 3.** Path B (one-shot `clean_area`) + the proxy-entity decision.
- **Wave 4 (optional).** LLM answer-normalization for free-form answers ("make it
  thorough" → max passes) layered *on top* of the deterministic flow; proactive start via
  `assist_satellite.start_conversation`.

## 12. Testing

The entity logic is **pure and testable without voice hardware** (the force-routing is
pipeline-side). Drive `async_process` with a scripted sequence of `ConversationInput`
(same `conversation_id`), assert each `ConversationResult.response` speech + the
`continue_conversation` flag, and assert the final dispatch payload against a mocked
send-path. Cover: happy path, re-prompt, cancel, mop-less skip, unknown vacuum/room,
TTL-drop. Gate: `pytest --no-cov` (behavior), per the testing convention.

## 13. Non-goals (for now)

- Replacing the panel UI (voice is an *additional* surface).
- Arbitrary free-form NLU (we enumerate known vacuums/rooms/modes; free-form is Wave 4
  LLM territory).
- Editing saved profiles by voice / a full conversational profile manager (later).

## 14. Open questions / decisions for review

1. **Entry wiring** — document the transparent-wrapper-as-pipeline-agent as default, or
   the dedicated pipeline? (Leaning wrapper.)
2. **Enablement** — auto-create the `ConversationEntity` (opt-out) or opt-in setting?
3. **Conditional slots** — should the adapter explicitly declare slot applicability
   (water-iff-mop, passes-iff-supported), or infer from the existing capability flags?
4. **Single-vacuum skip** — auto-skip `ASK_VACUUM` when one vacuum, or always confirm?
5. **"No" at confirm** — restart, or re-prompt only the slot the user wants to change
   (needs a "change the suction" mini-grammar)?
6. **Path B** — proxy vacuum entity vs upstream eufy-clean contribution (Wave 3).

## 15. References

- HA conversation models — `ConversationEntity`, `ConversationResult(response,
  conversation_id, continue_conversation)`:
  `homeassistant/components/conversation/{entity,models}.py`.
- The force-routing of follow-ups: `homeassistant/components/assist_pipeline/pipeline.py`.
- Default agent has no slot-filling: `homeassistant/components/conversation/default_agent.py`.
- Session TTL (5 min) + ULID `conversation_id`: `homeassistant/helpers/chat_session.py`.
- HA 2025.4 "continue conversation" release notes; HA 2026.3 `clean_area`/`Segment` release
  notes.
- Internal: the verified mechanism + the one-shot path are also captured in the project
  memory (`ha-conversation-agent-multiturn`, `ha-vacuum-clean-area-segments`,
  `voice-room-control`).
