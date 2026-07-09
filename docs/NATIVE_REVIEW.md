# Native Slovak Review & Bakeoff Recordings — How To Do This Without Knowing a Slovak Speaker

The README lists three gaps that look like they need "a native speaker you know."
None of them do. Two need **one remote hire (~$50–100 total)**; the third needs
no native speaker at all.

## The one hire that solves #1 and #3

A single Slovak tutor or translator, hired remotely, can do both the content
review and the native-side bakeoff recordings in a few paid hours. Where to
find one, in order of practicality:

| Channel | What you get | Cost |
|---|---|---|
| **iTalki / Preply** (search "Slovak tutor") | Native tutors, ~$10–25/hr, book hours and use them for review + recording | ~$50–80 total |
| **Upwork** (search "Slovak translator" or "Slovak voice over") | Professional translators; many also do voice recording gigs | ~$15–40/hr |
| **ProZ.com** | Certified SK translators for the review side | varies |
| **r/Slovakia** | Free/cheap help, less reliable turnaround | free–cheap |

iTalki is the recommended first stop: tutors are used to odd requests, you can
vet Slovak-teaching experience from reviews, and trial lessons are cheap.

## Task 1 — Content review (README item 1)

Everything machine-authored is already flagged `PENDING_NATIVE_REVIEW` and
surfaced at `/health`. The reviewer's deliverable is a pass over:

- `backend/hovor/content/seed/lexemes.json` — 131 lexemes (SK text, gloss, register)
- `backend/hovor/content/seed/missions.json` — 3 mission scripts (character lines, hidden goals, hints)
- `backend/hovor/content/seed/repair_items.json` — error-repair items
- `backend/hovor/content/seed/skills.json` / `campaign.json` — names and descriptions

Ask for: corrections, naturalness notes ("grammatical but nobody says this"),
and register checks (formal/informal consistency). Estimated effort: **3–5
hours**. When it lands, flip `review_status` in the content version and the
`/health` flag clears.

## Task 2 — Bakeoff recordings (README item 3)

`backend/hovor/bakeoff/sample_manifest.json` defines 12 utterances. **Six are
learner-accent (en-US) recordings — record those yourself.** You are literally
the target speaker profile. Only the six `"type": "native"` utterances need the
hire (u001, u004, u005, u007, u009, u011).

Recording instructions to send the hire:

- One audio file per utterance, reading the `reference` text exactly.
- Phone mic is fine — the `condition` field *wants* varied acoustics
  (quiet room, street, in a car, cheap earbuds, deliberately fast).
- WAV or M4A, mono, 16 kHz+. Name files by utterance id: `u001.wav`, …
- The manifest's speaker gender/age metadata is aspirational for a panel of
  one; update the metadata to match whoever you hire rather than chasing a
  40s male AND a 20s female for twelve sentences.

Then add `"audio_path"` fields to the manifest and run:

```bash
cd backend
uv run python -m hovor.bakeoff hovor/bakeoff/sample_manifest.json --providers openai
```

### Interim: synthetic smoke run (no human needed, do it today)

OpenAI TTS can synthesize the 12 utterances in a Slovak voice to validate the
harness end-to-end (manifest → providers → WER/CER/diacritic metrics → report).
Label the output `SYNTHETIC — pipeline validation only`; TTS audio is cleaner
than human speech and must never feed the real provider-selection report.

## README item 5 (pronunciation engine) needs no native speaker

Build 5 is gated on an **opt-in corpus of learner speech** — your users' (or
your own) recorded attempts, collected through the consent flows that already
exist and are tested (§31). Native speakers are not the input. It unblocks
itself once real learners use the app with research opt-in enabled. Leaving it
absent is per spec, not a gap to staff.
