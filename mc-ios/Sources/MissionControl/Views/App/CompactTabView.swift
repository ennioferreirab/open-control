import SwiftUI

struct CompactTabView: View {
    @SceneStorage("compactTab.selectedTab") private var selectedTab: String = "tasks"
    @FocusState private var isSearchFocused: Bool

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack {
                KanbanBoardView()
            }
            .tabItem { Label("Tasks", systemImage: "square.grid.2x2") }
            .tag("tasks")

            NavigationStack {
                AgentListView()
            }
            .tabItem { Label("Agents", systemImage: "cpu") }
            .tag("agents")

            NavigationStack {
                ChatPlaceholderView()
            }
            .tabItem { Label("Chat", systemImage: "bubble.left.and.bubble.right") }
            .tag("chat")

            NavigationStack {
                SettingsView()
            }
            .tabItem { Label("Settings", systemImage: "gear") }
            .tag("settings")
        }
        .keyboardShortcut(.tab, modifiers: [])
        .onKeyPress(.init("1"), phases: .down) { _ in
            selectedTab = "tasks"; return .handled
        }
        .onKeyPress(.init("2"), phases: .down) { _ in
            selectedTab = "agents"; return .handled
        }
        .onKeyPress(.init("3"), phases: .down) { _ in
            selectedTab = "chat"; return .handled
        }
        .onKeyPress(.init("4"), phases: .down) { _ in
            selectedTab = "settings"; return .handled
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
