import HovorKit
import SwiftUI

/// The Journey Home: campaign regions with mission progress. The map is a
/// game layer — unlock state comes from the backend, never computed here.
struct MapView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        NavigationStack {
            List {
                ForEach(model.map?.regions ?? []) { region in
                    Section {
                        ForEach(region.missions, id: \.missionId) { mission in
                            HStack {
                                Image(systemName: mission.completed ? "checkmark.seal.fill" : "circle")
                                    .foregroundStyle(mission.completed ? .green : .secondary)
                                Text(mission.title)
                                Spacer()
                                if mission.noEnglishAvailable {
                                    Text("SK only")
                                        .font(.caption2)
                                        .padding(.horizontal, 6)
                                        .background(.yellow.opacity(0.2), in: Capsule())
                                }
                            }
                        }
                    } header: {
                        HStack {
                            if !region.unlocked { Image(systemName: "lock.fill") }
                            Text(region.title)
                        }
                    }
                    .disabled(!region.unlocked)
                }
            }
            .navigationTitle(model.map?.title ?? "The Journey Home")
        }
    }
}
