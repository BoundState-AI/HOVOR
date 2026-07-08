# HOVOR!

**Learn Slovak by actually speaking it.**

Adaptive Slovak language learning platform. This directory contains the
**Build 1 backend vertical slice** from the HOVOR! Rev 1 specification:
one complete learning path — absolute beginner → introduce yourself →
answer a question → complete a live voice mission — with a real learner
model, real review scheduling, real mission state, and no fake screens.

The seed campaign is the ancestry path: Modra, Pezinok, Píla, Svätý Jur —
archives, family records, meeting relatives. The first boss fight is
**The Missing Birth Record** at the Modra district archive.

## What's implemented (and proven by tests)

| Spec requirement | Where |
|---|---|
| Per-mode mastery — recognition ≠ production (§2.2, §13) | `hovor/services/learner_model.py` |
| Review scheduler attacks the weakest mode (§29) | `learner_model.due_reviews` |
| Failed vocabulary auto-revisited (§34.7) | failure ⇒ due immediately |
| Recurring errors persist across sessions (§12, §34.8) | `ErrorObservation` + 3-strike detection |
| XP cannot be farmed (§16.1, §34.9) | novelty decay in `services/xp.py` |
| Missions won by communicating, not reciting (§5C, §34.10) | `evaluation.match_objective` + tests |
| Provider failure ≠ learner failure (§32, §34.11) | orchestrator degradation path + test |
| Every evaluation traceable to versions (§27, §34.12) | `scoring_version` + `content_version` on every attempt |
| No fake pronunciation scores (§2.3, §10, §34.13) | `pronunciation_status` is qualitative only; test enforces it |
| Content is versioned (§20, §34.14) | `content/seed/*.json`, `content_version` everywhere |
| Native review required before ship (§21, §34.15) | content flagged `PENDING_NATIVE_REVIEW`; surfaced in `/health` |
| Provider-neutral voice boundary (§7) | `voice/provider.py` + deterministic mock |
| Rescue-mode hint ladder (§11.1) | orchestrator `_advance_hint` |
| Phase A/B/C/D session loop (§5) | `services/session_composer.py`, `services/debrief.py` |

## Quick start

```bash
cd hovor/backend
uv venv && uv pip install -e ".[dev]"
uv run uvicorn hovor.main:app --reload
# tests
uv run pytest tests/ -v
```

## Play the Modra archive mission over HTTP

```bash
curl -X POST localhost:8000/api/v1/users -H 'Content-Type: application/json' -d '{"name":"Ján"}'
curl -X POST localhost:8000/api/v1/learning-sessions -H 'Content-Type: application/json' -d '{"user_id":1}'
curl -X POST localhost:8000/api/v1/voice-sessions -H 'Content-Type: application/json' \
  -d '{"user_id":1,"mission_id":"modra_archive_records","learning_session_id":1}'
# then converse:
curl -X POST localhost:8000/api/v1/voice-sessions/1/turns -H 'Content-Type: application/json' \
  -d '{"text":"Dobrý deň, volám sa Ján."}'
curl -X POST localhost:8000/api/v1/voice-sessions/1/turns -H 'Content-Type: application/json' \
  -d '{"text":"Môj prastarý otec sa narodil v Píle, pri Modre."}'
```

The archivist elicits, acknowledges, deliberately misstates the birthplace
(you must catch and repair it), and finally sends you to the state archive
in Modra with the next step. Multiple phrasings win; hint ladders rescue you;
interrupting is allowed; a provider outage degrades to push-to-talk without
scoring you or losing mission state.

## What is deliberately NOT here yet

- **Real voice providers** — the `VoiceProvider` boundary is built; the
  OpenAI Realtime adapter is the first real implementation to slot in
  (see `docs/ARCHITECTURE.md`). The mock proves the orchestration.
- **Pronunciation scoring** — per spec §10, no numeric Slovak pronunciation
  score exists anywhere in the system, and the data model makes it a
  deliberate act to add one.
- **The Slovak speech bakeoff (Build 0)** — needs API keys and native
  speaker audio; the attempt log already records `provider` and dual
  transcript fields to receive it.
- **Native-reviewed content** — all seed content is flagged
  `PENDING_NATIVE_REVIEW` and the `/health` endpoint says so.

## Layout

```
hovor/
├── README.md            ← you are here
├── docs/ARCHITECTURE.md ← service boundaries, iOS port plan, provider contract
└── backend/
    ├── hovor/
    │   ├── main.py, api/         FastAPI surface (the contract iOS consumes)
    │   ├── content/seed/*.json   versioned curriculum: lexemes, skill graph, missions
    │   ├── models/               learner state: mastery, attempts, errors, XP, sessions
    │   ├── services/             evaluation, learner model, scheduler, XP, composer, debrief
    │   └── voice/                VoiceProvider boundary, mock provider, orchestrator
    └── tests/                    the Rev 1 acceptance criteria, executable
```
