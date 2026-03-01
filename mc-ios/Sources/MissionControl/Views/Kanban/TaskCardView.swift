import SwiftUI

struct TaskCardView: View {
    @Environment(TaskStore.self) private var taskStore
    let task: MCTask
    let onTap: () -> Void

    @State private var errorMessage: String?
    @State private var showError = false

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 8) {
                // Title
                Text(task.title)
                    .font(.headline)
                    .foregroundStyle(.primary)
                    .multilineTextAlignment(.leading)
                    .lineLimit(2)

                // Assigned agent
                if let agent = task.assignedAgent {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(Color.green)
                            .frame(width: 8, height: 8)
                        Text(agent)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                }

                // Tag chips
                if let tags = task.tags, !tags.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 4) {
                            ForEach(tags, id: \.self) { tag in
                                Text(tag)
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                    .foregroundStyle(.primary)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 3)
                                    .glassEffect(.regular.tint(.accentColor), in: .capsule)
                            }
                        }
                    }
                }

                // Bottom row: file indicator + favorite star
                HStack {
                    if let files = task.files, !files.isEmpty {
                        HStack(spacing: 4) {
                            Image(systemName: "paperclip")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text("\(files.count)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }

                    Spacer()

                    if task.isFavorite == true {
                        Image(systemName: "star.fill")
                            .font(.caption)
                            .foregroundStyle(.yellow)
                            .symbolEffect(.bounce, value: task.isFavorite)
                    }
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .glassEffect(.regular.interactive(), in: .rect(cornerRadius: 10))
        }
        .buttonStyle(.plain)
        .contextMenu {
            Button {
                Task {
                    do {
                        try await taskStore.toggleFavorite(taskId: task.id)
                    } catch {
                        errorMessage = error.localizedDescription
                        showError = true
                    }
                }
            } label: {
                Label(
                    task.isFavorite == true ? "Remove from Favorites" : "Add to Favorites",
                    systemImage: task.isFavorite == true ? "star.slash" : "star"
                )
            }

            Menu("Move to...") {
                ForEach(kanbanStatuses, id: \.self) { status in
                    if status != task.status {
                        Button(status.displayName) {
                            Task {
                                do {
                                    try await taskStore.updateStatus(taskId: task.id, status: status)
                                } catch {
                                    errorMessage = error.localizedDescription
                                    showError = true
                                }
                            }
                        }
                    }
                }
            }

            Divider()

            Button(role: .destructive) {
                Task {
                    do {
                        try await taskStore.softDelete(taskId: task.id)
                    } catch {
                        errorMessage = error.localizedDescription
                        showError = true
                    }
                }
            } label: {
                Label("Delete", systemImage: "trash")
            }
        }
        .alert("Error", isPresented: $showError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(errorMessage ?? "An error occurred")
        }
    }

    private let kanbanStatuses: [TaskStatus] = [
        .inbox, .assigned, .inProgress, .review, .done
    ]
}
