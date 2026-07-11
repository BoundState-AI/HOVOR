# Interim Machine Review — ancestry-slice-0.2.0

**Date:** 2026-07-11 · **Reviewer:** Claude (independent of the model that
authored the content) · **Status:** does NOT clear `PENDING_NATIVE_REVIEW`.
This is a second-machine cross-check to make the content safe enough for
daily practice until the in-person native review happens (planned: Prague
trip). A native pass is still the gate before trusting register/naturalness.

## Scope

Full pass over every Slovak string in:
- `lexemes.json` (all 131), `missions.json` (all 3 scripts: every opening,
  elicit, ack, and show_text line), `repair_items.json` (all 5),
  `grammar_notes.json` (learner-facing English — pedagogy check only).

## Errors found and FIXED (applied 2026-07-11, tests green: 81 passed)

| Where | Was | Now | Why |
|---|---|---|---|
| `missions.json` · svaty_jur_family · confirm_identity ack | „Ja to vedela!" | „Ja **som** to vedela!" | Slovak 1st-person past **requires** the auxiliary *som*; dropping it is Czech colloquial interference (cz „já to věděla"), flat-out wrong in Slovak. |
| `missions.json` · modra_archive_records · get_next_step ack | „pýtajte si **rodnú matriku**" | „pýtajte si **matriku narodených**" | "rodná matrika" isn't the term. The register of births is *matrika narodených*; the certificate is *rodný list* (already a lexeme). |

## Nits left for the native reviewer (not fixed — judgment calls)

1. **„Povedzte mi o vašej rodine"** (modra_archive_records · explain_ancestor
   elicit) — prescriptively *o svojej rodine* (reflexive possessive when the
   subject owns it). *o vašej* is common in real speech; native call on
   whether the formal archivist character should model the textbook form.
2. **Lexeme „ujo"** (uncle) — colloquial/Western-Slovak leaning; *strýko* is
   the neutral standard. Fine for teta Marta's informal register; reviewer
   should confirm it matches the family-dialect flavor Joe wants.

## Everything else

Checked and reads correct and natural to this reviewer, including the case
endings the missions lean on (do Pezinka / v Pezinku, do Košíc, z tretieho
nástupišťa, štyri eurá, o desiatej, v Píle pri Modre) and all five
repair-item broken→fixed pairs (the „sa" second-position item is right).

## Verdict

Safe to start daily practice now. Real risk remaining is subtle
naturalness/register, which only the native pass resolves.
