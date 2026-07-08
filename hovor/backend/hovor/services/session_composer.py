"""Daily session composition (spec §5).

Phase A — retrieval ambush: items at the forgetting boundary, weakest mode.
Phase B — new material: a tightly constrained batch of unseen lexemes.
Phase C — voice mission.
Phase D — debrief (produced at session end by debrief.py).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from hovor.content.loader import ContentBundle
from hovor.core.config import settings
from hovor.models.learner import LearningSession, MasteryEstimate
from hovor.services import learner_model

# Which exercise type drills which retrieval mode (spec §18, §29).
MODE_TO_EXERCISE = {
    "recognition_text": "read_translate",
    "recognition_audio": "listen_select",
    "production_prompted": "concept_retrieve",
    "production_spontaneous": "voice_mission",
}


def _exercise_for(item_id: str, mode: str, content: ContentBundle) -> dict:
    lexeme = content.lexeme(item_id)
    exercise = {
        "exercise_id": f"{item_id}:{mode}",
        "type": MODE_TO_EXERCISE[mode],
        "item_id": item_id,
        "mode": mode,
        "skill_nodes": list(lexeme.skill_nodes),
    }
    if mode.startswith("recognition"):
        exercise["prompt"] = lexeme.slovak
        exercise["instruction"] = (
            "Listen and say what it means." if mode == "recognition_audio" else "What does this mean?"
        )
    else:
        exercise["prompt"] = lexeme.english
        exercise["instruction"] = "Say it in Slovak."
    return exercise


def _seen_item_ids(db: Session, user_id: int) -> set[str]:
    rows = db.scalars(select(MasteryEstimate).where(MasteryEstimate.user_id == user_id)).all()
    return {r.item_id for r in rows}


def _introduction_order(content: ContentBundle) -> list[str]:
    """New material respects the skill graph: lower-stage nodes first, and a
    node's lexemes only after its prerequisites' (spec §4: geography/game layer
    must never distort prerequisite learning)."""
    indegree = {n: 0 for n in content.skill_nodes}
    for src, dst in content.skill_edges:
        indegree[dst] += 1
    order: list[str] = []
    frontier = sorted(
        [n for n, d in indegree.items() if d == 0],
        key=lambda n: (content.skill_nodes[n].stage, n),
    )
    while frontier:
        node = frontier.pop(0)
        order.append(node)
        for src, dst in content.skill_edges:
            if src == node:
                indegree[dst] -= 1
                if indegree[dst] == 0:
                    frontier.append(dst)
        frontier.sort(key=lambda n: (content.skill_nodes[n].stage, n))

    node_rank = {n: i for i, n in enumerate(order)}
    lex_ids = sorted(
        content.lexemes,
        key=lambda lid: min(node_rank.get(s, 99) for s in content.lexemes[lid].skill_nodes),
    )
    return lex_ids


def compose_session(db: Session, user_id: int, content: ContentBundle) -> LearningSession:
    # Phase A — retrieval ambush
    due = learner_model.due_reviews(db, user_id, settings.retrieval_batch_size)
    phase_a = [_exercise_for(r.item_id, r.mode, content) for r in due if r.item_id in content.lexemes]

    # Phase B — new material
    seen = _seen_item_ids(db, user_id)
    new_ids = [lid for lid in _introduction_order(content) if lid not in seen]
    phase_b = []
    for lid in new_ids[: settings.new_material_batch_size]:
        lexeme = content.lexeme(lid)
        phase_b.append(
            {
                "introduce": {
                    "item_id": lid,
                    "slovak": lexeme.slovak,
                    "english": lexeme.english,
                    "register": lexeme.register,
                    "skill_nodes": list(lexeme.skill_nodes),
                },
                # Immediate reuse: introduction is followed by production (spec §5B).
                "exercise": _exercise_for(lid, "production_prompted", content),
            }
        )

    # Phase C — voice mission (first mission of the campaign for the slice)
    mission_id = next(iter(content.missions))
    mission = content.mission(mission_id)
    phase_c = {
        "mission_id": mission_id,
        "title": mission["title"],
        "region": mission["region"],
        "briefing": mission["briefing"],
    }

    session = LearningSession(
        user_id=user_id,
        plan={"phase_a": phase_a, "phase_b": phase_b, "phase_c": phase_c},
        content_version=content.content_version,
    )
    db.add(session)
    db.flush()
    return session
