import SwiftUI

enum SidebarItem: String, CaseIterable, Identifiable {
    // Boards section
    case tasks = "Tasks"
    case agents = "Agents"
    // Communication section
    case chat = "Chat"
    // General section
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
    @State private var columnVisibility: NavigationSplitViewVisibility = .all
    @State private var selectedTask: MCTask?
    @State private var showCreateTask = false
    @FocusState private var isSearchFocused: Bool

    private var selectedItem: SidebarItem {
        SidebarItem(rawValue: selectedItemRaw) ?? .tasks
    }

    private var selectedItemBinding: Binding<SidebarItem?> {
        Binding(
            get: { selectedItem },
            set: { selectedItemRaw = $0?.rawValue ?? SidebarItem.tasks.rawValue }
        )
    }

    var body: some View {
        NavigationSplitView(columnVisibility: $columnVisibility) {
            sidebarContent
                .navigationSplitViewColumnWidth(min: 180, ideal: 220, max: 280)
        } content: {
            contentColumn
                .navigationSplitViewColumnWidth(min: 400, ideal: 600, max: .infinity)
        } detail: {
            detailColumn
                .navigationSplitViewColumnWidth(min: 300, ideal: 380, max: 500)
        }
        .sheet(isPresented: $showCreateTask) {
            CreateTaskView()
        }
        // Keyboard shortcuts: Cmd+1..4 to switch sidebar sections
        .onReceive(NotificationCenter.default.publisher(for: .createNewTask)) { _ in
            showCreateTask = true
        }
        .keyboardShortcut("1", modifiers: .command, action: { selectedItemRaw = SidebarItem.tasks.rawValue })
        .keyboardShortcut("2", modifiers: .command, action: { selectedItemRaw = SidebarItem.agents.rawValue })
        .keyboardShortcut("3", modifiers: .command, action: { selectedItemRaw = SidebarItem.chat.rawValue })
        .keyboardShortcut("4", modifiers: .command, action: { selectedItemRaw = SidebarItem.settings.rawValue })
        .keyboardShortcut("n", modifiers: .command, action: { showCreateTask = true })
        .keyboardShortcut("r", modifiers: .command, action: {
            NotificationCenter.default.post(name: .refreshTasks, object: nil)
        })
    }

    // MARK: - Sidebar

    private var sidebarContent: some View {
        List(selection: selectedItemBinding) {
            Section("Boards") {
                Label(SidebarItem.tasks.rawValue, systemImage: SidebarItem.tasks.systemImage)
                    .tag(SidebarItem.tasks)
                Label(SidebarItem.agents.rawValue, systemImage: SidebarItem.agents.systemImage)
                    .tag(SidebarItem.agents)
            }
            Section("Communication") {
                Label(SidebarItem.chat.rawValue, systemImage: SidebarItem.chat.systemImage)
                    .tag(SidebarItem.chat)
            }
            Section("General") {
                Label(SidebarItem.settings.rawValue, systemImage: SidebarItem.settings.systemImage)
                    .tag(SidebarItem.settings)
            }
        }
        .navigationTitle("Mission Control")
        .listStyle(.sidebar)
    }

    // MARK: - Content column

    @ViewBuilder
    private var contentColumn: some View {
        switch selectedItem {
        case .tasks:
            NavigationStack {
                KanbanBoardView()
            }
        case .agents:
            NavigationStack {
                AgentListView()
            }
        case .chat:
            NavigationStack {
                ChatPlaceholderView()
            }
        case .settings:
            NavigationStack {
                SettingsView()
            }
        }
    }

    // MARK: - Detail column

    @ViewBuilder
    private var detailColumn: some View {
        if let task = selectedTask {
            NavigationStack {
                TaskDetailView(task: task)
            }
        } else {
            ContentUnavailableView(
                "No Task Selected",
                systemImage: "square.dashed",
                description: Text("Select a task from the board to view details")
            )
        }
    }
}

// MARK: - View+KeyboardShortcut helper

private extension View {
    func keyboardShortcut(_ key: KeyEquivalent, modifiers: EventModifiers = .command, action: @escaping () -> Void) -> some View {
        self.background(
            Button("") { action() }
                .keyboardShortcut(key, modifiers: modifiers)
                .opacity(0)
                .allowsHitTesting(false)
        )
    }
}
