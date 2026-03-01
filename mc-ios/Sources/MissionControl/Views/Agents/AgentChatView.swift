import SwiftUI

struct AgentChatView: View {
    @Environment(ChatStore.self) private var chatStore
    let agent: MCAgent

    @State private var messageText = ""
    @FocusState private var isFocused: Bool

    private var canSend: Bool {
        !messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 4) {
                        if chatStore.messages.isEmpty && !chatStore.isLoading {
                            emptyState
                        } else {
                            ForEach(chatStore.messages) { message in
                                ChatMessageView(message: message)
                                    .id(message.id)
                            }
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                }
                .onChange(of: chatStore.messages.count) { _, _ in
                    if let lastId = chatStore.messages.last?.id {
                        withAnimation(.spring(duration: 0.3)) {
                            proxy.scrollTo(lastId, anchor: .bottom)
                        }
                    }
                }
            }

            Divider()
            inputBar
        }
        .navigationTitle(agent.displayName)
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .task {
            chatStore.setAgent(agent.name)
        }
    }

    // MARK: - Input bar

    private var inputBar: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Message \(agent.displayName)…", text: $messageText, axis: .vertical)
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
                    .foregroundStyle(canSend ? Color.white : Color.secondary)
                    .frame(width: 36, height: 36)
                    .background(canSend ? Color.accentColor : Color.secondary.opacity(0.2))
                    .clipShape(Circle())
            }
            .disabled(!canSend)
            .accessibilityLabel("Send message")
            .animation(.spring(duration: 0.2), value: canSend)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(.regularMaterial)
    }

    // MARK: - Empty state

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.largeTitle)
                .foregroundStyle(.tertiary)
            Text("No messages yet")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text("Start a conversation with \(agent.displayName)")
                .font(.caption)
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 60)
    }

    // MARK: - Send

    private func sendMessage() {
        let trimmed = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        messageText = ""
        Task {
            do {
                try await chatStore.sendMessage(agentName: agent.name, content: trimmed)
            } catch {}
        }
    }
}

// MARK: - Chat Message View

struct ChatMessageView: View {
    let message: MCChat

    private var isUser: Bool { message.authorType == .user }

    var body: some View {
        if isUser {
            userMessageView
        } else {
            agentMessageView
        }
    }

    // MARK: - User message (right-aligned, blue bubble)

    private var userMessageView: some View {
        HStack(alignment: .bottom, spacing: 8) {
            Spacer(minLength: 60)
            VStack(alignment: .trailing, spacing: 4) {
                Text(message.content)
                    .font(.body)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(Color.blue)
                    .clipShape(RoundedRectangle(cornerRadius: 18))

                if let status = message.status, status != .done {
                    statusIndicator(status)
                }

                Text(relativeTimestamp(message.timestamp))
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 2)
    }

    // MARK: - Agent message (left-aligned, material bubble)

    private var agentMessageView: some View {
        HStack(alignment: .bottom, spacing: 8) {
            Image(systemName: "cpu")
                .font(.caption)
                .foregroundStyle(.white)
                .frame(width: 28, height: 28)
                .background(Color.secondary)
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 4) {
                Text(message.authorName)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.secondary)

                Text(message.content)
                    .font(.body)
                    .foregroundStyle(.primary)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(.regularMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 18))

                Text(relativeTimestamp(message.timestamp))
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }

            Spacer(minLength: 60)
        }
        .padding(.vertical, 2)
    }

    // MARK: - Status indicator

    @ViewBuilder
    private func statusIndicator(_ status: ChatStatus) -> some View {
        HStack(spacing: 4) {
            switch status {
            case .pending:
                Image(systemName: "clock")
                    .font(.caption2)
                Text("Pending")
                    .font(.caption2)
            case .processing:
                ProgressView()
                    .scaleEffect(0.6)
                Text("Processing…")
                    .font(.caption2)
            case .done:
                EmptyView()
            }
        }
        .foregroundStyle(.secondary)
    }

    // MARK: - Helpers

    private func relativeTimestamp(_ timestamp: String) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        let iso = ISO8601DateFormatter()
        if let date = iso.date(from: timestamp) {
            return formatter.localizedString(for: date, relativeTo: Date())
        }
        return timestamp
    }
}
