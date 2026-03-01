import Foundation
import Observation
@preconcurrency import ConvexMobile

@Observable
@MainActor
final class TagStore {
    var tags: [MCTag] = []
    var isLoading = false
    var error: String?

    nonisolated(unsafe) private var subscriptionTask: Task<Void, Never>?

    deinit {
        subscriptionTask?.cancel()
    }

    // MARK: - Subscription

    func startSubscription() {
        subscriptionTask?.cancel()
        subscriptionTask = Task { [weak self] in
            await self?.subscribeToTags()
        }
    }

    private func subscribeToTags() async {
        guard let client = ConvexClientManager.shared.client else {
            error = "No Convex client available"
            return
        }
        isLoading = true

        let stream = client.subscribe(to: "taskTags:list", yielding: [MCTag].self)
            .replaceError(with: [])
            .values

        for await updatedTags in stream {
            guard !Task.isCancelled else { break }
            if isLoading { isLoading = false }
            tags = updatedTags
        }
    }

    // MARK: - Mutations

    func createTag(name: String, color: TagColor) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        let args: [String: ConvexEncodable?] = ["name": name, "color": color.rawValue]
        try await client.mutation("taskTags:create", with: args)
    }

    func deleteTag(tagId: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("taskTags:delete", with: ["tagId": tagId])
    }
}
