import SwiftUI

struct ActivityTabView: View {
    @Environment(ActivityStore.self) private var activityStore
    let taskId: String

    private var filteredActivities: [MCActivity] {
        activityStore.activities.filter { $0.taskId == taskId }
    }

    var body: some View {
        Group {
            if filteredActivities.isEmpty {
                emptyState
            } else {
                List {
                    ForEach(sectionKeys, id: \.self) { dateKey in
                        Section(header: Text(sectionTitle(for: dateKey))) {
                            ForEach(groupedActivities[dateKey] ?? []) { activity in
                                ActivityRowView(activity: activity)
                            }
                        }
                    }
                }
                #if os(iOS)
                .listStyle(.insetGrouped)
                #endif
            }
        }
    }

    // MARK: - Grouping

    private var groupedActivities: [String: [MCActivity]] {
        let iso = ISO8601DateFormatter()
        let dayFormatter = DateFormatter()
        dayFormatter.dateFormat = "yyyy-MM-dd"
        var groups: [String: [MCActivity]] = [:]
        for activity in filteredActivities {
            let key: String
            if let date = iso.date(from: activity.timestamp) {
                key = dayFormatter.string(from: date)
            } else {
                key = activity.timestamp.prefix(10).description
            }
            groups[key, default: []].append(activity)
        }
        return groups
    }

    private var sectionKeys: [String] {
        groupedActivities.keys.sorted(by: >)
    }

    private func sectionTitle(for dateKey: String) -> String {
        let dayFormatter = DateFormatter()
        dayFormatter.dateFormat = "yyyy-MM-dd"
        guard let date = dayFormatter.date(from: dateKey) else { return dateKey }
        if Calendar.current.isDateInToday(date) { return "Today" }
        if Calendar.current.isDateInYesterday(date) { return "Yesterday" }
        let display = DateFormatter()
        display.dateStyle = .medium
        display.timeStyle = .none
        return display.string(from: date)
    }

    // MARK: - Empty state

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "clock.arrow.circlepath")
                .font(.largeTitle)
                .foregroundStyle(.tertiary)
            Text("No activity yet")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text("Events and state changes will appear here")
                .font(.caption)
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.vertical, 60)
    }
}

// MARK: - Activity Row

struct ActivityRowView: View {
    let activity: MCActivity

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: eventIcon(activity.eventType))
                .font(.subheadline)
                .foregroundStyle(eventColor(activity.eventType))
                .frame(width: 30, height: 30)
                .background(eventColor(activity.eventType).opacity(0.12))
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 2) {
                Text(activity.description)
                    .font(.subheadline)
                    .foregroundStyle(.primary)
                    .lineLimit(2)

                HStack(spacing: 4) {
                    if let agentName = activity.agentName {
                        Text(agentName)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("·")
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                    }
                    Text(relativeTimestamp(activity.timestamp))
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
            }
        }
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

    private func eventIcon(_ eventType: ActivityEventType) -> String {
        switch eventType {
        case .taskCreated: return "plus.circle.fill"
        case .taskCompleted: return "checkmark.circle.fill"
        case .taskCrashed: return "exclamationmark.triangle.fill"
        case .taskAssigned: return "person.badge.plus"
        case .reviewRequested: return "eye.fill"
        default: return "circle.fill"
        }
    }

    private func eventColor(_ eventType: ActivityEventType) -> Color {
        switch eventType {
        case .taskCreated: return .blue
        case .taskCompleted: return .green
        case .taskCrashed: return .red
        case .taskAssigned: return .cyan
        case .reviewRequested: return .orange
        default: return .secondary
        }
    }
}
