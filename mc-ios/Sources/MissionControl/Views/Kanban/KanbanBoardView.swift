import SwiftUI

struct KanbanBoardView: View {
    @Environment(TaskStore.self) private var taskStore
    @Environment(BoardStore.self) private var boardStore
    @Environment(\.horizontalSizeClass) private var sizeClass

    /// When provided (iPad/Mac split view), tapping a task calls this instead of presenting a sheet.
    var onTaskSelected: ((MCTask) -> Void)? = nil

    @State private var searchText = ""
    @State private var selectedTags: Set<String> = []
    @State private var selectedTask: MCTask?
    @State private var showCreateTask = false

    private let visibleStatuses: [TaskStatus] = [.inbox, .assigned, .inProgress, .review, .done]

    // Collect unique tag names across all visible tasks for the filter bar
    private var allUniqueTags: [String] {
        var seen = Set<String>()
        return visibleStatuses
            .flatMap { taskStore.tasksByStatus[$0] ?? [] }
            .compactMap(\.tags)
            .flatMap { $0 }
            .filter { seen.insert($0).inserted }
    }

    private func filteredTasks(for status: TaskStatus) -> [MCTask] {
        (taskStore.tasksByStatus[status] ?? []).filter { task in
            let matchesSearch = searchText.isEmpty
                || task.title.localizedCaseInsensitiveContains(searchText)
                || (task.description?.localizedCaseInsensitiveContains(searchText) ?? false)
            let matchesTags = selectedTags.isEmpty
                || selectedTags.isSubset(of: Set(task.tags ?? []))
            return matchesSearch && matchesTags
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            TagFilterBar(tags: allUniqueTags, selectedTags: $selectedTags)

            if sizeClass == .compact {
                compactBoard
            } else {
                regularBoard
            }
        }
        .navigationTitle("Board")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                BoardSelectorView()
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showCreateTask = true
                } label: {
                    Image(systemName: "plus")
                }
                .accessibilityLabel("Create new task")
            }
        }
        .searchable(text: $searchText, prompt: "Search tasks…")
        .refreshable {
            if let boardId = taskStore.currentBoardId {
                taskStore.setBoard(boardId)
            }
        }
        .sheet(item: $selectedTask) { task in
            TaskDetailView(task: task)
        }
        .sheet(isPresented: $showCreateTask) {
            CreateTaskView()
        }
        .onReceive(NotificationCenter.default.publisher(for: .refreshTasks)) { _ in
            if let boardId = taskStore.currentBoardId {
                taskStore.setBoard(boardId)
            }
        }
    }

    // MARK: - Compact (iPhone) layout

    private var compactBoard: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            GlassEffectContainer(spacing: 12) {
                HStack(alignment: .top, spacing: 12) {
                    ForEach(visibleStatuses, id: \.self) { status in
                        KanbanColumnView(
                            status: status,
                            tasks: filteredTasks(for: status),
                            onTaskTap: { task in
                                if let onTaskSelected {
                                    onTaskSelected(task)
                                } else {
                                    selectedTask = task
                                }
                            }
                        )
                        .containerRelativeFrame(.horizontal) { width, _ in
                            min(280, width * 0.75)
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }

    // MARK: - Regular (iPad/Mac) layout

    private var regularBoard: some View {
        GlassEffectContainer(spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                ForEach(visibleStatuses, id: \.self) { status in
                    KanbanColumnView(
                        status: status,
                        tasks: filteredTasks(for: status),
                        onTaskTap: { task in
                            if let onTaskSelected {
                                onTaskSelected(task)
                            } else {
                                selectedTask = task
                            }
                        }
                    )
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
    }
}
