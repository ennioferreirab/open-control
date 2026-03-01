import SwiftUI

struct KanbanBoardView: View {
    @Environment(TaskStore.self) private var taskStore
    @Environment(BoardStore.self) private var boardStore
    @Environment(\.horizontalSizeClass) private var sizeClass

    @State private var searchText = ""
    @State private var selectedTags: Set<String> = []
    @State private var selectedTask: MCTask?

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
                    // TODO: new task creation
                } label: {
                    Image(systemName: "plus")
                }
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
    }

    // MARK: - Compact (iPhone) layout

    private var compactBoard: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(alignment: .top, spacing: 12) {
                ForEach(visibleStatuses, id: \.self) { status in
                    KanbanColumnView(
                        status: status,
                        tasks: filteredTasks(for: status),
                        onTaskTap: { task in selectedTask = task }
                    )
                    .frame(width: 280)
                    .frame(maxHeight: 600)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }

    // MARK: - Regular (iPad/Mac) layout

    private var regularBoard: some View {
        HStack(alignment: .top, spacing: 12) {
            ForEach(visibleStatuses, id: \.self) { status in
                KanbanColumnView(
                    status: status,
                    tasks: filteredTasks(for: status),
                    onTaskTap: { task in selectedTask = task }
                )
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
    }
}
