import HovorKit
import SwiftUI

/// Phase A/B exercise runner. Latency is captured from prompt display to
/// submission — it feeds the learner model's retrieval-strength estimate.
struct SessionView: View {
    @Environment(AppModel.self) private var model
    @State private var queue: [Step] = []
    @State private var answer = ""
    @State private var feedback: AttemptResult?
    @State private var promptShownAt = Date()

    enum Step {
        case introduce(Introduction)
        case exercise(Exercise)
        case mission(MissionBrief)
    }

    var body: some View {
        NavigationStack {
            Group {
                if let step = queue.first {
                    stepView(step)
                } else {
                    Button("Start session") {
                        Task {
                            await model.startSession()
                            buildQueue()
                        }
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
            .navigationTitle("HOVOR!")
        }
    }

    @ViewBuilder
    private func stepView(_ step: Step) -> some View {
        switch step {
        case .introduce(let intro):
            VStack(spacing: 12) {
                Text(intro.slovak).font(.largeTitle.bold())
                Text(intro.english).foregroundStyle(.secondary)
                Button("Got it") { advance() }.buttonStyle(.borderedProminent)
            }
        case .exercise(let ex):
            VStack(spacing: 12) {
                Text(ex.prompt).font(.largeTitle.bold())
                Text(ex.instruction).foregroundStyle(.secondary)
                TextField("po slovensky...", text: $answer)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { Task { await submit(ex) } }
                if let feedback {
                    Text(feedback.semanticSuccess ? "✓ +\(feedback.xpAwarded) XP" : "✗ \(feedback.errorTags.joined(separator: ", "))")
                        .foregroundStyle(feedback.semanticSuccess ? .green : .red)
                    Button("Continue") { advance() }.buttonStyle(.borderedProminent)
                }
            }
            .padding()
            .onAppear { promptShownAt = Date() }
        case .mission(let brief):
            MissionView(brief: brief)
        }
    }

    private func buildQueue() {
        guard let plan = model.session?.plan else { return }
        queue = plan.phaseA.map(Step.exercise)
        for item in plan.phaseB {
            queue.append(.introduce(item.introduce))
            queue.append(.exercise(item.exercise))
        }
        queue.append(.mission(plan.phaseC))
    }

    private func submit(_ ex: Exercise) async {
        guard let user = model.user else { return }
        feedback = try? await model.api.submitAttempt(
            userId: user.id,
            sessionId: model.session?.sessionId,
            exerciseId: ex.exerciseId,
            response: answer,
            latencyMs: Int(Date().timeIntervalSince(promptShownAt) * 1000)
        )
    }

    private func advance() {
        answer = ""
        feedback = nil
        if !queue.isEmpty { queue.removeFirst() }
    }
}
