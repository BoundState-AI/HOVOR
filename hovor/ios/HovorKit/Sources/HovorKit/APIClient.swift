// Thin async client for the HOVOR! backend. One method per endpoint the
// web client uses — the contracts are already exercised end to end by the
// backend test suite.

import Foundation

public struct APIClient: Sendable {
    public let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    // MARK: - users

    public func createUser(name: String) async throws -> User {
        try await post("users", body: ["name": name])
    }

    public func map(userId: Int) async throws -> CampaignMap {
        try await get("users/\(userId)/map")
    }

    // MARK: - learning sessions

    public func startSession(userId: Int) async throws -> LearningSession {
        try await post("learning-sessions", body: ["user_id": userId])
    }

    public func debrief(sessionId: Int) async throws -> [String: AnyCodable] {
        try await get("learning-sessions/\(sessionId)/debrief")
    }

    // MARK: - attempts

    public func submitAttempt(
        userId: Int, sessionId: Int?, exerciseId: String, response: String,
        latencyMs: Int?, inputMode: String = "text"
    ) async throws -> AttemptResult {
        var body: [String: AnyCodable] = [
            "user_id": .init(userId),
            "exercise_id": .init(exerciseId),
            "response": .init(response),
            "input_mode": .init(inputMode),
        ]
        if let sessionId { body["session_id"] = .init(sessionId) }
        if let latencyMs { body["latency_ms"] = .init(latencyMs) }
        return try await post("attempts", body: body)
    }

    // MARK: - voice missions (control plane; audio rides WebRTC separately)

    public func startVoiceSession(
        userId: Int, missionId: String, learningSessionId: Int?, noEnglish: Bool = false
    ) async throws -> [String: AnyCodable] {
        var body: [String: AnyCodable] = [
            "user_id": .init(userId),
            "mission_id": .init(missionId),
            "no_english": .init(noEnglish),
        ]
        if let learningSessionId { body["learning_session_id"] = .init(learningSessionId) }
        return try await post("voice-sessions", body: body)
    }

    public func sendTurn(voiceSessionId: Int, text: String) async throws -> VoiceTurnResult {
        try await post("voice-sessions/\(voiceSessionId)/turns", body: ["text": text])
    }

    public func interrupt(voiceSessionId: Int) async throws {
        let _: [String: AnyCodable] = try await post("voice-sessions/\(voiceSessionId)/interrupt", body: [String: String]())
    }

    // MARK: - plumbing

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let (data, _) = try await session.data(from: baseURL.appending(path: "api/v1/\(path)"))
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func post<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        var request = URLRequest(url: baseURL.appending(path: "api/v1/\(path)"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(T.self, from: data)
    }
}

/// Minimal type-erased Codable for heterogeneous payloads.
public struct AnyCodable: Codable, Sendable {
    public let value: Sendable

    public init(_ value: Int) { self.value = value }
    public init(_ value: String) { self.value = value }
    public init(_ value: Bool) { self.value = value }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let v = try? container.decode(Bool.self) { value = v }
        else if let v = try? container.decode(Int.self) { value = v }
        else if let v = try? container.decode(Double.self) { value = v }
        else if let v = try? container.decode(String.self) { value = v }
        else if let v = try? container.decode([String: AnyCodable].self) { value = v }
        else if let v = try? container.decode([AnyCodable].self) { value = v }
        else { value = Optional<String>.none as Any as! Sendable }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case let v as Bool: try container.encode(v)
        case let v as Int: try container.encode(v)
        case let v as Double: try container.encode(v)
        case let v as String: try container.encode(v)
        case let v as [String: AnyCodable]: try container.encode(v)
        case let v as [AnyCodable]: try container.encode(v)
        default: try container.encodeNil()
        }
    }
}
