import SwiftUI

struct StepCardView: View {
    let step: MCStep
    @State private var showDetail = false

    private var statusColor: Color {
        switch step.status {
        case .planned: return .gray
        case .assigned: return .cyan
        case .running: return .blue
        case .completed: return .green
        case .crashed: return .red
        case .blocked: return .orange
        case .waitingHuman: return .yellow
        }
    }

    private var statusLabel: String {
        switch step.status {
        case .planned: return "Planned"
        case .assigned: return "Assigned"
        case .running: return "Running"
        case .completed: return "Completed"
        case .crashed: return "Crashed"
        case .blocked: return "Blocked"
        case .waitingHuman: return "Waiting"
        }
    }

    private var isRunning: Bool { step.status == .running }

    var body: some View {
        Button {
            showDetail.toggle()
        } label: {
            HStack(alignment: .top, spacing: 12) {
                // Animated status indicator
                ZStack {
                    if isRunning {
                        Image(systemName: "circle.fill")
                            .foregroundStyle(statusColor.opacity(0.25))
                            .font(.title2)
                            .symbolEffect(.pulse, isActive: true)
                    }
                    Image(systemName: "circle.fill")
                        .foregroundStyle(statusColor)
                        .font(.caption)
                }
                .frame(width: 24, height: 24)
                .padding(.top, 2)

                VStack(alignment: .leading, spacing: 6) {
                    // Step number + title
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text("Step \(step.order)")
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                        Text(step.title)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundStyle(.primary)
                    }

                    // Description
                    Text(step.description)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)

                    // Bottom row: agent + status
                    HStack(spacing: 6) {
                        HStack(spacing: 4) {
                            Image(systemName: "cpu")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Text(step.assignedAgent)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(.quaternary)
                        .clipShape(Capsule())

                        Text(statusLabel)
                            .font(.caption2)
                            .fontWeight(.medium)
                            .foregroundStyle(statusColor)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(statusColor.opacity(0.12))
                            .clipShape(Capsule())
                    }

                    // Error message if crashed
                    if let error = step.errorMessage, !error.isEmpty {
                        HStack(alignment: .top, spacing: 6) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.caption)
                                .foregroundStyle(.red)
                            Text(error)
                                .font(.caption)
                                .foregroundStyle(.red)
                                .lineLimit(3)
                        }
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(Color.red.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .padding(.top, 4)
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .glassEffect(.regular, in: .rect(cornerRadius: 10))
        }
        .buttonStyle(.plain)
        .sheet(isPresented: $showDetail) {
            StepDetailSheet(step: step)
        }
    }
}

// MARK: - Step Detail Sheet

struct StepDetailSheet: View {
    let step: MCStep
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section("Details") {
                    LabeledContent("Status", value: step.status.rawValue.replacingOccurrences(of: "_", with: " ").capitalized)
                    LabeledContent("Order", value: "\(step.order)")
                    LabeledContent("Agent", value: step.assignedAgent)
                }

                Section("Description") {
                    Text(step.description)
                        .font(.body)
                }

                if let error = step.errorMessage, !error.isEmpty {
                    Section("Error") {
                        Text(error)
                            .font(.body)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle(step.title)
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
