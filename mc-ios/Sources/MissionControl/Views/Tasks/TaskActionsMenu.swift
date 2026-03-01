import SwiftUI
#if os(iOS)
import UIKit
#endif

struct TaskActionsMenu: View {
    @Environment(TaskStore.self) private var taskStore

    let task: MCTask
    var onDelete: (() -> Void)? = nil

    @State private var showDeleteConfirmation = false
    @State private var showDenyAlert = false
    @State private var denyFeedback = ""
    @State private var errorMessage: String?
    @State private var showError = false

    var body: some View {
        Menu {
            statusActions
            Divider()
            Button(role: .destructive) {
                showDeleteConfirmation = true
            } label: {
                Label("Delete", systemImage: "trash")
            }
        } label: {
            Image(systemName: "ellipsis.circle")
                .accessibilityLabel("Task actions")
        }
        .confirmationDialog(
            "Delete "\(task.title)"?",
            isPresented: $showDeleteConfirmation,
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) {
                performAction {
                    try await taskStore.softDelete(taskId: task.id)
                    onDelete?()
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This action cannot be undone.")
        }
        .alert("Deny Task", isPresented: $showDenyAlert) {
            TextField("Feedback", text: $denyFeedback)
            Button("Send Denial") {
                let feedback = denyFeedback
                denyFeedback = ""
                guard !feedback.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                performAction { try await taskStore.denyTask(taskId: task.id, feedback: feedback) }
            }
            Button("Cancel", role: .cancel) { denyFeedback = "" }
        } message: {
            Text("Explain why this task is being denied.")
        }
        .alert("Error", isPresented: $showError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(errorMessage ?? "An error occurred")
        }
    }

    // MARK: - Status-based Actions

    @ViewBuilder
    private var statusActions: some View {
        switch task.status {
        case .review:
            Button {
                performAction { try await taskStore.updateStatus(taskId: task.id, status: .done) }
            } label: {
                Label("Approve", systemImage: "checkmark.circle")
            }

            Button {
                performAction { try await taskStore.updateStatus(taskId: task.id, status: .inProgress) }
            } label: {
                Label("Resume", systemImage: "play.circle")
            }

            Button {
                showDenyAlert = true
            } label: {
                Label("Deny with Feedback", systemImage: "xmark.circle")
            }

        case .inProgress:
            Button {
                performAction { try await taskStore.updateStatus(taskId: task.id, status: .review) }
            } label: {
                Label("Pause", systemImage: "pause.circle")
            }

        case .crashed, .failed:
            Button {
                performAction { try await taskStore.updateStatus(taskId: task.id, status: .ready) }
            } label: {
                Label("Retry", systemImage: "arrow.clockwise.circle")
            }

        default:
            EmptyView()
        }
    }

    // MARK: - Helpers

    private func performAction(_ action: @escaping () async throws -> Void) {
        Task {
            do {
                try await action()
                triggerHaptic(success: true)
            } catch {
                errorMessage = error.localizedDescription
                showError = true
                triggerHaptic(success: false)
            }
        }
    }

    private func triggerHaptic(success: Bool) {
        #if os(iOS)
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(success ? .success : .error)
        #endif
    }
}
