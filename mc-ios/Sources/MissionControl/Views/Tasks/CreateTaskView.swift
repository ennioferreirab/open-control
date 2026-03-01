import SwiftUI

private extension TrustLevel {
    var displayName: String {
        switch self {
        case .autonomous: return "Autonomous"
        case .agentReviewed: return "Agent Reviewed"
        case .humanApproved: return "Human Approved"
        }
    }
}

struct CreateTaskView: View {
    @Environment(TaskStore.self) private var taskStore
    @Environment(BoardStore.self) private var boardStore
    @Environment(AgentStore.self) private var agentStore
    @Environment(\.dismiss) private var dismiss

    @State private var title = ""
    @State private var description = ""
    @State private var selectedBoardId = ""
    @State private var selectedAgent = ""
    @State private var selectedTrustLevel: TrustLevel = .autonomous
    @State private var selectedTags: Set<String> = []
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    @State private var showError = false

    private var selectedBoard: MCBoard? {
        boardStore.boards.first { $0.id == selectedBoardId }
    }

    private var availableAgents: [MCAgent] {
        guard let board = selectedBoard else { return [] }
        return agentStore.agents.filter { board.enabledAgents.contains($0.name) && $0.deletedAt == nil }
    }

    private var availableTags: [String] {
        var seen = Set<String>()
        return taskStore.tasks
            .compactMap(\.tags)
            .flatMap { $0 }
            .filter { seen.insert($0).inserted }
            .sorted()
    }

    private var canSubmit: Bool {
        !title.trimmingCharacters(in: .whitespaces).isEmpty && !isSubmitting
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Task Details") {
                    TextField("Title", text: $title)
                        .submitLabel(.next)

                    ZStack(alignment: .topLeading) {
                        if description.isEmpty {
                            Text("Description (optional)")
                                .foregroundStyle(.tertiary)
                                .padding(.top, 8)
                                .padding(.leading, 4)
                                .allowsHitTesting(false)
                        }
                        TextEditor(text: $description)
                            .frame(minHeight: 80)
                    }
                }

                Section("Configuration") {
                    Picker("Board", selection: $selectedBoardId) {
                        ForEach(boardStore.activeBoards) { board in
                            Text(board.displayName).tag(board.id)
                        }
                    }
                    .onChange(of: selectedBoardId) {
                        selectedAgent = ""
                    }

                    Picker("Assigned Agent", selection: $selectedAgent) {
                        Text("None").tag("")
                        ForEach(availableAgents) { agent in
                            Text(agent.displayName).tag(agent.name)
                        }
                    }

                    Picker("Trust Level", selection: $selectedTrustLevel) {
                        ForEach(TrustLevel.allCases, id: \.self) { level in
                            Text(level.displayName).tag(level)
                        }
                    }
                }

                if !availableTags.isEmpty {
                    Section("Tags") {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 80))], spacing: 8) {
                            ForEach(availableTags, id: \.self) { tag in
                                TagChipButton(
                                    tag: tag,
                                    isSelected: selectedTags.contains(tag),
                                    onTap: { toggleTag(tag) }
                                )
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
            .navigationTitle("New Task")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if isSubmitting {
                        ProgressView()
                    } else {
                        Button("Create") {
                            Task { await submit() }
                        }
                        .disabled(!canSubmit)
                    }
                }
            }
            .alert("Error", isPresented: $showError) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(errorMessage ?? "An error occurred")
            }
        }
        .onAppear {
            if let defaultBoard = boardStore.defaultBoard {
                selectedBoardId = defaultBoard.id
            }
        }
    }

    private func toggleTag(_ tag: String) {
        if selectedTags.contains(tag) {
            selectedTags.remove(tag)
        } else {
            selectedTags.insert(tag)
        }
    }

    private func submit() async {
        let trimmedTitle = title.trimmingCharacters(in: .whitespaces)
        guard !trimmedTitle.isEmpty else { return }
        let boardId = selectedBoardId.isEmpty ? (boardStore.defaultBoard?.id ?? "") : selectedBoardId
        guard !boardId.isEmpty else {
            errorMessage = "Please select a board."
            showError = true
            return
        }

        isSubmitting = true
        defer { isSubmitting = false }

        do {
            try await taskStore.createTask(
                title: trimmedTitle,
                boardId: boardId,
                description: description.isEmpty ? nil : description,
                assignedAgent: selectedAgent.isEmpty ? nil : selectedAgent,
                trustLevel: selectedTrustLevel,
                tags: selectedTags.isEmpty ? nil : Array(selectedTags)
            )
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }
}

// MARK: - Tag Chip Button

private struct TagChipButton: View {
    let tag: String
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            Text(tag)
                .font(.caption)
                .fontWeight(.medium)
                .foregroundStyle(.primary)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .glassEffect(
                    isSelected ? .regular.tint(.accentColor) : .clear,
                    in: .capsule
                )
                .animation(.spring(duration: 0.2), value: isSelected)
        }
        .buttonStyle(.plain)
    }
}
