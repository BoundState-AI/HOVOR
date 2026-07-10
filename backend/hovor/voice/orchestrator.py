"""Conversation Orchestrator (spec §24, §25).

Owns mission state, objective validation, scoring, and learner-state updates.
The voice provider receives bounded session context and proposes; application
code here validates. The provider never mutates XP, mastery, or permanent
learner state.
"""

from sqlalchemy.orm import Session

from hovor import SCORING_VERSION
from hovor.content.loader import ContentBundle
from hovor.models.learner import Attempt, User, XPEvent, utcnow
from hovor.models.voice import ConversationTurn, VoiceSession
from hovor.services import game, learner_model, xp
from hovor.services.events import log_event
from hovor.services.evaluation import (
    CATEGORY_MINOR,
    ErrorTag,
    match_objective,
    normalize,
    strip_diacritics,
)
from hovor.voice.provider import ProviderError, VoiceProvider

# Crude but effective English-dependence detector (spec §2.2): common English
# function/content words that are not Slovak words. Two or more hits in one
# utterance marks the turn as English fallback.
_ENGLISH_MARKERS = {
    "the", "i", "is", "was", "my", "me", "you", "he", "she", "it", "we", "they",
    "born", "please", "what", "where", "when", "hello", "yes", "thanks", "thank",
    "grandfather", "grandpa", "family", "need", "help", "sorry", "and", "but",
    "can", "want", "don't", "know", "understand", "speak", "english",
}

# Emergency help in a no-English run costs XP (spec §16.5) — deep-ladder
# hints (show_text, translate) are the ones that break immersion.
NO_ENGLISH_HELP_COST = 10

# Tutor strictness (spec §11.1, §22) shapes the rescue ladder:
# (starting rung, deepest auto-offered rung). Rungs: 0 repeat_slower,
# 1 semantic, 2 first_word, 3 show_text, 4 translate.
_STRICTNESS_LADDER = {
    "gentle": (0, 4),
    "normal": (0, 4),
    "direct": (1, 4),
    "ruthless": (1, 2),  # never auto-reveals the answer
}


def _looks_english(text: str) -> bool:
    words = set(strip_diacritics(normalize(text)).split())
    return len(words & _ENGLISH_MARKERS) >= 2


