import SwiftUI

struct TagSettingsView: View {
    @Environment(TagStore.self) private var tagStore

    @State private var showAddTag = false
    @State private var deletingTag: MCTag?

    var body: some View {
        List {
            ForEach(tagStore.tags) { tag in
                HStack {
                    Circle()
                        .fill(tag.color.swiftUIColor)
                        .frame(width: 12, height: 12)
                    Text(tag.name)
                    Spacer()
                }
                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                    Button(role: .destructive) {
                        deletingTag = tag
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                }
            }
        }
        .navigationTitle("Tags")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .task { tagStore.startSubscription() }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showAddTag = true
                } label: {
                    Image(systemName: "plus")
                }
                .accessibilityLabel("Add tag")
            }
        }
        .sheet(isPresented: $showAddTag) {
            TagAddView()
        }
        .confirmationDialog(
            "Delete Tag",
            isPresented: Binding(
                get: { deletingTag != nil },
                set: { if !$0 { deletingTag = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) {
                if let tag = deletingTag {
                    Task { try? await tagStore.deleteTag(tagId: tag.id) }
                }
                deletingTag = nil
            }
            Button("Cancel", role: .cancel) { deletingTag = nil }
        } message: {
            if let tag = deletingTag {
                Text("Delete tag \"\(tag.name)\"?")
            }
        }
    }
}

// MARK: - Add Tag Sheet

struct TagAddView: View {
    @Environment(TagStore.self) private var tagStore
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var selectedColor: TagColor = .blue
    @State private var isSubmitting = false
    @State private var errorMessage: String?

    private let columns = Array(repeating: GridItem(.flexible()), count: 4)

    var body: some View {
        NavigationStack {
            Form {
                Section("Name") {
                    TextField("Tag name", text: $name)
                }
                Section("Color") {
                    LazyVGrid(columns: columns, spacing: 12) {
                        ForEach(TagColor.allCases, id: \.self) { color in
                            Button {
                                selectedColor = color
                            } label: {
                                ZStack {
                                    Circle()
                                        .fill(color.swiftUIColor)
                                        .frame(width: 36, height: 36)
                                    if selectedColor == color {
                                        Image(systemName: "checkmark")
                                            .font(.caption.bold())
                                            .foregroundStyle(.white)
                                    }
                                }
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.vertical, 8)
                }
                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundStyle(.red)
                            .font(.caption)
                    }
                }
            }
            .navigationTitle("New Tag")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") { submit() }
                        .disabled(name.isEmpty || isSubmitting)
                }
            }
        }
    }

    private func submit() {
        isSubmitting = true
        errorMessage = nil
        Task {
            do {
                try await tagStore.createTag(name: name, color: selectedColor)
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
                isSubmitting = false
            }
        }
    }
}

// MARK: - TagColor + SwiftUI

extension TagColor {
    var swiftUIColor: Color {
        switch self {
        case .blue: return .blue
        case .green: return .green
        case .red: return .red
        case .amber: return .orange
        case .violet: return .purple
        case .pink: return .pink
        case .orange: return Color.orange.opacity(0.8)
        case .teal: return .teal
        }
    }
}
