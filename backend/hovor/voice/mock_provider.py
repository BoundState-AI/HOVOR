"""Deterministic mock voice provider.

Plays the mission character from the scripted lines in mission content, driven
entirely by the bounded context the orchestrator passes in — it holds no
persistent truth (spec §24). Scriptable failures let tests prove that provider
failure is never scored as learner failure (spec §32).
"""

from typing import Any

from hovor.voice.provider import ProviderError, ProviderEvent, TutorReply, VoiceProvider


class MockVoiceProvider(VoiceProvider):
    name = "mock-0.1"

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._turn_count = 0
        self._speaking = False

    def create_session(self, config: dict[str, Any]) -> None:
        self._config = config

    def update_session(self, config: dict[str, Any]) -> None:
        self._config.update(config)

    def send_text(self, text: str, context: dict[str, Any]) -> TutorReply:
        self._turn_count += 1
        fail_on = self._config.get("fail_on_turn")
        if fail_on is not None and self._turn_count == fail_on:
            raise ProviderError("simulated provider outage")

        mission = context["mission"]
        just_completed: list[str] = context.get("just_completed", [])
        pending_id: str | None = context.get("pending_objective")
        hint: dict | None = context.get("hint")
        mission_complete: bool = context.get("mission_complete", False)

        objectives = {o["id"]: o for o in mission["objectives"]}
        parts: list[str] = []
        gloss_parts: list[str] = []

        for oid in just_completed:
            parts.append(objectives[oid]["ack"]["slovak"])
            gloss_parts.append(objectives[oid]["ack"]["english"])

        if mission_complete:
            parts.append(mission["completion_line"]["slovak"])
            gloss_parts.append(mission["completion_line"]["english"])
        elif hint is not None:
            parts.append(hint["text"])
            gloss_parts.append(f"[hint:{hint['level']}]")
        elif pending_id is not None:
            parts.append(objectives[pending_id]["elicit"]["slovak"])
            gloss_parts.append(objectives[pending_id]["elicit"]["english"])

        self._speaking = True
        return TutorReply(
            text=" ".join(parts) if parts else "Prosím?",
            english_gloss=" ".join(gloss_parts) if gloss_parts else "Pardon?",
            events=[
                ProviderEvent("final_transcript", {"text": text}),
                ProviderEvent("response_started"),
                ProviderEvent("response_completed"),
            ],
            # The mock "model" proposes completions; the orchestrator has
            # already validated them independently — proposals are advisory.
            proposed_tool_calls=[
                {"tool": "complete_objective", "objective_id": oid} for oid in just_completed
            ],
        )

    def interrupt(self) -> ProviderEvent:
        was_speaking = self._speaking
        self._speaking = False
        return ProviderEvent("interruption", {"stopped_mid_response": was_speaking})

    def close(self) -> None:
        self._speaking = False
