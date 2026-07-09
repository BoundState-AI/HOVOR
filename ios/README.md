# HOVOR! iOS

SwiftUI client scaffold. **Not yet built in CI** — this environment has no
Xcode toolchain; the code targets iOS 17 / Swift 5.9 and mirrors contracts
that ARE fully tested on the backend.

## Layout

- `HovorKit/` — Swift package: Codable models mirroring the backend API,
  `APIClient` (async/await), and `VoiceProviding` — the Swift twin of the
  backend's provider-neutral voice boundary (spec §7).
  `MockVoiceProvider` routes text turns through the backend mission engine:
  that is the offline/dev mode *and* the §32 push-to-talk fallback.
- `HovorApp/` — app shell: campaign map, exercise runner (latency capture
  feeds the learner model), and the mission screen with on-device sk-SK
  speech recognition for push-to-talk.

## Wiring the real voice leg (next)

`OpenAIRealtimeProvider: VoiceProviding` owns a WebRTC session with the
realtime API; the backend voice-session endpoints remain the control plane
(objective validation, scoring, mission state — the model proposes, the
app validates, spec §25). Nothing above the `VoiceProviding` protocol
changes when it lands, GPT-Live included.

## Development against the local backend

Run the backend (`uvicorn hovor.main:app`), point `AppModel.api` at it
(default `http://localhost:8000`), and the whole loop — map, session,
mission chat — works against the deterministic mock provider without keys.
