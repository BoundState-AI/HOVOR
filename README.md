# HOVOR!

**Learn Slovak by actually speaking it.**

Adaptive Slovak language learning platform. This repository holds the working
implementation of the HOVOR! Rev 1 spec: the full learning loop with a real
learner model, the ancestry campaign ("The Journey Home": Bratislava →
Svätý Jur → Pezinok → Modra), a playable web client, the Build 0 speech
bakeoff harness, an OpenAI Realtime adapter behind a provider-neutral
boundary, and an iOS scaffold on the same contracts.

## Quick start

```bash
cd backend
uv venv && uv pip install -e ".[dev]"
uv run uvicorn hovor.main:app --reload
# open http://localhost:8000  ← playable web client
# tests
uv run pytest tests/ -v
# speech bakeoff (mock provider; add keys + audio for real ones)
uv run python -m hovor.bakeoff hovor/bakeoff/sample_manifest.json --providers mock
```

## What exists, mapped to the spec

| Subsystem | Spec | Status |
|---|---|---|
| Per-mode learner model (recognition ≠ production), weakest-mode scheduling | §13 §29 | ✅ tested |
| Session loop: retrieval ambush → new material → voice mission → debrief | §5 | ✅ tested + playable |
| Campaign map with mission-gated unlocks (3 missions, 4 regions) | §4 §16.4 | ✅ tested |
| Exercise engine: read/listen/retrieve, dictation, minimal contrast, rapid recall, error repair | §18 | ✅ tested |
| Longitudinal error memory, recurring-error ambush + resolution ("Again?") | §12 §34.8 | ✅ tested |
| XP with novelty decay (no farming), streaks with earned shields, 7 achievements, focus meter | §16 §17 | ✅ tested |
| No-English runs with XP-cost emergency help | §16.5 | ✅ tested |
| Tutor strictness → hint ladder shape (ruthless never reveals) | §11 §22 | ✅ tested |
| Provider-neutral voice boundary + deterministic mock | §7 | ✅ tested |
| OpenAI Realtime adapter (injectable transport; fake-transport tests) | §6.2 | ✅ live-verified (GA wire format) |
| Two-way voice: live tutor speaks (spoken WAV per turn, "live tutor" toggle) | §6 §23.3 | ✅ live-verified; per-turn reconnect (broker = latency upgrade) |
| Hear-it: on-demand pronunciation of any content string (🔊, true listening dictation) | §18 | ✅ live-verified; whitelisted + cached TTS |
| Speech input on every platform (MediaRecorder → server-side sk transcription) + mobile layout | §8 §23 | ✅ live-verified closed-loop (TTS→ASR, diacritics intact) |
| Provider failure ≠ learner failure; degraded push-to-talk | §32 §34.11 | ✅ tested |
| Dual-transcript agreement gate ("let's not score it") | §8.2 §12 | ✅ tested |
| Build 0 bakeoff: WER/CER/diacritic/proper-noun/latency → report | §9 §33 | ✅ harness tested, ⏳ needs keys + native audio |
| Privacy: consent-gated audio, research opt-in, delete-my-audio | §31 | ✅ tested |
| Observability: event log + /metrics | §30 | ✅ tested |
| No numeric pronunciation score anywhere | §2.3 §10 §34.13 | ✅ enforced by tests |
| Versioned content flagged for native review | §20 §21 | ✅ (`PENDING_NATIVE_REVIEW`, surfaced in /health) |
| Web client (playable, browser sk-SK push-to-talk) | — | ✅ driven end-to-end in Chromium |
| iOS scaffold (HovorKit + app shell) | §23.1 | ⏳ written, needs Xcode to build |

## What still needs a human or a key

1. **Native Slovak review** (§21) — every lexeme, mission line, and repair
   item is machine-authored and flagged. This is the gate before real users.
   No native speaker in your network needed — see `docs/NATIVE_REVIEW.md`
   for the remote-hire playbook.
2. **OPENAI_API_KEY** — flips the mission engine from the deterministic mock
   to live spoken Slovak via the Realtime adapter (live-verified). Put it in
   `backend/.env` (gitignored, loaded automatically) per machine/deploy.
3. **Bakeoff audio** — the manifest format and metrics are ready. Half the
   panel is learner-accent audio you can record yourself; the native half is
   the same hire as item 1 (`docs/NATIVE_REVIEW.md`).
4. **Xcode** — HovorKit now builds and tests in CI on a macOS runner
   (`.github/workflows/ios.yml`); the app shell still needs an Xcode project.
5. **Pronunciation engine** (Build 5, §10) — intentionally absent until an
   opt-in **learner** speech corpus exists (collected via the tested consent
   flows, §31). Not blocked on native speakers; unblocks with real usage.

## Layout

```
.
├── README.md
├── docs/ARCHITECTURE.md      service boundaries, iOS port plan, provider contract
├── ios/                      HovorKit package + SwiftUI app shell
└── backend/
    ├── hovor/
    │   ├── main.py, api/     FastAPI + the /app web client mount
    │   ├── web/              playable single-page client
    │   ├── content/seed/     versioned curriculum: 131 lexemes, 16 skills,
    │   │                     3 missions, campaign, repairs, achievements
    │   ├── models/           learner state, voice sessions, events
    │   ├── services/         evaluation, learner model, scheduler, XP,
    │   │                     composer, debrief, game, events
    │   ├── voice/            provider boundary, mock, OpenAI Realtime, orchestrator
    │   └── bakeoff/          Build 0 harness (python -m hovor.bakeoff)
    └── tests/                55 tests: the Rev 1 acceptance criteria, executable
```
