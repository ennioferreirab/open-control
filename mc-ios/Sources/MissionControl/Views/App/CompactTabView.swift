import SwiftUI

struct CompactTabView: View {
    @SceneStorage("compactTab.selectedTab") private var selectedTab: String = "tasks"

    var body: some View {
        TabView(selection: $selectedTab) {
            Tab("Tasks", systemImage: "square.grid.2x2", value: "tasks") {
                NavigationStack {
                    TasksPlaceholderView()
                }
            }

            Tab("Agents", systemImage: "cpu", value: "agents") {
                NavigationStack {
                    AgentsPlaceholderView()
                }
            }

            Tab("Chat", systemImage: "bubble.left.and.bubble.right", value: "chat") {
                NavigationStack {
                    ChatPlaceholderView()
                }
            }

            Tab("Settings", systemImage: "gear", value: "settings") {
                NavigationStack {
                    SettingsView()
                }
            }
        }
    }
}

// MARK: - Placeholder Views

struct TasksPlaceholderView: View {
    var body: some View {
        ContentUnavailableView(
            "Tasks",
            systemImage: "square.grid.2x2",
            description: Text("Your tasks will appear here")
        )
        .navigationTitle("Tasks")
    }
}

struct AgentsPlaceholderView: View {
    var body: some View {
        ContentUnavailableView(
            "Agents",
            systemImage: "cpu",
            description: Text("Connected agents will appear here")
        )
        .navigationTitle("Agents")
    }
}

struct ChatPlaceholderView: View {
    var body: some View {
        ContentUnavailableView(
            "Chat",
            systemImage: "bubble.left.and.bubble.right",
            description: Text("Conversations will appear here")
        )
        .navigationTitle("Chat")
    }
}
