import Foundation
import Observation
@preconcurrency import ConvexMobile

@Observable
@MainActor
final class ChatStore {
    var messages: [MCChat] = []
    var isLoading = false
    var error: String?
    private(set) var currentAgentName: String?

    nonisolated(unsafe) private var subscriptionTask: Task<Void, Never>?

    deinit {
        subscriptionTask?.cancel()
    }

    // MARK: - Subscription

    func setAgent(_ agentName: String) {
        guard agentName != currentAgentName else { return }
        currentAgentName = agentName
        messages = []
        subscriptionTask?.cancel()
        subscriptionTask = Task { [weak self] in
            await self?.subscribeToChats(agentName: agentName)
        }
    }

    private func subscribeToChats(agentName: String) async {
        guard let client = ConvexClientManager.shared.client else {
            error = "No Convex client available"
            return
        }
        isLoading = true

        let stream = client.subscribe(to: "chats:listByAgent", with: ["agentName": agentName], yielding: [MCChat].self)
            .replaceError(with: [])
            .values

        for await updatedMessages in stream {
            guard !Task.isCancelled else { break }
            if isLoading { isLoading = false }
            messages = updatedMessages
        }
    }

    // MARK: - Mutations

    func sendMessage(agentName: String, content: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        let args: [String: ConvexEncodable?] = [
            "agentName": agentName,
            "content": content,
            "authorName": "user",
            "authorType": ChatAuthorType.user.rawValue
        ]
        try await client.mutation("chats:send", with: args)
    }
}
