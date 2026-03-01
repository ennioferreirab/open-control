import SwiftUI

enum TaskDetailTab: String, CaseIterable {
    case thread = "Thread"
    case plan = "Plan"
    case files = "Files"
    case activity = "Activity"
}

struct TaskDetailView: View {
    @Environment(TaskStore.self) private var taskStore
    @Environment(MessageStore.self) private var messageStore
    @Environment(StepStore.self) private var stepStore
    @Environment(ActivityStore.self) private var activityStore
    @Environment(\.dismiss) private var dismiss

    let task: MCTask
    @State private var selectedTab: TaskDetailTab = .thread

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                headerSection

                Picker("Tab", selection: $selectedTab) {
                    ForEach(TaskDetailTab.allCases, id: \.self) { tab in
                        Text(tab.rawValue).tag(tab)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)

                Divider()

                tabContent
                    .animation(.spring(duration: 0.3), value: selectedTab)
            }
            .navigationTitle(task.title)
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
                ToolbarItemGroup(placement: .primaryAction) {
                    toolbarActions
                }
            }
        }
        .task {
            messageStore.setTask(task.id)
            stepStore.setTask(task.id)
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(task.status.displayName)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(task.status.color)
                    .clipShape(Capsule())

                if let agent = task.assignedAgent {
                    HStack(spacing: 4) {
                        Image(systemName: "cpu")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text(agent)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Spacer()

                if task.isFavorite == true {
                    Image(systemName: "star.fill")
                        .foregroundStyle(.yellow)
                        .font(.caption)
                }
            }

            if let description = task.description, !description.isEmpty {
                Text(description)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(3)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 12)
        .padding(.bottom, 8)
    }

    // MARK: - Tab Content

    @ViewBuilder
    private var tabContent: some View {
        switch selectedTab {
        case .thread:
            ThreadView(taskId: task.id)
        case .plan:
            ExecutionPlanView()
        case .files:
            FilesTabView(task: task)
        case .activity:
            ActivityTabView(taskId: task.id)
        }
    }

    // MARK: - Toolbar Actions

    @ViewBuilder
    private var toolbarActions: some View {
        if task.status == .review {
            Button {
                Task {
                    do {
                        try await taskStore.updateStatus(taskId: task.id, status: .done)
                    } catch {}
                }
            } label: {
                Image(systemName: "checkmark")
                    .foregroundStyle(.green)
            }
            .accessibilityLabel("Approve task")
        }

        if task.status == .inProgress || task.status == .assigned {
            Button {
                Task {
                    do {
                        try await taskStore.updateStatus(taskId: task.id, status: .review)
                    } catch {}
                }
            } label: {
                Image(systemName: "pause")
                    .foregroundStyle(.orange)
            }
            .accessibilityLabel("Pause task")
        }

        if task.status == .failed || task.status == .crashed {
            Button {
                Task {
                    do {
                        try await taskStore.updateStatus(taskId: task.id, status: .ready)
                    } catch {}
                }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .foregroundStyle(.blue)
            }
            .accessibilityLabel("Retry task")
        }

        Button(role: .destructive) {
            Task {
                do {
                    try await taskStore.softDelete(taskId: task.id)
                    dismiss()
                } catch {}
            }
        } label: {
            Image(systemName: "trash")
                .foregroundStyle(.red)
        }
        .accessibilityLabel("Delete task")
    }

}
