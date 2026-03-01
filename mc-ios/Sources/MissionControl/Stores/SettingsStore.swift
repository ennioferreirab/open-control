import Foundation
import Observation
@preconcurrency import ConvexMobile

@Observable
@MainActor
final class SettingsStore {
    var settings: [MCSetting] = []
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
            await self?.subscribeToSettings()
        }
    }

    private func subscribeToSettings() async {
        guard let client = ConvexClientManager.shared.client else {
            error = "No Convex client available"
            return
        }
        isLoading = true

        let stream = client.subscribe(to: "settings:list", yielding: [MCSetting].self)
            .replaceError(with: [])
            .values

        for await updatedSettings in stream {
            guard !Task.isCancelled else { break }
            if isLoading { isLoading = false }
            settings = updatedSettings
        }
    }

    // MARK: - Mutations

    func updateSetting(key: String, value: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        let args: [String: ConvexEncodable?] = ["key": key, "value": value]
        try await client.mutation("settings:update", with: args)
    }

    // MARK: - Helpers

    func value(for key: String) -> String? {
        settings.first { $0.key == key }?.value
    }
}
