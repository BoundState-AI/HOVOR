"""Exercise-type dispatch, confusion pairs, focus meter, recurring-error
resolution, and the transcript-agreement gate."""

from sqlalchemy import select

from hovor.models.learner import ErrorObservation, MasteryEstimate, User
from hovor.services import learner_model
from hovor.services.attempts import submit_exercise_attempt
from hovor.services.session_composer import compose_session


def _user(db, **kw):
    user = User(name="T", **kw)
    db.add(user)
    db.flush()
    return user


def test_contrast_exercise_logs_confusion(db, content):
    user = _user(db)
    attempt, _ = submit_exercise_attempt(
        db, user.id, None, "contrast:kde:kedy", "when", content
    )
    assert attempt.semantic_success is False
    assert attempt.error_tags == ["confusion:kde:kedy"]  # read 'kde' as 'kedy'


def test_dictation_updates_listening_mode(db, content):
    user = _user(db)
    attempt, _ = submit_exercise_attempt(db, user.id, None, "dictation:vlak", "vlak", content)
    assert attempt.semantic_success
    row = learner_model.get_or_create_mastery(db, user.id, "vlak", "recognition_audio", content.content_version)
    assert row.strength > 0
    prod = learner_model.get_or_create_mastery(db, user.id, "vlak", "production_prompted", content.content_version)
    assert prod.strength == 0.0  # listening credit never leaks into production


def test_rapid_recall_requires_speed(db, content):
    user = _user(db)
    submit_exercise_attempt(db, user.id, None, "rapid:vlak", "vlak", content, latency_ms=5000)
    row = learner_model.get_or_create_mastery(db, user.id, "vlak", "production_prompted", content.content_version)
    assert row.strength == 0.0  # right answer, too slow — no credit
    submit_exercise_attempt(db, user.id, None, "rapid:vlak", "vlak", content, latency_ms=900)
    db.refresh(row)
    assert row.strength > 0


def test_repair_exercise_and_recurring_resolution(db, content):
    """The full 'Again?' arc: recur three times, then two clean successes
    resolve it and grant the achievement."""
    user = _user(db)
    for _ in range(3):
        attempt, _ = submit_exercise_attempt(
            db, user.id, None, "repair:er_z_amerika", "som z amerika", content
        )
        assert not attempt.semantic_success
    recurring = learner_model.recurring_errors(db, user.id)
    assert "repair_failure:er_z_amerika" in recurring

    submit_exercise_attempt(db, user.id, None, "repair:er_z_amerika", "som z ameriky", content)
    _, extras = submit_exercise_attempt(db, user.id, None, "repair:er_z_amerika", "som z ameriky", content)
    assert "again" in {a["id"] for a in extras["achievements"]}
    assert learner_model.recurring_errors(db, user.id) == {}
    unresolved = db.scalars(
        select(ErrorObservation).where(ErrorObservation.resolved == False)  # noqa: E712
    ).all()
    assert not [o for o in unresolved if o.error_tag == "repair_failure:er_z_amerika"]


def test_focus_meter_escalates_on_failures(db, content):
    from hovor.models.learner import LearningSession

    user = _user(db)
    session = LearningSession(user_id=user.id, plan={}, content_version=content.content_version)
    db.add(session)
    db.flush()

    _, e1 = submit_exercise_attempt(db, user.id, session.id, "vlak:production_prompted", "zle", content)
    assert e1["focus"]["state"] == "ok"
    _, e2 = submit_exercise_attempt(db, user.id, session.id, "vlak:production_prompted", "zle", content)
    assert e2["focus"]["state"] == "strained"
    _, e3 = submit_exercise_attempt(db, user.id, session.id, "vlak:production_prompted", "zle", content)
    assert e3["focus"]["state"] == "overloaded"  # support, never punishment


def test_transcript_disagreement_blocks_scoring(db, content):
    """Spec §12: 'I'm not certain whether that was your pronunciation or the
    transcription. Let's not score it.'"""
    user = _user(db)
    attempt, extras = submit_exercise_attempt(
        db, user.id, None, "vlak:production_prompted", "vlak", content,
        input_mode="speech", secondary_transcript="idem do obchodu zajtra",
    )
    assert attempt.semantic_success is False  # not scored as success...
    assert attempt.error_tags == ["transcript_disagreement"]
    assert "not score" in extras["note"]
    row = learner_model.get_or_create_mastery(db, user.id, "vlak", "production_prompted", content.content_version)
    assert row.attempts == 0  # ...and mastery untouched: uncertainty ≠ failure


def test_agreeing_transcripts_score_normally(db, content):
    user = _user(db)
    attempt, _ = submit_exercise_attempt(
        db, user.id, None, "vlak:production_prompted", "vlak", content,
        input_mode="speech", secondary_transcript="vlak",
    )
    assert attempt.semantic_success is True
    assert attempt.transcript_disagreement == 0.0


def test_audio_dropped_without_consent(db, content):
    no_consent = _user(db)
    attempt, _ = submit_exercise_attempt(
        db, no_consent.id, None, "vlak:production_prompted", "vlak", content,
        input_mode="speech", audio_reference="s3://bucket/a.wav",
    )
    assert attempt.audio_reference is None  # privacy default (spec §31)

    consented = _user(db, retain_audio=True)
    attempt, _ = submit_exercise_attempt(
        db, consented.id, None, "vlak:production_prompted", "vlak", content,
        input_mode="speech", audio_reference="s3://bucket/b.wav",
    )
    assert attempt.audio_reference == "s3://bucket/b.wav"


def test_composer_serves_contrast_and_repair(db, content):
    user = _user(db)
    # Weak recognition on a confusion-pair member → contrast drill in Phase A.
    learner_model.record_outcome(db, user.id, "kde", "recognition_text", False, content.content_version)
    # A recurring repair-mapped error → repair ambush first.
    for _ in range(3):
        submit_exercise_attempt(db, user.id, None, "repair:er_z_amerika", "som z amerika", content)

    session = compose_session(db, user.id, content)
    types = [e["type"] for e in session.plan["phase_a"]]
    assert types[0] == "error_repair"  # yesterday's recurring error goes first
    assert "minimal_contrast" in types
