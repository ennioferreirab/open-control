import Foundation
import Observation
import ConvexMobile

@Observable
@MainActor
final class TaskStore {
    var tasks: [MCTask] = []
    var isLoading = false
    var error: String?
    private(set) var currentBoardId: String?

    private var subscriptionTask: Task<Void, Never>?

    deinit {
        subscriptionTask?.cancel()
    }

    // MARK: - Computed

    var tasksByStatus: [TaskStatus: [MCTask]] {
        Dictionary(grouping: tasks, by: \.status)
    }

    var activeTasks: [MCTask] {
        tasks.filter { $0.deletedAt == nil }
    }

    var favoriteTasks: [MCTask] {
        tasks.filter { $0.isFavorite == true }
    }

    // MARK: - Subscription

    func setBoard(_ boardId: String) {
        guard boardId != currentBoardId else { return }
        currentBoardId = boardId
        subscriptionTask?.cancel()
        subscriptionTask = Task { [weak self] in
            await self?.subscribeToTasks(boardId: boardId)
        }
    }

    private func subscribeToTasks(boardId: String) async {
        guard let client = ConvexClientManager.shared.client else {
            error = "No Convex client available"
            return
        }
        isLoading = true

        // TODO: Verify exact subscribe(to:with:yielding:) signature in convex-swift SDK.
        // The Combine publisher is converted to an AsyncSequence via .values.
        let stream = client.subscribe(to: "tasks:listByBoard", with: ["boardId": boardId], yielding: [MCTask].self)
            .replaceError(with: [])
            .values

        for await updatedTasks in stream {
            guard !Task.isCancelled else { break }
            if isLoading { isLoading = false }
            tasks = updatedTasks
        }
    }

    // MARK: - Mutations

    func createTask(title: String, boardId: String, description: String? = nil) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        var args: [String: ConvexEncodable?] = ["title": title, "boardId": boardId]
        if let description { args["description"] = description }
        try await client.mutation("tasks:create", with: args)
    }

    func toggleFavorite(taskId: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("tasks:toggleFavorite", with: ["taskId": taskId])
    }

    func updateStatus(taskId: String, status: TaskStatus) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("tasks:updateStatus", with: [
            "taskId": taskId,
            "status": status.rawValue
        ])
    }

    func softDelete(taskId: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("tasks:softDelete", with: ["taskId": taskId])
    }
}
