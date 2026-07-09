# HOVOR! Architecture

Status: backend through Build 3 implemented and tested; web client playable;
OpenAI Realtime adapter code-complete (live pending key); Build 0 bakeoff
harness ready for keys + audio; iOS scaffold written (unbuilt).
Spec reference: HOVOR! Rev 1, 8 July 2026.

## Shape

Modular monolith (spec §23.3: "do not deploy nine microservices on day one").
The service boundaries exist as Python modules with clean seams, so they can
be split when operational evidence justifies it:

```
FastAPI (hovor/api)
    ├── Learner Service .......... services/learner_model.py
    ├── Curriculum Service ....... content/loader.py (versioned JSON)
    ├── Exercise Service ......... services/session_composer.py, services/attempts.py
    ├── Review Scheduler ......... learner_model.due_reviews / record_outcome
    ├── Game Service (XP) ........ services/xp.py
    ├── Conversation Orchestrator  voice/orchestrator.py
    └── Voice Provider boundary .. voice/provider.py  ← adapters live below this line
```

Three hard rules the code enforces:

1. **The voice model never owns persistent truth** (§24). The provider gets
   bounded per-turn context and returns proposals; `MissionOrchestrator`
   validates objective completion itself and is the only writer of mastery,
   XP, and mission state (§25).
2. **Provider failure is a separate event class from learner error** (§32).
   `ProviderError` degrades the channel (`degraded_push_to_talk`), preserves
   mission state, and scores nothing.
3. **No numeric pronunciation score exists** (§2.3, §10). Speech attempts
   carry `pronunciation_status ∈ {not_assessed, unknown, high_confidence_note}`.
   Adding a number requires a schema change — a deliberate act gated on a
   calibrated Slovak pronunciation engine.

## The VoiceProvider contract (§7)

`voice/provider.py` defines the provider-neutral boundary. No provider event
format crosses above it.

| Contract | Backend (Python) | iOS (Swift, planned) |
|---|---|---|
| `create_session/update_session` | `VoiceProvider.create_session(config)` | `protocol VoiceProviding { func createSession(_:) async throws }` |
| learner utterance in | `send_text(text, context) -> TutorReply` | `send(audio:)` via WebRTC, transcripts back as events |
| barge-in | `interrupt() -> ProviderEvent` | `interrupt()` cancels playback + provider response |
| events | `ProviderEvent(type, payload)` | `AsyncStream<ProviderEvent>` |

Implementations:

- `MockVoiceProvider` (done) — deterministic, scriptable failures, drives all tests.
- `OpenAIRealtimeProvider` (done, live-unverified) — `voice/openai_realtime.py`:
  injectable Transport (WebSocket now, WebRTC-swappable), shared
  `build_tutor_instructions()` (persona + hidden-objective steering +
  correction policy + no-English rule), fake-transport tests prove turn
  assembly, tool-call proposals, interrupt, and §32 degradation. Needs
  OPENAI_API_KEY for live verification.
- `OpenAILiveProvider` (future) — GPT-Live full-duplex when the API ships.
  Slots in with no changes to curriculum, learner state, missions, or scoring.
- Azure / Google / ElevenLabs — bakeoff adapters exist as fail-loud skeletons
  in `bakeoff/providers.py`; the dual-transcript agreement gate on attempts
  (`transcript_disagreement`) is the §8.2 independent path's landing zone.

## iOS port plan (SwiftUI)

The slice was built API-first so the iOS client is a consumer, not a rewrite:

1. **Contracts.** Everything the tests drive over HTTP is the client contract:
   `POST /users`, `POST /learning-sessions` (returns the Phase A/B/C plan),
   `POST /attempts`, `POST /voice-sessions`, `POST /voice-sessions/{id}/turns`,
   `/interrupt`, `GET /learning-sessions/{id}/debrief`, `GET /users/{id}/profile`.
   Generate Swift models from the OpenAPI schema FastAPI already serves at `/openapi.json`.
2. **Audio leg.** `AVAudioEngine` capture → WebRTC to the realtime provider
   (per OpenAI guidance); the backend voice-session endpoints become the
   control plane (start mission, validate objectives, record attempts) while
   audio flows client↔provider directly. The mock provider path stays as the
   offline/dev mode — the current `turns` endpoint with typed text IS
   push-to-talk fallback (§32) already.
3. **State.** The client caches the session plan and mission transcript in
   SQLite; the backend remains the source of truth for mastery/XP/errors.
4. **Swift mirror of the boundary.** `VoiceProviding` protocol with
   `MockVoiceProvider` (same scripted missions, decoded from the same
   versioned JSON) so UI development doesn't need a network or a key.

## Data model notes

- `MasteryEstimate` is one row per (user, item, retrieval mode). The four
  modes (`recognition_text`, `recognition_audio`, `production_prompted`,
  `production_spontaneous`) are scheduled independently; `due_reviews`
  surfaces the weakest due mode per item — this is what makes "you recognize
  vlak but can't retrieve it in conversation" a queryable fact (§13).
- `Attempt` preserves raw + normalized response, `scoring_version`,
  `content_version`, `provider`, and `event_class` so a better evaluator can
  rescore history later (§27).
- Content is immutable versioned JSON (`ancestry-slice-0.1.0`), flagged
  `PENDING_NATIVE_REVIEW` until the native reviewer program (§21) clears it;
  `/health` exposes both facts.

## Adaptation engine (§28)

Deliberately transparent and rule-based for now:

- success: `strength += 0.35 × (1 − strength)`, halved if latency > 6 s
- failure: `strength ×= 0.5`, item due **immediately**
- intervals: 10 min → 8 h → 1 d → 3 d → 7 d → 21 d by strength band
- hints: ≥ 2 hints on an exercise forfeits mastery credit (not mission progress)
- errors: 3 unresolved observations of one tag ⇒ `recurring_pattern`,
  prioritized in debrief

Collect evidence first; no black-box RL (§28).

## What Build 0 (bakeoff) will plug into

`Attempt` already carries `provider` and the speech fields are reserved
(`input_mode="speech"`, dual-transcript columns planned in the same table
family). The bakeoff harness is a separate deliverable: manifest of speakers ×
conditions × content (incl. Modra/Pezinok/Svätý Jur proper nouns), WER/CER/
diacritic/proper-noun metrics, latency and cost per provider — producing
`VOICE_BENCHMARK_REPORT_v1` before any provider is locked in.
