import SwiftUI

struct ThreadInputView: View {
    @Environment(MessageStore.self) private var messageStore
    let taskId: String
    @State private var messageText = ""
    @FocusState private var isFocused: Bool

    private var canSend: Bool {
        !messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Send a message…", text: $messageText, axis: .vertical)
                .textFieldStyle(.plain)
                .font(.body)
                .lineLimit(1...6)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(.regularMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 20))
                .focused($isFocused)
                .submitLabel(.send)
                .onSubmit {
                    if canSend { sendMessage() }
                }

            Button(action: sendMessage) {
                Image(systemName: "paperplane.fill")
                    .font(.body)
                    .foregroundStyle(canSend ? .white : .tertiary)
                    .frame(width: 36, height: 36)
                    .background(
                        canSend ? Color.accentColor : Color.secondary.opacity(0.2)
                    )
                    .clipShape(Circle())
            }
            .disabled(!canSend)
            .animation(.spring(duration: 0.2), value: canSend)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(.regularMaterial)
    }

    private func sendMessage() {
        let trimmed = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        messageText = ""
        Task {
            do {
                try await messageStore.sendMessage(taskId: taskId, content: trimmed, authorName: "user")
            } catch {}
        }
    }
}
