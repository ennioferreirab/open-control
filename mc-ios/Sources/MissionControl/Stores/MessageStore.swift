import Foundation
import Observation
import ConvexMobile

@Observable
@MainActor
final class MessageStore {
    var messages: [MCMessage] = []
    var isLoading = false
    var error: String?
    private(set) var currentTaskId: String?

    private var subscriptionTask: Task<Void, Never>?

    deinit {
        subscriptionTask?.cancel()
    }

    // MARK: - Computed

    var workMessages: [MCMessage] {
        messages.filter { $0.messageType == .work }
    }

    var systemMessages: [MCMessage] {
        messages.filter { $0.messageType == .systemEvent }
    }

    // MARK: - Subscription

    func setTask(_ taskId: String) {
        guard taskId != currentTaskId else { return }
        currentTaskId = taskId
        subscriptionTask?.cancel()
        subscriptionTask = Task { [weak self] in
            await self?.subscribeToMessages(taskId: taskId)
        }
    }

    func clearTask() {
        currentTaskId = nil
        subscriptionTask?.cancel()
        messages = []
    }

    private func subscribeToMessages(taskId: String) async {
        guard let client = ConvexClientManager.shared.client else {
            error = "No Convex client available"
            return
        }
        isLoading = true

        let stream = client.subscribe(to: "messages:listByTask", with: ["taskId": taskId], yielding: [MCMessage].self)
            .replaceError(with: [])
            .values

        for await updatedMessages in stream {
            guard !Task.isCancelled else { break }
            if isLoading { isLoading = false }
            messages = updatedMessages
        }
    }

    // MARK: - Mutations

    func sendMessage(taskId: String, content: String, authorName: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("messages:send", with: [
            "taskId": taskId,
            "content": content,
            "authorName": authorName,
            "authorType": AuthorType.user.rawValue,
            "messageType": MessageType.userMessage.rawValue
        ])
    }

    func addComment(taskId: String, content: String, authorName: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("messages:send", with: [
            "taskId": taskId,
            "content": content,
            "authorName": authorName,
            "authorType": AuthorType.user.rawValue,
            "messageType": MessageType.comment.rawValue
        ])
    }
}
