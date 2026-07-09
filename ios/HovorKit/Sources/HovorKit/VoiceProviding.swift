// Swift mirror of the backend's provider-neutral voice boundary (spec §7).
// The OpenAI Realtime implementation owns the WebRTC audio leg; the backend
// voice-session endpoints stay the control plane (objectives, scoring,
// mission state). No provider event format crosses above this protocol.

import AVFoundation
import Foundation

public enum ProviderEvent: Sendable {
    case speechStarted
    case speechStopped
    case partialTranscript(String)
    case finalTranscript(String)
    case responseStarted
    case audioDelta(Data)
    case responseCompleted(text: String)
    case interruption
    case error(String)
}

public struct VoiceSessionConfig: Sendable {
    public var missionId: String
    public var noEnglish: Bool
    public var voice: String

    public init(missionId: String, noEnglish: Bool = false, voice: String = "marin") {
        self.missionId = missionId
        self.noEnglish = noEnglish
        self.voice = voice
    }
}

public protocol VoiceProviding: Sendable {
    var events: AsyncStream<ProviderEvent> { get }

    func createSession(_ config: VoiceSessionConfig) async throws
    func send(audio buffer: AVAudioPCMBuffer) async throws
    func send(text: String) async throws
    func interrupt() async
    func close() async
}

/// Offline/dev provider: routes text turns through the backend's mock
/// mission engine — identical semantics to the web client's push-to-talk
/// path, no key or network audio required. This is also the §32 fallback
/// when a realtime provider dies mid-mission.
public actor MockVoiceProvider: VoiceProviding {
    private let api: APIClient
    private let userId: Int
    private var voiceSessionId: Int?
    private var learningSessionId: Int?
    private var continuation: AsyncStream<ProviderEvent>.Continuation?

    public nonisolated let events: AsyncStream<ProviderEvent>
    private nonisolated let eventsContinuation: AsyncStream<ProviderEvent>.Continuation

    public init(api: APIClient, userId: Int, learningSessionId: Int? = nil) {
        self.api = api
        self.userId = userId
        self.learningSessionId = learningSessionId
        var cont: AsyncStream<ProviderEvent>.Continuation!
        self.events = AsyncStream { cont = $0 }
        self.eventsContinuation = cont
    }

    public func createSession(_ config: VoiceSessionConfig) async throws {
        let response = try await api.startVoiceSession(
            userId: userId, missionId: config.missionId,
            learningSessionId: learningSessionId, noEnglish: config.noEnglish
        )
        if case let .some(id) = response["voice_session_id"]?.value as? Int {
            voiceSessionId = id
        }
        if let opening = response["tutor_text"]?.value as? String {
            eventsContinuation.yield(.responseCompleted(text: opening))
        }
    }

    public func send(audio buffer: AVAudioPCMBuffer) async throws {
        // Mock provider takes no audio; on-device SFSpeechRecognizer (sk-SK)
        // transcribes and the transcript arrives via send(text:).
    }

    public func send(text: String) async throws {
        guard let id = voiceSessionId else { return }
        eventsContinuation.yield(.finalTranscript(text))
        eventsContinuation.yield(.responseStarted)
        let result = try await api.sendTurn(voiceSessionId: id, text: text)
        if result.providerFailure {
            eventsContinuation.yield(.error("provider failure — push-to-talk fallback, nothing scored"))
            return
        }
        eventsContinuation.yield(.responseCompleted(text: result.tutorText ?? ""))
    }

    public func interrupt() async {
        guard let id = voiceSessionId else { return }
        try? await api.interrupt(voiceSessionId: id)
        eventsContinuation.yield(.interruption)
    }

    public func close() async {
        eventsContinuation.finish()
    }
}
