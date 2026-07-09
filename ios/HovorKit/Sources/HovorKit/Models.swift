// Codable mirrors of the HOVOR! backend contracts (see /openapi.json).
// The backend remains the source of truth for mastery, XP, and errors;
// the client renders and captures.

import Foundation

public struct User: Codable, Identifiable, Sendable {
    public let id: Int
    public let name: String
    public let totalXP: Int

    enum CodingKeys: String, CodingKey {
        case id, name
        case totalXP = "total_xp"
    }
}

public struct MasteryRow: Codable, Sendable {
    public let itemId: String
    public let mode: String
    public let strength: Double
    public let attempts: Int
    public let successes: Int
    public let nextReview: String?

    enum CodingKeys: String, CodingKey {
        case mode, strength, attempts, successes
        case itemId = "item_id"
        case nextReview = "next_review"
    }
}

public struct Exercise: Codable, Sendable {
    public let exerciseId: String
    public let type: String
    public let itemId: String
    public let mode: String
    public let prompt: String
    public let instruction: String
    public let contrastWith: String?
    public let timeBudgetMs: Int?

    enum CodingKeys: String, CodingKey {
        case type, mode, prompt, instruction
        case exerciseId = "exercise_id"
        case itemId = "item_id"
        case contrastWith = "contrast_with"
        case timeBudgetMs = "time_budget_ms"
    }
}

public struct Introduction: Codable, Sendable {
    public let itemId: String
    public let slovak: String
    public let english: String
    public let register: String

    enum CodingKeys: String, CodingKey {
        case slovak, english, register
        case itemId = "item_id"
    }
}

public struct PhaseBItem: Codable, Sendable {
    public let introduce: Introduction
    public let exercise: Exercise
}

public struct MissionBrief: Codable, Sendable {
    public let missionId: String
    public let title: String
    public let region: String
    public let briefing: String

    enum CodingKeys: String, CodingKey {
        case title, region, briefing
        case missionId = "mission_id"
    }
}

public struct SessionPlan: Codable, Sendable {
    public let phaseA: [Exercise]
    public let phaseB: [PhaseBItem]
    public let phaseC: MissionBrief

    enum CodingKeys: String, CodingKey {
        case phaseA = "phase_a"
        case phaseB = "phase_b"
        case phaseC = "phase_c"
    }
}

public struct LearningSession: Codable, Sendable {
    public let sessionId: Int
    public let plan: SessionPlan
    public let contentVersion: String

    enum CodingKeys: String, CodingKey {
        case plan
        case sessionId = "session_id"
        case contentVersion = "content_version"
    }
}

public struct AttemptResult: Codable, Sendable {
    public let attemptId: Int
    public let semanticSuccess: Bool
    public let errorTags: [String]
    public let xpAwarded: Int
    public let pronunciationStatus: String  // never numeric (spec §2.3)
    public let focus: FocusState?
    public let note: String?

    enum CodingKeys: String, CodingKey {
        case focus, note
        case attemptId = "attempt_id"
        case semanticSuccess = "semantic_success"
        case errorTags = "error_tags"
        case xpAwarded = "xp_awarded"
        case pronunciationStatus = "pronunciation_status"
    }
}

public struct FocusState: Codable, Sendable {
    public let state: String
    public let advice: String?
}

public struct VoiceTurnResult: Codable, Sendable {
    public let providerFailure: Bool
    public let tutorText: String?
    public let tutorEnglish: String?
    public let objectivesCompletedThisTurn: [String]?
    public let missionComplete: Bool?
    public let sessionState: String?

    enum CodingKeys: String, CodingKey {
        case providerFailure = "provider_failure"
        case tutorText = "tutor_text"
        case tutorEnglish = "tutor_english"
        case objectivesCompletedThisTurn = "objectives_completed_this_turn"
        case missionComplete = "mission_complete"
        case sessionState = "session_state"
    }
}

public struct Region: Codable, Identifiable, Sendable {
    public let id: String
    public let title: String
    public let unlocked: Bool
    public let missions: [RegionMission]
}

public struct RegionMission: Codable, Sendable {
    public let missionId: String
    public let title: String
    public let completed: Bool
    public let noEnglishAvailable: Bool

    enum CodingKeys: String, CodingKey {
        case title, completed
        case missionId = "mission_id"
        case noEnglishAvailable = "no_english_available"
    }
}

public struct CampaignMap: Codable, Sendable {
    public let campaignId: String
    public let title: String
    public let regions: [Region]

    enum CodingKeys: String, CodingKey {
        case title, regions
        case campaignId = "campaign_id"
    }
}