class MissionOrchestrator:
    def __init__(self, db: Session, content: ContentBundle, provider: VoiceProvider):
        self.db = db
        self.content = content
        self.provider = provider

    # -- session lifecycle -------------------------------------------------

    def start(
        self, user_id: int, mission_id: str, learning_session_id: int | None = None,
        provider_config: dict | None = None, no_english: bool = False,
    ) -> tuple[VoiceSession, dict]:
        mission = self.content.mission(mission_id)
        vs = VoiceSession(
            user_id=user_id,
            learning_session_id=learning_session_id,
            mission_id=mission_id,
            provider=self.provider.name,
            objective_state={o["id"]: {"status": "pending"} for o in mission["objectives"]},
            hint_levels={},
            no_english=no_english,
            content_version=self.content.content_version,
        )
        self.db.add(vs)
        self.db.flush()

        self.provider.create_session(provider_config or {})
        opening = mission["opening_line"]
        self._log(vs, "tutor", "utterance", opening["slovak"], {"english": opening["english"]})
        return vs, opening

    # -- turn handling -----------------------------------------------------

    def handle_learner_turn(self, vs: VoiceSession, text: str) -> dict:
        mission = self.content.mission(vs.mission_id)
        self._log(vs, "learner", "utterance", text)

        # English-dependence signal (spec §2.2): logged, never punished —
        # except in a no-English run, where it's part of the game's rules.
        english_fallback = _looks_english(text)
        if english_fallback:
            vs.english_turns += 1
            learner_model.record_errors(
                self.db, vs.user_id, None,
                [ErrorTag(tag="english_dependence", category=CATEGORY_MINOR,
                          detail=text[:120])],
            )
            log_event(self.db, "english_fallback", vs.user_id,
                      {"mission_id": vs.mission_id, "no_english": vs.no_english})

        # Validate objective completion ourselves — never trust the provider's
        # proposals as truth (spec §25).
        just_completed = self._match_objectives(vs, mission, text)

        pending = self._next_pending(vs, mission)
        hint = None
        if not just_completed and pending is not None:
            hint = self._advance_hint(vs, mission, pending)

        mission_complete = self._check_win(vs, mission)

        context = {
            "mission": mission,
            "just_completed": just_completed,
            "pending_objective": pending,
            "hint": hint,
            "mission_complete": mission_complete,
        }

        try:
            reply = self.provider.send_text(text, context)
        except ProviderError as exc:
            # Provider failure is its own event class: preserve mission state,
            # degrade the channel, score nothing (spec §32, §34.11).
            self._log(vs, "system", "provider_error", str(exc))
            log_event(self.db, "provider_error", vs.user_id,
                      {"provider": self.provider.name, "mission_id": vs.mission_id})
            vs.state = "degraded_push_to_talk"
            self.db.flush()
            return {
                "provider_failure": True,
                "fallback": "push_to_talk",
                "mission_state_preserved": True,
                "objective_state": vs.objective_state,
                "tutor_text": None,
            }

        # Scoring happens only after a healthy provider round-trip.
        for oid in just_completed:
            self._score_objective(vs, mission, oid, text)
        achievements: list[dict] = []
        if mission_complete and vs.state == "active":
            vs.state = "completed"
            vs.ended_at = utcnow()
            xp.award(self.db, vs.user_id, "mission_complete", exercise_id=f"mission:{vs.mission_id}")
            achievements = game.check_after_mission(self.db, vs, self.content)
            log_event(self.db, "mission_completed", vs.user_id,
                      {"mission_id": vs.mission_id, "no_english": vs.no_english,
                       "english_turns": vs.english_turns})
        self.db.flush()

        self._log(vs, "tutor", "utterance", reply.text, {"english": reply.english_gloss})
        return {
            "provider_failure": False,
            "tutor_text": reply.text,
            "tutor_english": reply.english_gloss,
            # Spoken reply (base64 WAV) when the provider produced audio.
            # Response-only: audio is never written to the conversation log (§31).
            "tutor_audio_b64": reply.audio_b64,
            "objectives_completed_this_turn": just_completed,
            "hint": hint,
            "objective_state": vs.objective_state,
            "mission_complete": mission_complete,
            "session_state": vs.state,
            "achievements": achievements,
            "english_fallback": english_fallback,
        }

    def interrupt(self, vs: VoiceSession) -> dict:
        event = self.provider.interrupt()
        self._log(vs, "learner", "interruption", None, event.payload)
        return {"interrupted": True, **event.payload}

    # -- internals -----------------------------------------------------------

    def _match_objectives(self, vs: VoiceSession, mission: dict, text: str) -> list[str]:
        """Greedy front-to-back matching: one utterance may satisfy several
        consecutive objectives (multiple valid phrasings, spec §34.10)."""
        completed: list[str] = []
        state = dict(vs.objective_state)
        for objective in mission["objectives"]:
            oid = objective["id"]
            if state[oid]["status"] == "completed":
                continue
            if match_objective(text, objective["match"]):
                state[oid] = {"status": "completed"}
                completed.append(oid)
            else:
                break  # objectives beyond the first unmet one stay locked
        vs.objective_state = state
        return completed

    def _next_pending(self, vs: VoiceSession, mission: dict) -> str | None:
        for objective in mission["objectives"]:
            if vs.objective_state[objective["id"]]["status"] == "pending":
                return objective["id"]
        return None

    def _advance_hint(self, vs: VoiceSession, mission: dict, objective_id: str) -> dict:
        """Rescue-mode support ladder (spec §11.1): each miss escalates one
        rung. The user's strictness setting shapes where the ladder starts
        and how deep it auto-descends (spec §22); a no-English run charges XP
        for the immersion-breaking rungs (spec §16.5)."""
        objective = next(o for o in mission["objectives"] if o["id"] == objective_id)
        user = self.db.get(User, vs.user_id)
        start, deepest = _STRICTNESS_LADDER.get(
            user.tutor_strictness if user else "normal", (0, 4)
        )

        levels = dict(vs.hint_levels)
        level = levels.get(objective_id)
        level = start if level is None else level + 1
        level = min(level, deepest, len(objective["hints"]) - 1)
        levels[objective_id] = level
        vs.hint_levels = levels

        if vs.no_english and level >= 3:
            # Emergency help available — at a price (spec §16.5).
            self.db.add(XPEvent(user_id=vs.user_id, amount=-NO_ENGLISH_HELP_COST,
                                reason="emergency_help"))
            log_event(self.db, "emergency_help_used", vs.user_id,
                      {"mission_id": vs.mission_id, "level": level})

        self._log(vs, "tutor", "hint", objective["hints"][level]["text"], {"level": level})

        # Deep in the ladder means retrieval genuinely failed — log the
        # evidence so the scheduler revisits these lexemes (spec §34.7).
        if level >= 3:
            for lexeme_id in objective.get("lexemes", []):
                learner_model.record_outcome(
                    self.db, vs.user_id, lexeme_id, "production_spontaneous",
                    success=False, content_version=vs.content_version,
                )
        return objective["hints"][level]

    def _check_win(self, vs: VoiceSession, mission: dict) -> bool:
        required = mission["win_conditions"]["required_objectives"]
        return all(vs.objective_state[oid]["status"] == "completed" for oid in required)

    def _score_objective(self, vs: VoiceSession, mission: dict, objective_id: str, text: str) -> None:
        objective = next(o for o in mission["objectives"] if o["id"] == objective_id)
        hint_count = vs.hint_levels.get(objective_id, -1) + 1

        attempt = Attempt(
            user_id=vs.user_id,
            session_id=vs.learning_session_id,
            voice_session_id=vs.id,
            exercise_id=f"mission:{vs.mission_id}:{objective_id}",
            item_id=None,
            mode="production_spontaneous",
            input_mode="speech",
            raw_response=text,
            normalized_response=normalize(text),
            semantic_success=True,
            target_structure_success=True if objective.get("target_structure") else None,
            hint_count=hint_count,
            error_tags=[],
            event_class="learner",
            # Rule-based slice: no calibrated pronunciation engine, so status
            # is explicit "unknown" for speech — never a fake score (spec §2.3).
            pronunciation_status="unknown",
            scoring_version=SCORING_VERSION,
            content_version=vs.content_version,
            provider=self.provider.name,
        )
        self.db.add(attempt)
        self.db.flush()

        # Spontaneous production evidence for each lexeme the objective targets;
        # heavy hint use forfeits the mastery credit but not mission progress.
        credited = hint_count < 2
        for lexeme_id in objective.get("lexemes", []):
            if lexeme_id not in self.content.lexemes:
                continue
            lexeme = self.content.lexeme(lexeme_id)
            if match_objective(text, {"any_phrases": [lexeme.slovak, *lexeme.slovak_variants]}):
                learner_model.record_outcome(
                    self.db, vs.user_id, lexeme_id, "production_spontaneous",
                    success=credited, content_version=vs.content_version,
                )

        reason = (
            "misunderstanding_repaired" if objective_id == "repair_misunderstanding"
            else "mission_objective"
        )
        attempt.xp_awarded = xp.award(
            self.db, vs.user_id, reason,
            exercise_id=attempt.exercise_id, attempt_id=attempt.id,
        )

    def _log(self, vs: VoiceSession, role: str, event_type: str, text: str | None, meta: dict | None = None) -> None:
        self.db.add(
            ConversationTurn(
                voice_session_id=vs.id, role=role, event_type=event_type,
                text=text, meta=meta or {},
            )
        )
        self.db.flush()
