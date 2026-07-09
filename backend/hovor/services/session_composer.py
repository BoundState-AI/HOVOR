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
from hovor.services import game, learner_model

# Which exercise type drills which retrieval mode (spec §18, §29).
MODE_TO_EXERCISE = {
    "recognition_text": "read_translate",
    "recognition_audio": "listen_select",
    "production_prompted": "concept_retrieve",
    "production_spontaneous": "voice_mission",
}


def _exercise_for(item_id: str, mode: str, content: ContentBundle, strength: float = 0.0) -> dict:
    """Pick the exercise variant that attacks this (item, mode) hardest:
    confusion pairs get contrast drills, known-ish audio gets dictation,
    solid prompted production gets a rapid-recall time budget (spec §18)."""
    lexeme = content.lexeme(item_id)
    base = {"item_id": item_id, "mode": mode, "skill_nodes": list(lexeme.skill_nodes)}

    partner = content.confusion_partner(item_id)
    if mode == "recognition_text" and partner and strength < 0.6:
        other = content.lexeme(partner)
        return {
            **base,
            "exercise_id": f"contrast:{item_id}:{partner}",
            "type": "minimal_contrast",
            "prompt": lexeme.slovak,
            "contrast_with": other.slovak,
            "instruction": f"'{lexeme.slovak}' vs '{other.slovak}' — what does '{lexeme.slovak}' mean?",
        }
    if mode == "recognition_audio" and strength >= 0.3:
        return {
            **base,
            "exercise_id": f"dictation:{item_id}",
            "type": "listen_type",
            "prompt": lexeme.slovak,  # client plays TTS of this; slice shows text
            "instruction": "Listen and type exactly what you hear.",
        }
    if mode == "production_prompted" and strength >= 0.5:
        return {
            **base,
            "exercise_id": f"rapid:{item_id}",
            "type": "rapid_recall",
            "prompt": lexeme.english,
            "time_budget_ms": 3000,
            "instruction": "Say it in Slovak — fast.",
        }

    exercise = {
        **base,
        "exercise_id": f"{item_id}:{mode}",
        "type": MODE_TO_EXERCISE[mode],
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


def _repair_exercise_for_recurring(db: Session, user_id: int, content: ContentBundle) -> dict | None:
    """If a recurring grammar error maps to a repair item, ambush it (spec §5A:
    'repair yesterday's recurring error')."""
    recurring = learner_model.recurring_errors(db, user_id)
    if not recurring:
        return None
    recurring_items = {tag.split(":", 1)[1] for tag in recurring if ":" in tag}
    for item in content.repair_items.values():
        if set(item.get("lexemes", [])) & recurring_items or item["id"] in recurring_items:
            return {
                "exercise_id": f"repair:{item['id']}",
                "type": "error_repair",
                "item_id": item["id"],
                "mode": "production_prompted",
                "prompt": item["broken"],
                "instruction": "This sentence has a mistake you keep making. Say it correctly.",
                "skill_nodes": item.get("skill_nodes", []),
            }
    return None


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
    phase_a = [
        _exercise_for(r.item_id, r.mode, content, strength=r.strength)
        for r in due
        if r.item_id in content.lexemes
    ]
    if repair := _repair_exercise_for_recurring(db, user_id, content):
        phase_a.insert(0, repair)  # yesterday's recurring error goes first

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

    # Phase C — the campaign decides: first uncompleted mission in the first
    # unlocked region (spec §4: map is a layer over the curriculum graph).
    mission_id = game.next_mission(db, user_id, content)
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
