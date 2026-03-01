import SwiftUI

struct AgentListView: View {
    @Environment(AgentStore.self) private var agentStore
    @State private var searchText = ""
    @State private var agentToDelete: MCAgent?
    @State private var showDeleteConfirmation = false

    private var filteredSystemAgents: [MCAgent] {
        agentStore.systemAgents.filter { matchesSearch($0) }
    }

    private var filteredRegisteredAgents: [MCAgent] {
        agentStore.registeredAgents.filter { matchesSearch($0) }
    }

    private func matchesSearch(_ agent: MCAgent) -> Bool {
        searchText.isEmpty
            || agent.displayName.localizedCaseInsensitiveContains(searchText)
            || agent.name.localizedCaseInsensitiveContains(searchText)
            || agent.role.localizedCaseInsensitiveContains(searchText)
    }

    var body: some View {
        List {
            if !filteredSystemAgents.isEmpty {
                Section("System Agents") {
                    ForEach(filteredSystemAgents) { agent in
                        NavigationLink(value: agent) {
                            AgentRowView(agent: agent)
                        }
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) {
                                agentToDelete = agent
                                showDeleteConfirmation = true
                            } label: {
                                Label("Delete", systemImage: "trash")
                            }
                        }
                    }
                }
            }

            if !filteredRegisteredAgents.isEmpty {
                Section("Registered Agents") {
                    ForEach(filteredRegisteredAgents) { agent in
                        NavigationLink(value: agent) {
                            AgentRowView(agent: agent)
                        }
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) {
                                agentToDelete = agent
                                showDeleteConfirmation = true
                            } label: {
                                Label("Delete", systemImage: "trash")
                            }
                        }
                    }
                }
            }

            if filteredSystemAgents.isEmpty && filteredRegisteredAgents.isEmpty {
                ContentUnavailableView(
                    searchText.isEmpty ? "No Agents" : "No Results",
                    systemImage: "cpu",
                    description: Text(
                        searchText.isEmpty
                            ? "No agents are connected"
                            : "No agents match your search"
                    )
                )
                .listRowBackground(Color.clear)
            }
        }
        .navigationTitle("Agents")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.large)
        #endif
        .searchable(text: $searchText, prompt: "Search agents…")
        .navigationDestination(for: MCAgent.self) { agent in
            AgentDetailView(agent: agent)
        }
        .confirmationDialog(
            "Delete Agent",
            isPresented: $showDeleteConfirmation,
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) {
                guard let agent = agentToDelete else { return }
                Task {
                    do {
                        try await agentStore.softDelete(agentId: agent.id)
                    } catch {}
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            if let agent = agentToDelete {
                Text("Are you sure you want to delete \(agent.displayName)?")
            }
        }
        .task {
            agentStore.startSubscription()
        }
    }
}

// MARK: - Agent Row

struct AgentRowView: View {
    let agent: MCAgent

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(agent.status.color)
                .frame(width: 10, height: 10)

            VStack(alignment: .leading, spacing: 2) {
                Text(agent.displayName)
                    .font(.body)
                    .fontWeight(.medium)
                Text(agent.role)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            if agent.enabled == false {
                Text("Disabled")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(.quaternary)
                    .clipShape(Capsule())
            }
        }
        .padding(.vertical, 2)
    }
}

// MARK: - AgentStatus color

extension AgentStatus {
    var color: Color {
        switch self {
        case .active: return .green
        case .idle: return .gray
        case .crashed: return .red
        }
    }

    var displayName: String {
        switch self {
        case .active: return "Active"
        case .idle: return "Idle"
        case .crashed: return "Crashed"
        }
    }
}
