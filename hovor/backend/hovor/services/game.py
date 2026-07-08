"""Game layer (spec §4, §16, §17): campaign map, streaks, achievements.

Three concepts stay separate: XP = activity, Mastery = demonstrated learning,
Rank = campaign progression. The map is a game layer over the curriculum
graph — unlocks come from completed missions, never the other way around.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from hovor.content.loader import ContentBundle
from hovor.models.learner import Attempt, UserAchievement, XPEvent
from hovor.models.voice import VoiceSession
from hovor.services.events import log_event


# -- campaign map --------------------------------------------------------------

def completed_missions(db: Session, user_id: int) -> set[str]:
    rows = db.scalars(
        select(VoiceSession).where(
            VoiceSession.user_id == user_id, VoiceSession.state == "completed"
        )
    ).all()
    return {r.mission_id for r in rows}


def map_state(db: Session, user_id: int, content: ContentBundle) -> dict:
    done = completed_missions(db, user_id)
    regions = []
    for region in content.campaign["regions"]:
        unlock = region["unlock"]
        unlocked = unlock["type"] == "always" or all(
            m in done for m in unlock.get("missions", [])
        )
        regions.append(
            {
                "id": region["id"],
                "title": region["title"],
                "order": region["order"],
                "status": region.get("status", "available"),
                "unlocked": unlocked,
                "missions": [
                    {
                        "mission_id": mid,
                        "title": content.mission(mid)["title"],
                        "completed": mid in done,
                        # Replayable as a no-English run once beaten (spec §16.5).
                        "no_english_available": mid in done,
                    }
                    for mid in region["missions"]
                ],
                "focus_skills": region["focus_skills"],
            }
        )
    return {
        "campaign_id": content.campaign["campaign_id"],
        "title": content.campaign["title"],
        "regions": regions,
    }


def next_mission(db: Session, user_id: int, content: ContentBundle) -> str:
    """First uncompleted mission in the first unlocked region; falls back to
    the last mission so veterans can keep replaying."""
    state = map_state(db, user_id, content)
    last = None
    for region in state["regions"]:
        for m in region["missions"]:
            last = m["mission_id"]
            if region["unlocked"] and not m["completed"]:
                return m["mission_id"]
    return last or next(iter(content.missions))


# -- streak (spec §16.2) --------------------------------------------------------

def streak(db: Session, user_id: int) -> dict:
    """Consecutive days with at least one successful attempt. Shields are
    EARNED (one per full 7-day run, max 2) and cover single-day gaps —
    missing one day does not destroy months of work, and there is nothing
    to buy."""
    rows = db.scalars(
        select(Attempt).where(
            Attempt.user_id == user_id,
            Attempt.semantic_success == True,  # noqa: E712
            Attempt.event_class == "learner",
        )
    ).all()
    days = sorted({a.timestamp.date() for a in rows}, reverse=True)
    if not days:
        return {"days": 0, "shields": 0, "active_today": False}

    today = days[0] if days else date.today()
    active_days = set(days)
    shields_earned = 0
    shields_used = 0
    count = 0
    cursor = days[0]
    while True:
        if cursor in active_days:
            count += 1
            if count % 7 == 0 and shields_earned < 2:
                shields_earned += 1
        else:
            if shields_earned - shields_used > 0:
                shields_used += 1  # a shield absorbs one missed day
            else:
                break
        cursor = cursor - timedelta(days=1)
        if cursor < days[-1]:
            break
    return {
        "days": count,
        "shields": max(0, shields_earned - shields_used),
        "active_today": date.today() in active_days or today == date.today(),
    }


# -- achievements (spec §16.6) ---------------------------------------------------

def _has(db: Session, user_id: int, achievement_id: str) -> bool:
    return (
        db.scalar(
            select(UserAchievement).where(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement_id,
            )
        )
        is not None
    )


def _grant(db: Session, user_id: int, achievement_id: str, content: ContentBundle) -> dict | None:
    if achievement_id not in content.achievements or _has(db, user_id, achievement_id):
        return None
    db.add(UserAchievement(user_id=user_id, achievement_id=achievement_id))
    db.flush()
    log_event(db, "achievement_granted", user_id, {"achievement_id": achievement_id})
    a = content.achievements[achievement_id]
    return {"id": achievement_id, "title": a["title"], "description": a["description"]}


def check_after_attempt(db: Session, user_id: int, attempt: Attempt, content: ContentBundle) -> list[dict]:
    granted = []
    if attempt.input_mode == "speech" and attempt.semantic_success:
        if g := _grant(db, user_id, "first_blood", content):
            granted.append(g)
    return granted


def check_after_mission(db: Session, vs: VoiceSession, content: ContentBundle) -> list[dict]:
    granted = []
    for aid, a in content.achievements.items():
        cond = a["condition"]
        kind = cond["kind"]
        ok = False
        if kind == "mission_complete":
            ok = cond["mission_id"] == vs.mission_id
        elif kind == "mission_complete_no_english":
            ok = vs.english_turns == 0
        elif kind == "mission_complete_max_hints":
            total_hints = sum(level + 1 for level in vs.hint_levels.values())
            ok = total_hints <= cond["max_hints"]
        elif kind == "mission_complete_no_english_mode":
            ok = vs.no_english
        if ok and (g := _grant(db, vs.user_id, aid, content)):
            granted.append(g)
    return granted


def check_recurring_resolved(db: Session, user_id: int, content: ContentBundle) -> list[dict]:
    granted = []
    if g := _grant(db, user_id, "again", content):
        granted.append(g)
    return granted


def achievements_for(db: Session, user_id: int, content: ContentBundle) -> list[dict]:
    rows = db.scalars(
        select(UserAchievement).where(UserAchievement.user_id == user_id)
    ).all()
    out = []
    for r in rows:
        a = content.achievements.get(r.achievement_id, {})
        out.append(
            {
                "id": r.achievement_id,
                "title": a.get("title", r.achievement_id),
                "description": a.get("description", ""),
                "earned_at": r.created_at.isoformat(),
            }
        )
    return out


def xp_history(db: Session, user_id: int, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(XPEvent).where(XPEvent.user_id == user_id).order_by(XPEvent.id.desc()).limit(limit)
    ).all()
    return [{"amount": r.amount, "reason": r.reason, "at": r.created_at.isoformat()} for r in rows]
