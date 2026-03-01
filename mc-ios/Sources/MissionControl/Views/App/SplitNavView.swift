import SwiftUI

enum SidebarItem: String, CaseIterable, Identifiable {
    // Boards section
    case tasks = "Tasks"
    case agents = "Agents"
    // Top-level
    case chat = "Chat"
    case settings = "Settings"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .tasks: return "square.grid.2x2"
        case .agents: return "cpu"
        case .chat: return "bubble.left.and.bubble.right"
        case .settings: return "gear"
        }
    }

    var section: String {
        switch self {
        case .tasks, .agents: return "Boards"
        case .chat: return "Communication"
        case .settings: return "General"
        }
    }
}

struct SplitNavView: View {
    @SceneStorage("splitNav.selectedItem") private var selectedItemRaw: String = SidebarItem.tasks.rawValue

    private var selectedItem: SidebarItem {
        get { SidebarItem(rawValue: selectedItemRaw) ?? .tasks }
    }

    var body: some View {
        NavigationSplitView {
            List(SidebarItem.allCases, id: \.id, selection: Binding(
                get: { selectedItem },
                set: { selectedItemRaw = $0?.rawValue ?? SidebarItem.tasks.rawValue }
            )) { item in
                Label(item.rawValue, systemImage: item.systemImage)
                    .tag(item)
            }
            .navigationTitle("Mission Control")
            .listStyle(.sidebar)
        } detail: {
            NavigationStack {
                detailView(for: selectedItem)
            }
        }
    }

    @ViewBuilder
    private func detailView(for item: SidebarItem) -> some View {
        switch item {
        case .tasks:
            TasksPlaceholderView()
        case .agents:
            AgentListView()
        case .chat:
            ChatPlaceholderView()
        case .settings:
            SettingsView()
        }
    }
}
