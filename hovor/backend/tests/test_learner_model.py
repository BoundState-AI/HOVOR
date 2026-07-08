"""Spec §2.2 / §13 / §29 / §34.6-8: per-mode mastery, scheduling, error memory."""

from hovor.services import learner_model


def test_recognition_success_never_marks_production(db, content):
    cv = content.content_version
    for _ in range(5):
        learner_model.record_outcome(db, 1, "vlak", "recognition_text", True, cv)

    rec = learner_model.get_or_create_mastery(db, 1, "vlak", "recognition_text", cv)
    prod = learner_model.get_or_create_mastery(db, 1, "vlak", "production_spontaneous", cv)
    assert rec.strength > 0.7
    assert prod.strength == 0.0  # "learned" receptively is not learned productively


def test_failed_item_is_rescheduled_aggressively(db, content):
    cv = content.content_version
    ok = learner_model.record_outcome(db, 1, "vlak", "production_prompted", True, cv)
    spaced_delay = ok.next_review - ok.last_seen

    fail = learner_model.record_outcome(db, 1, "vlak", "production_prompted", False, cv)
    fail_delay = fail.next_review - fail.last_seen
    assert fail_delay < spaced_delay  # failure comes back sooner


def test_failure_reduces_strength(db, content):
    cv = content.content_version
    learner_model.record_outcome(db, 1, "vlak", "production_prompted", True, cv)
    before = learner_model.get_or_create_mastery(db, 1, "vlak", "production_prompted", cv).strength
    learner_model.record_outcome(db, 1, "vlak", "production_prompted", False, cv)
    after = learner_model.get_or_create_mastery(db, 1, "vlak", "production_prompted", cv).strength
    assert after < before


def test_slow_retrieval_earns_less_credit(db, content):
    cv = content.content_version
    fast = learner_model.record_outcome(db, 1, "vlak", "production_prompted", True, cv, latency_ms=800)
    slow = learner_model.record_outcome(db, 2, "vlak", "production_prompted", True, cv, latency_ms=9000)
    assert fast.strength > slow.strength


def test_due_reviews_attack_weakest_mode(db, content):
    cv = content.content_version
    learner_model.record_outcome(db, 1, "vlak", "recognition_text", True, cv)
    learner_model.record_outcome(db, 1, "vlak", "production_prompted", False, cv)
    # Force both due
    for row in db.query(learner_model.MasteryEstimate).all():
        row.next_review = None
    due = learner_model.due_reviews(db, 1, 10)
    vlak_rows = [r for r in due if r.item_id == "vlak"]
    assert len(vlak_rows) == 1
    assert vlak_rows[0].mode == "production_prompted"  # the weaker mode wins


def test_recurring_error_detection(db, content):
    from hovor.services.evaluation import CATEGORY_GRAMMAR_TARGET, ErrorTag

    err = [ErrorTag(tag="ending_error:vlak", category=CATEGORY_GRAMMAR_TARGET)]
    assert learner_model.record_errors(db, 1, None, err) == []
    assert learner_model.record_errors(db, 1, None, err) == []
    assert learner_model.record_errors(db, 1, None, err) == ["ending_error:vlak"]  # 3rd strike
    assert "ending_error:vlak" in learner_model.recurring_errors(db, 1)
