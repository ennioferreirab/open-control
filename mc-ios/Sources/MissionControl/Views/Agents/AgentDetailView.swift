import SwiftUI

struct AgentDetailView: View {
    @Environment(AgentStore.self) private var agentStore
    @Environment(\.dismiss) private var dismiss
    let agent: MCAgent

    @State private var showDeleteConfirmation = false

    var body: some View {
        List {
            // MARK: Header section
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 10) {
                        Image(systemName: "cpu")
                            .font(.title2)
                            .foregroundStyle(.secondary)
                            .frame(width: 44, height: 44)
                            .background(.quaternary)
                            .clipShape(RoundedRectangle(cornerRadius: 10))

                        VStack(alignment: .leading, spacing: 2) {
                            Text(agent.displayName)
                                .font(.title3)
                                .fontWeight(.semibold)
                            Text(agent.role)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        statusBadge(agent.status)
                    }
                }
                .padding(.vertical, 4)
            }

            // MARK: Info section
            Section("Info") {
                LabeledContent("Status") {
                    statusBadge(agent.status)
                }

                if let model = agent.model {
                    LabeledContent("Model", value: model)
                }

                if let reasoningLevel = agent.reasoningLevel {
                    LabeledContent("Reasoning", value: reasoningLevel)
                }
            }

            // MARK: Skills section
            if !agent.skills.isEmpty {
                Section("Skills") {
                    FlowLayout(spacing: 6) {
                        ForEach(agent.skills, id: \.self) { skill in
                            Text(skill)
                                .font(.caption)
                                .fontWeight(.medium)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 4)
                                .background(Color.accentColor.opacity(0.15))
                                .foregroundStyle(Color.accentColor)
                                .clipShape(Capsule())
                        }
                    }
                    .padding(.vertical, 4)
                }
            }

            // MARK: Variables section
            if let variables = agent.variables, !variables.isEmpty {
                Section("Variables") {
                    ForEach(variables, id: \.name) { variable in
                        LabeledContent(variable.name, value: variable.value)
                            .font(.caption)
                    }
                }
            }

            // MARK: Settings section
            Section("Settings") {
                Toggle(
                    "Enabled",
                    isOn: Binding(
                        get: { agent.enabled ?? true },
                        set: { newValue in
                            Task {
                                do {
                                    try await agentStore.setEnabled(agentId: agent.id, enabled: newValue)
                                } catch {}
                            }
                        }
                    )
                )
            }

            // MARK: Actions section
            Section {
                NavigationLink(destination: AgentChatView(agent: agent)) {
                    Label("Chat with Agent", systemImage: "bubble.left.and.bubble.right")
                        .foregroundStyle(Color.accentColor)
                }

                Button(role: .destructive) {
                    showDeleteConfirmation = true
                } label: {
                    Label("Delete Agent", systemImage: "trash")
                }
            }
        }
        .navigationTitle(agent.displayName)
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .confirmationDialog(
            "Delete Agent",
            isPresented: $showDeleteConfirmation,
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) {
                Task {
                    do {
                        try await agentStore.softDelete(agentId: agent.id)
                        dismiss()
                    } catch {}
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Are you sure you want to delete \(agent.displayName)? This action can be undone.")
        }
    }

    @ViewBuilder
    private func statusBadge(_ status: AgentStatus) -> some View {
        HStack(spacing: 4) {
            Circle()
                .fill(status.color)
                .frame(width: 7, height: 7)
            Text(status.displayName)
                .font(.caption)
                .fontWeight(.medium)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 3)
        .background(status.color.opacity(0.12))
        .clipShape(Capsule())
    }
}

// MARK: - Flow Layout for skill chips

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = computeRows(proposal: proposal, subviews: subviews)
        let height = rows.map(\.height).reduce(0, +) + spacing * CGFloat(max(rows.count - 1, 0))
        return CGSize(width: proposal.width ?? 0, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = computeRows(proposal: proposal, subviews: subviews)
        var y = bounds.minY
        for row in rows {
            var x = bounds.minX
            for item in row.items {
                item.view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(item.size))
                x += item.size.width + spacing
            }
            y += row.height + spacing
        }
    }

    private struct Row {
        var items: [(view: LayoutSubview, size: CGSize)] = []
        var height: CGFloat { items.map(\.size.height).max() ?? 0 }
    }

    private func computeRows(proposal: ProposedViewSize, subviews: Subviews) -> [Row] {
        let maxWidth = proposal.width ?? .infinity
        var rows: [Row] = []
        var currentRow = Row()
        var rowWidth: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if rowWidth + size.width > maxWidth && !currentRow.items.isEmpty {
                rows.append(currentRow)
                currentRow = Row()
                rowWidth = 0
            }
            currentRow.items.append((view: subview, size: size))
            rowWidth += size.width + spacing
        }
        if !currentRow.items.isEmpty {
            rows.append(currentRow)
        }
        return rows
    }
}
