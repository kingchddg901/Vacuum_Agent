# Guide-key authoring source

The authored sentences behind the maintenance guides, one file per language, 42 keys each.
`scripts/sync-dreame-guide-keys.py` reads these and writes what ships:
`src/i18n/guide-keys.js` (English, bundled) and
`custom_components/eufy_vacuum/frontend/guides/keys/<lang>.json` (the other 17, served).

**Edit here, then regenerate.** Never hand-edit the outputs; they are overwritten.

```bash
python scripts/sync-dreame-guide-keys.py
```

The generator refuses to write unless every key the backend can emit
(`adapters/dreame/upkeep_keys.py::DREAME_UPKEEP_KEYS`) is present in every pack, so a
missing translation fails loudly here rather than rendering an empty step on someone's card.

## What is in a pack

- **Keys without a leading underscore are the sentences.** Those are the product. Keyed by
  `<family>.<action>` (`filter.remove_and_tap`, `note.no_detergent`), authored in the
  reader's register — imperative, object-free where a key is shared across parts, in the
  card's per-user language. Doc 41 §1c explains how a key reaches a card.
- **Keys with a leading underscore are authoring notes.** The generator strips them; they
  never ship. They record *why* a sentence says what it says — ordering decisions, what was
  deliberately left out, which models a regime covers, and the grammatical register each
  language settled on (`_register`, `_vocabulary`). They are the part a future author needs
  most, which is why they travel with the sentences instead of staying on one machine.

## The provenance line, stated once

Every sentence here was **authored**, written against the hardware and checked against the
manufacturer's manuals — not lifted from them. Where a manual's wording is the right word
for a *part* (dust bin, brush guard, mop pad holder), the notes say so and that word is used
as nomenclature; that is the `_lexicon` / `_vocabulary` rule, and part names are not prose.

The notes **cite** manuals by model and section and **paraphrase** what they say where the
reasoning depends on it. They do not quote them; the passages that did were redacted to
citations when this directory moved into the repository and again in the 2.5.0 pre-release
audit, which found four the first pass missed. The manuals
themselves, the OCR corpus and the derived tables that produced the regimes stay outside
git, deliberately, because they are not ours to host.

This directory is in the repository so the guides remain reproducible without any one
machine. It lived at `durable/dreame-port-fixture/resources/key-authoring/` until
2026-10-22, alongside material that should not be published; only the authored packs moved.

## Locale spelling

The packs spell Chinese as `keys_zh_hans.json` / `keys_zh_hant.json`; the served files are
`zh-Hans.json` / `zh-Hant.json` because the card builds the URL from its resolved language
code. The generator is the only place that seam is crossed.
