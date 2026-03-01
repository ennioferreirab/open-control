import Foundation
import Observation
@preconcurrency import ConvexMobile

@Observable
@MainActor
final class ActivityStore {
    var activities: [MCActivity] = []
    var isLoading = false
    var error: String?

    nonisolated(unsafe) private var subscriptionTask: Task<Void, Never>?

    deinit {
        subscriptionTask?.cancel()
    }

    // MARK: - Computed

    /// Activities sorted newest first by timestamp.
    var sortedActivities: [MCActivity] {
        activities.sorted { $0.timestamp > $1.timestamp }
    }

    func activities(for taskId: String) -> [MCActivity] {
        activities
            .filter { $0.taskId == taskId }
            .sorted { $0.timestamp > $1.timestamp }
    }

    func activities(forAgent agentName: String) -> [MCActivity] {
        activities
            .filter { $0.agentName == agentName }
            .sorted { $0.timestamp > $1.timestamp }
    }

    // MARK: - Subscription

    func startSubscription() {
        subscriptionTask?.cancel()
        subscriptionTask = Task { [weak self] in
            await self?.subscribeToActivities()
        }
    }

    private func subscribeToActivities() async {
        guard let client = ConvexClientManager.shared.client else {
            error = "No Convex client available"
            return
        }
        isLoading = true

        let stream = client.subscribe(to: "activities:list", yielding: [MCActivity].self)
            .replaceError(with: [])
            .values

        for await updatedActivities in stream {
            guard !Task.isCancelled else { break }
            if isLoading { isLoading = false }
            activities = updatedActivities
        }
    }
}
