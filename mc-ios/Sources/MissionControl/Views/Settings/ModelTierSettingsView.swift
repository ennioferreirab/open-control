import SwiftUI

struct ModelTierSettingsView: View {
    @Environment(SettingsStore.self) private var settingsStore

    private let modelKeys = ["default_model", "reasoning_model", "fast_model"]

    var body: some View {
        List {
            Section {
                ForEach(modelKeys, id: \.self) { key in
                    NavigationLink {
                        ModelTierEditView(key: key, currentValue: settingsStore.value(for: key) ?? "")
                    } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(displayName(for: key))
                                .font(.body)
                            Text(settingsStore.value(for: key) ?? "Not set")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            } header: {
                Text("Model Configuration")
            } footer: {
                Text("Configure which model to use for each tier of agent task.")
            }
        }
        .navigationTitle("Model Tiers")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .task { settingsStore.startSubscription() }
    }

    private func displayName(for key: String) -> String {
        switch key {
        case "default_model": return "Default Model"
        case "reasoning_model": return "Reasoning Model"
        case "fast_model": return "Fast Model"
        default: return key
        }
    }
}

// MARK: - Edit View

private struct ModelTierEditView: View {
    @Environment(SettingsStore.self) private var settingsStore
    @Environment(\.dismiss) private var dismiss

    let key: String
    @State private var value: String
    @State private var isSubmitting = false
    @State private var errorMessage: String?

    init(key: String, currentValue: String) {
        self.key = key
        _value = State(initialValue: currentValue)
    }

    var body: some View {
        Form {
            Section("Model ID") {
                TextField("e.g. claude-sonnet-4-6", text: $value)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
            }
            if let error = errorMessage {
                Section {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.caption)
                }
            }
        }
        .navigationTitle(displayName)
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("Save") { save() }
                    .disabled(value.isEmpty || isSubmitting)
            }
        }
    }

    private var displayName: String {
        switch key {
        case "default_model": return "Default Model"
        case "reasoning_model": return "Reasoning Model"
        case "fast_model": return "Fast Model"
        default: return key
        }
    }

    private func save() {
        isSubmitting = true
        errorMessage = nil
        Task {
            do {
                try await settingsStore.updateSetting(key: key, value: value)
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
                isSubmitting = false
            }
        }
    }
}
