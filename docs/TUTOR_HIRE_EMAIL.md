# Tutor Hire — Ready-to-Send Message + Checklist

> **Plan of record (2026-07-11): the native review happens in person on the
> Prague trip** — plenty of native Slovak speakers/tutors in Prague. The
> message below works nearly verbatim as an in-person brief; the recording
> task gets *easier* face to face. Interim: content cross-checked by a second
> machine (`INTERIM_MACHINE_REVIEW.md` — 2 errors fixed) and cleared for
> daily practice. The remote-hire path below stays as the fallback if the
> trip slips.

Drafted 2026-07-11. Send via iTalki/Preply message (search "Slovak tutor",
filter for teaching experience + good reviews). Budget: ~$50–80 total
(3–5 hrs review + ~30 min recording). Attach or link the files listed at
the bottom after booking.

---

## The message (copy/paste)

Subject: Paid project: review Slovak learning content + record 6 short audio clips (~4–5 hours)

Hi [name],

I'm an American learning Slovak — my great-grandfather emigrated from the
Modra/Pezinok area, and I'm building a small personal speaking-practice app
around that family history. All of the Slovak content in it was
machine-generated, and before I practice with it daily I need a native
speaker to check it. I'd like to book your time for two tasks:

**Task 1 — Content review (~3–5 hours).** I'll send you a structured
document (~131 words/phrases, 3 short conversation scripts, and some
error-explanation notes). For each item, mark it:

- **OK** — correct and natural
- **WRONG** — with the correction
- **UNNATURAL** — grammatical, but a real person would say ___ instead

Please also flag register problems (formal vs. informal mixed up),
missing diacritics, and anything a Slovak would find odd. Comments in
English are fine. Editing directly in the document with tracked changes
or comments is perfect.

**Task 2 — Six short recordings (~30 min).** Six Slovak sentences, one
audio file each, reading the text exactly as written. Your phone
microphone is fine — I actually *want* everyday recording conditions
(I'll note per sentence: quiet room, on the street, etc.). WAV or M4A,
named u001, u004, u005, u007, u009, u011.

I'd book this as regular lesson hours at your normal rate. Timeline is
flexible — within two weeks would be great. Happy to answer questions
about any of the content, and if the review goes well I'll have follow-up
batches as the app grows (plus I'll eventually want real conversation
lessons!).

Ďakujem!
Joe

---

## What to attach after they accept

| File | Purpose |
|---|---|
| `docs/REVIEW_PACKET.md` | the structured review document (Task 1) |
| `backend/hovor/content/seed/lexemes.json` | raw lexeme data, if they want it |
| `backend/hovor/content/seed/missions.json` | mission scripts |
| `backend/hovor/content/seed/repair_items.json` | error-repair explanations |
| The 6 `"type": "native"` reference sentences from `backend/hovor/bakeoff/sample_manifest.json` (u001, u004, u005, u007, u009, u011), each with its `condition` note | Task 2 recording sheet |

## When the review comes back

1. Apply corrections to the seed JSON files (bump `content_version`).
2. Flip `review_status` from `PENDING_NATIVE_REVIEW` → reviewed; confirm
   the `/health` flag clears.
3. Drop the 6 recordings into the bakeoff manifest (`audio_path` fields),
   record the 6 learner-accent utterances yourself, and run the real
   bakeoff (PowerShell, not Git Bash — env-var mangling):
   `uv run python -m hovor.bakeoff hovor/bakeoff/sample_manifest.json --providers openai`

## Candidate content additions (decide BEFORE sending, so one review pass covers them)

Gap audit of the current 131 lexemes (2026-07-11): survival coverage is
better than expected — food/drink, numbers, travel transactions, question
words, and time are all present, and verbs are smartly stored as
first-person conjugated forms (chcem, mám, hľadám, potrebujem) rather than
infinitives. But these high-frequency items are **missing entirely**:

- **Motion verb — no "idem" (I'm going / I go).** A travel campaign with no
  way to say "I'm going to Modra" is the single biggest gap.
- **Directions: vpravo, vľavo, rovno, ďaleko, blízko** — asking "kde"
  is covered but understanding the answer is not.
- **Modals: môžem (I can / may I), musím (I must)** — needed for polite
  requests and half of survival conversation.
- **viem / neviem po slovensky** — "neviem" exists only as "I don't know";
  "viem" (I know / I can [skill]) is absent.
- **Days of the week** — time expressions exist but no pondelok…nedeľa.
- **Polite address: pán / pani** — needed for the formal register the
  archive/matrika missions depend on.

Recommendation: add ~15–20 lexemes covering the above to `lexemes.json`
before sending the packet, so the tutor vets them in the same pass.
