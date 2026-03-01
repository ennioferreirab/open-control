import Foundation
import Observation
@preconcurrency import ConvexMobile

@Observable
@MainActor
final class BoardStore {
    var boards: [MCBoard] = []
    var isLoading = false
    var error: String?

    nonisolated(unsafe) private var subscriptionTask: Task<Void, Never>?

    deinit {
        subscriptionTask?.cancel()
    }

    // MARK: - Computed

    var defaultBoard: MCBoard? {
        boards.first { $0.isDefault == true } ?? boards.first
    }

    var activeBoards: [MCBoard] {
        boards.filter { $0.deletedAt == nil }
    }

    // MARK: - Subscription

    func startSubscription() {
        subscriptionTask?.cancel()
        subscriptionTask = Task { [weak self] in
            await self?.subscribeToBoards()
        }
    }

    private func subscribeToBoards() async {
        guard let client = ConvexClientManager.shared.client else {
            error = "No Convex client available"
            return
        }
        isLoading = true

        let stream = client.subscribe(to: "boards:list", yielding: [MCBoard].self)
            .replaceError(with: [])
            .values

        for await updatedBoards in stream {
            guard !Task.isCancelled else { break }
            if isLoading { isLoading = false }
            boards = updatedBoards
        }
    }

    // MARK: - Mutations

    func createBoard(name: String, displayName: String, description: String? = nil) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        var args: [String: ConvexEncodable?] = ["name": name, "displayName": displayName]
        if let description { args["description"] = description }
        try await client.mutation("boards:create", with: args)
    }

    func updateBoard(boardId: String, displayName: String, description: String?) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        var args: [String: ConvexEncodable?] = ["boardId": boardId, "displayName": displayName]
        if let description { args["description"] = description }
        try await client.mutation("boards:update", with: args)
    }

    func softDelete(boardId: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("boards:softDelete", with: ["boardId": boardId])
    }

    func setDefault(boardId: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("boards:setDefault", with: ["boardId": boardId])
    }
}
