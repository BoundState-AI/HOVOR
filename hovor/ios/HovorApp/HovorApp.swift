// HOVOR! iOS app shell. Voice is the product: the mission screen is the
// centerpiece; exercises and map support it.

import HovorKit
import SwiftUI

@main
struct HovorApp: App {
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
        }
    }
}

@Observable
final class AppModel {
    var api = APIClient(baseURL: URL(string: "http://localhost:8000")!)
    var user: User?
    var session: LearningSession?
    var map: CampaignMap?

    func ensureUser(named name: String) async {
        if user == nil {
            user = try? await api.createUser(name: name)
        }
        if let user {
            map = try? await api.map(userId: user.id)
        }
    }

    func startSession() async {
        guard let user else { return }
        session = try? await api.startSession(userId: user.id)
    }
}

struct RootView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        TabView {
            MapView()
                .tabItem { Label("Journey", systemImage: "map") }
            SessionView()
                .tabItem { Label("Learn", systemImage: "bubble.left.and.bubble.right") }
        }
        .task { await model.ensureUser(named: "Učeník") }
    }
}
