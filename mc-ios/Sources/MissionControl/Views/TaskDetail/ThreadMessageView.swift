import SwiftUI

struct ThreadMessageView: View {
    let message: MCMessage

    private var isUser: Bool { message.authorType == .user }
    private var isSystem: Bool { message.authorType == .system }

    var body: some View {
        if isSystem {
            systemMessageView
        } else if isUser {
            userMessageView
        } else {
            agentMessageView
        }
    }

    // MARK: - System message (centered, muted)

    private var systemMessageView: some View {
        HStack {
            Spacer()
            Text(message.content)
                .font(.caption)
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 16)
                .padding(.vertical, 6)
                .background(.quaternary)
                .clipShape(Capsule())
            Spacer()
        }
        .padding(.vertical, 4)
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

                VStack(alignment: .leading, spacing: 6) {
                    Text(message.content)
                        .font(.body)
                        .foregroundStyle(.primary)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(.regularMaterial)
                        .clipShape(RoundedRectangle(cornerRadius: 18))

                    if let artifacts = message.artifacts, !artifacts.isEmpty {
                        artifactsDisclosure(artifacts)
                    }
                }

                Text(relativeTimestamp(message.timestamp))
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }

            Spacer(minLength: 60)
        }
        .padding(.vertical, 2)
    }

    // MARK: - Artifacts

    private func artifactsDisclosure(_ artifacts: [MessageArtifact]) -> some View {
        DisclosureGroup("Attachments (\(artifacts.count))") {
            VStack(alignment: .leading, spacing: 4) {
                ForEach(Array(artifacts.enumerated()), id: \.offset) { _, artifact in
                    HStack(spacing: 6) {
                        Image(systemName: "doc")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text(artifact.path)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                }
            }
            .padding(.top, 4)
        }
        .font(.caption)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 10))
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
