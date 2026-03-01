import Foundation
import Observation
import ConvexMobile

@Observable
@MainActor
final class StepStore {
    var steps: [MCStep] = []
    var isLoading = false
    var error: String?
    private(set) var currentTaskId: String?

    private var subscriptionTask: Task<Void, Never>?

    deinit {
        subscriptionTask?.cancel()
    }

    // MARK: - Computed

    var sortedSteps: [MCStep] {
        steps.sorted { lhs, rhs in
            if lhs.parallelGroup != rhs.parallelGroup {
                return lhs.parallelGroup < rhs.parallelGroup
            }
            return lhs.order < rhs.order
        }
    }

    var completedSteps: [MCStep] {
        steps.filter { $0.status == .completed }
    }

    var pendingSteps: [MCStep] {
        steps.filter { $0.status == .planned || $0.status == .assigned }
    }

    var runningSteps: [MCStep] {
        steps.filter { $0.status == .running }
    }

    var blockedSteps: [MCStep] {
        steps.filter { $0.status == .blocked }
    }

    // MARK: - Subscription

    func setTask(_ taskId: String) {
        guard taskId != currentTaskId else { return }
        currentTaskId = taskId
        subscriptionTask?.cancel()
        subscriptionTask = Task { [weak self] in
            await self?.subscribeToSteps(taskId: taskId)
        }
    }

    func clearTask() {
        currentTaskId = nil
        subscriptionTask?.cancel()
        steps = []
    }

    private func subscribeToSteps(taskId: String) async {
        guard let client = ConvexClientManager.shared.client else {
            error = "No Convex client available"
            return
        }
        isLoading = true

        let stream = client.subscribe(to: "steps:listByTask", with: ["taskId": taskId], yielding: [MCStep].self)
            .replaceError(with: [])
            .values

        isLoading = false
        for await updatedSteps in stream {
            guard !Task.isCancelled else { break }
            steps = updatedSteps
        }
    }
}
