import Foundation
import Observation
import ConvexMobile

@Observable
@MainActor
final class AgentStore {
    var agents: [MCAgent] = []
    var isLoading = false
    var error: String?

    private var subscriptionTask: Task<Void, Never>?

    deinit {
        subscriptionTask?.cancel()
    }

    // MARK: - Computed: Categorised by system flag

    var systemAgents: [MCAgent] {
        agents.filter { $0.isSystem == true }
    }

    var registeredAgents: [MCAgent] {
        agents.filter { $0.isSystem != true && $0.deletedAt == nil }
    }

    var remoteAgents: [MCAgent] {
        agents.filter { $0.isSystem == false && $0.deletedAt == nil }
    }

    // MARK: - Computed: Filtered by status

    var activeAgents: [MCAgent] {
        agents.filter { $0.status == .active }
    }

    var idleAgents: [MCAgent] {
        agents.filter { $0.status == .idle }
    }

    var crashedAgents: [MCAgent] {
        agents.filter { $0.status == .crashed }
    }

    // MARK: - Subscription

    func startSubscription() {
        subscriptionTask?.cancel()
        subscriptionTask = Task { [weak self] in
            await self?.subscribeToAgents()
        }
    }

    private func subscribeToAgents() async {
        guard let client = ConvexClientManager.shared.client else {
            error = "No Convex client available"
            return
        }
        isLoading = true

        let stream = client.subscribe(to: "agents:list", yielding: [MCAgent].self)
            .replaceError(with: [])
            .values

        for await updatedAgents in stream {
            guard !Task.isCancelled else { break }
            if isLoading { isLoading = false }
            agents = updatedAgents
        }
    }

    // MARK: - Mutations

    func updateConfig(agentId: String, prompt: String?, soul: String?, model: String?) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        var args: [String: ConvexEncodable?] = ["agentId": agentId]
        if let prompt { args["prompt"] = prompt }
        if let soul { args["soul"] = soul }
        if let model { args["model"] = model }
        try await client.mutation("agents:updateConfig", with: args)
    }

    func setEnabled(agentId: String, enabled: Bool) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("agents:setEnabled", with: [
            "agentId": agentId,
            "enabled": enabled
        ])
    }

    func softDelete(agentId: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("agents:softDelete", with: ["agentId": agentId])
    }

    func restore(agentId: String) async throws {
        guard let client = ConvexClientManager.shared.client else { return }
        try await client.mutation("agents:restore", with: ["agentId": agentId])
    }
}
