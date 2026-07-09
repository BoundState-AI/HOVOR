import XCTest

@testable import HovorKit

final class ModelsTests: XCTestCase {
    func testSessionPlanDecodesBackendShape() throws {
        let json = """
        {
          "session_id": 1,
          "content_version": "ancestry-slice-0.2.0",
          "plan": {
            "phase_a": [{"exercise_id": "vlak:production_prompted", "type": "concept_retrieve",
                         "item_id": "vlak", "mode": "production_prompted",
                         "prompt": "train", "instruction": "Say it in Slovak."}],
            "phase_b": [{"introduce": {"item_id": "ahoj", "slovak": "ahoj",
                                        "english": "hi", "register": "informal"},
                         "exercise": {"exercise_id": "ahoj:production_prompted",
                                      "type": "concept_retrieve", "item_id": "ahoj",
                                      "mode": "production_prompted", "prompt": "hi",
                                      "instruction": "Say it in Slovak."}}],
            "phase_c": {"mission_id": "bratislava_arrival", "title": "Arrival",
                        "region": "Bratislava", "briefing": "Buy a ticket."}
          }
        }
        """.data(using: .utf8)!
        let session = try JSONDecoder().decode(LearningSession.self, from: json)
        XCTAssertEqual(session.plan.phaseC.missionId, "bratislava_arrival")
        XCTAssertEqual(session.plan.phaseA.first?.itemId, "vlak")
        XCTAssertEqual(session.plan.phaseB.first?.introduce.slovak, "ahoj")
    }

    func testAttemptResultNeverCarriesNumericPronunciation() throws {
        let json = """
        {"attempt_id": 5, "semantic_success": true, "error_tags": [],
         "xp_awarded": 5, "pronunciation_status": "unknown",
         "focus": {"state": "ok"}, "note": null}
        """.data(using: .utf8)!
        let result = try JSONDecoder().decode(AttemptResult.self, from: json)
        XCTAssertEqual(result.pronunciationStatus, "unknown")  // a status, not a score
    }
}
