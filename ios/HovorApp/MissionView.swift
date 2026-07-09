import AVFoundation
import HovorKit
import Speech
import SwiftUI

/// The voice mission screen — the centerpiece. Push-to-talk today
/// (on-device sk-SK speech recognition → text turn to the backend mission
/// engine); the same view swaps to full-duplex audio when a realtime
/// provider replaces MockVoiceProvider behind VoiceProviding.
struct MissionView: View {
    @Environment(AppModel.self) private var model
    let brief: MissionBrief

    @State private var provider: MockVoiceProvider?
    @State private var messages: [Message] = []
    @State private var draft = ""
    @State private var listening = false
    @State private var recognizer = SlovakRecognizer()

    struct Message: Identifiable {
        let id = UUID()
        let role: Role
        let text: String
        enum Role { case tutor, learner, system }
    }

    var body: some View {
        VStack(spacing: 0) {
            Text(brief.briefing)
                .font(.callout)
                .foregroundStyle(.secondary)
                .padding()

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 8) {
                    ForEach(messages) { message in
                        bubble(message)
                    }
                }
                .padding(.horizontal)
            }

            HStack {
                TextField("Povedz niečo po slovensky...", text: $draft)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { send(draft) }
                Button {
                    toggleListening()
                } label: {
                    Image(systemName: listening ? "mic.fill" : "mic")
                        .foregroundStyle(listening ? .red : .accentColor)
                }
                Button("Say") { send(draft) }
                    .buttonStyle(.borderedProminent)
            }
            .padding()
        }
        .navigationTitle(brief.title)
        .task { await start() }
    }

    @ViewBuilder
    private func bubble(_ message: Message) -> some View {
        HStack {
            if message.role == .learner { Spacer() }
            Text(message.text)
                .padding(10)
                .background(
                    message.role == .tutor ? Color(.secondarySystemBackground) : Color.accentColor.opacity(0.25),
                    in: RoundedRectangle(cornerRadius: 12)
                )
            if message.role == .tutor { Spacer() }
        }
    }

    private func start() async {
        guard let user = model.user else { return }
        let mock = MockVoiceProvider(
            api: model.api, userId: user.id,
            learningSessionId: model.session?.sessionId
        )
        provider = mock
        Task {
            for await event in mock.events {
                handle(event)
            }
        }
        try? await mock.createSession(.init(missionId: brief.missionId))
    }

    private func handle(_ event: ProviderEvent) {
        switch event {
        case .responseCompleted(let text):
            messages.append(.init(role: .tutor, text: text))
        case .finalTranscript(let text):
            messages.append(.init(role: .learner, text: text))
        case .error(let message):
            messages.append(.init(role: .system, text: "⚠ \(message)"))
        default:
            break
        }
    }

    private func send(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty, let provider else { return }
        draft = ""
        Task { try? await provider.send(text: trimmed) }
    }

    private func toggleListening() {
        listening.toggle()
        if listening {
            recognizer.start { transcript in
                draft = transcript
                listening = false
            }
        } else {
            recognizer.stop()
        }
    }
}

/// On-device Slovak speech recognition (sk-SK) for push-to-talk.
@Observable
final class SlovakRecognizer {
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "sk-SK"))
    private let audioEngine = AVAudioEngine()
    private var task: SFSpeechRecognitionTask?

    func start(onFinal: @escaping (String) -> Void) {
        SFSpeechRecognizer.requestAuthorization { status in
            guard status == .authorized else { return }
            DispatchQueue.main.async { self.begin(onFinal: onFinal) }
        }
    }

    private func begin(onFinal: @escaping (String) -> Void) {
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = false
        let input = audioEngine.inputNode
        input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { buffer, _ in
            request.append(buffer)
        }
        audioEngine.prepare()
        try? audioEngine.start()
        task = recognizer?.recognitionTask(with: request) { result, _ in
            if let result, result.isFinal {
                onFinal(result.bestTranscription.formattedString)
                self.stop()
            }
        }
    }

    func stop() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        task?.cancel()
        task = nil
    }
}
