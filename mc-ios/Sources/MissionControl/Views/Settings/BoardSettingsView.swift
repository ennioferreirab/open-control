import SwiftUI

struct BoardSettingsView: View {
    @Environment(BoardStore.self) private var boardStore

    @State private var showAddBoard = false
    @State private var editingBoard: MCBoard?
    @State private var deletingBoard: MCBoard?
    @State private var errorMessage: String?

    var body: some View {
        List {
            ForEach(boardStore.activeBoards) { board in
                NavigationLink {
                    BoardEditView(board: board)
                } label: {
                    BoardRowView(board: board)
                }
                .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                    Button(role: .destructive) {
                        deletingBoard = board
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                }
                .swipeActions(edge: .leading, allowsFullSwipe: true) {
                    Button {
                        Task { try? await boardStore.setDefault(boardId: board.id) }
                    } label: {
                        Label("Set Default", systemImage: "star.fill")
                    }
                    .tint(.yellow)
                }
            }
        }
        .navigationTitle("Boards")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .task { boardStore.startSubscription() }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showAddBoard = true
                } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .sheet(isPresented: $showAddBoard) {
            BoardAddView()
        }
        .confirmationDialog(
            "Delete Board",
            isPresented: Binding(
                get: { deletingBoard != nil },
                set: { if !$0 { deletingBoard = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) {
                if let board = deletingBoard {
                    Task { try? await boardStore.softDelete(boardId: board.id) }
                }
                deletingBoard = nil
            }
            Button("Cancel", role: .cancel) { deletingBoard = nil }
        } message: {
            if let board = deletingBoard {
                Text("Delete \"\(board.displayName)\"? This cannot be undone.")
            }
        }
    }
}

// MARK: - Board Row

private struct BoardRowView: View {
    let board: MCBoard

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(board.displayName)
                    .font(.body)
                Text(board.name)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if board.isDefault == true {
                Image(systemName: "star.fill")
                    .foregroundStyle(.yellow)
                    .font(.caption)
            }
        }
    }
}

// MARK: - Add Board Sheet

struct BoardAddView: View {
    @Environment(BoardStore.self) private var boardStore
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var displayName = ""
    @State private var description = ""
    @State private var isSubmitting = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Board Identity") {
                    TextField("Name (slug)", text: $name)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("Display Name", text: $displayName)
                }
                Section("Description") {
                    TextField("Optional description", text: $description, axis: .vertical)
                        .lineLimit(3...)
                }
                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundStyle(.red)
                            .font(.caption)
                    }
                }
            }
            .navigationTitle("New Board")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        submit()
                    }
                    .disabled(name.isEmpty || displayName.isEmpty || isSubmitting)
                }
            }
        }
    }

    private func submit() {
        isSubmitting = true
        errorMessage = nil
        Task {
            do {
                let desc = description.isEmpty ? nil : description
                try await boardStore.createBoard(name: name, displayName: displayName, description: desc)
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
                isSubmitting = false
            }
        }
    }
}

// MARK: - Edit Board View

struct BoardEditView: View {
    @Environment(BoardStore.self) private var boardStore
    @Environment(\.dismiss) private var dismiss

    let board: MCBoard

    @State private var displayName: String
    @State private var description: String
    @State private var isSubmitting = false
    @State private var errorMessage: String?

    init(board: MCBoard) {
        self.board = board
        _displayName = State(initialValue: board.displayName)
        _description = State(initialValue: board.description ?? "")
    }

    var body: some View {
        Form {
            Section("Board Identity") {
                LabeledContent("Name", value: board.name)
                TextField("Display Name", text: $displayName)
            }
            Section("Description") {
                TextField("Optional description", text: $description, axis: .vertical)
                    .lineLimit(3...)
            }
            if let error = errorMessage {
                Section {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.caption)
                }
            }
        }
        .navigationTitle("Edit Board")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("Save") { save() }
                    .disabled(displayName.isEmpty || isSubmitting)
            }
        }
    }

    private func save() {
        isSubmitting = true
        errorMessage = nil
        Task {
            do {
                let desc = description.isEmpty ? nil : description
                try await boardStore.updateBoard(boardId: board.id, displayName: displayName, description: desc)
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
                isSubmitting = false
            }
        }
    }
}
