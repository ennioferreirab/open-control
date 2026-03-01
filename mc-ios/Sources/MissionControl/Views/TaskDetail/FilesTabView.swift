import SwiftUI

struct FilesTabView: View {
    let task: MCTask

    var body: some View {
        Group {
            if let files = task.files, !files.isEmpty {
                List(files, id: \.name) { file in
                    FileRowView(file: file)
                }
                #if os(iOS)
                .listStyle(.insetGrouped)
                #endif
            } else {
                emptyState
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "doc")
                .font(.largeTitle)
                .foregroundStyle(.tertiary)
            Text("No files attached")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text("Files shared by agents will appear here")
                .font(.caption)
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.vertical, 60)
    }
}

// MARK: - File Row

struct FileRowView: View {
    let file: TaskFile

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: iconName(for: file.type))
                .font(.title2)
                .foregroundStyle(.blue)
                .frame(width: 32, height: 32)

            VStack(alignment: .leading, spacing: 2) {
                Text(file.name)
                    .font(.subheadline)
                    .foregroundStyle(.primary)
                    .lineLimit(1)
                HStack(spacing: 6) {
                    if !file.subfolder.isEmpty {
                        Text(file.subfolder)
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                        Text("·")
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                    }
                    Text(formattedSize(file.size))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            Image(systemName: "arrow.down.circle")
                .font(.body)
                .foregroundStyle(.secondary)
                .accessibilityLabel("Download file")
        }
        .contentShape(Rectangle())
        .onTapGesture {
            // TODO: implement file download / preview
        }
    }

    private func iconName(for fileType: String) -> String {
        switch fileType.lowercased() {
        case "pdf":
            return "doc.richtext"
        case "jpg", "jpeg", "png", "gif", "webp", "svg", "heic":
            return "photo"
        case "mp4", "mov", "avi", "mkv":
            return "film"
        case "mp3", "wav", "m4a", "aac":
            return "music.note"
        case "zip", "tar", "gz", "rar":
            return "archivebox"
        case "swift":
            return "swift"
        case "py", "rb", "go", "rs":
            return "doc.text"
        case "js", "ts", "jsx", "tsx", "html", "css":
            return "doc.text"
        case "json", "yaml", "yml", "toml":
            return "doc.badge.gearshape"
        case "md", "txt", "rtf":
            return "doc.plaintext"
        case "xls", "xlsx", "csv":
            return "tablecells"
        default:
            return "doc"
        }
    }

    private func formattedSize(_ bytes: Int) -> String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useKB, .useMB, .useGB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(bytes))
    }
}
