import SwiftUI

struct KanbanColumnView: View {
    let status: TaskStatus
    let tasks: [MCTask]
    let onTaskTap: (MCTask) -> Void

    var columnColor: Color { status.color }

    var columnTitle: String { status.displayName }

    var body: some View {
        VStack(spacing: 0) {
            // Column header
            HStack(spacing: 8) {
                Text(columnTitle)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(.primary)

                Spacer()

                Text("\(tasks.count)")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundStyle(.primary)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .glassEffect(.regular.tint(columnColor), in: .capsule)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .glassEffect(.regular.tint(columnColor), in: .rect(cornerRadius: 8))

            // Task list
            ScrollView(.vertical, showsIndicators: false) {
                LazyVStack(spacing: 8) {
                    if tasks.isEmpty {
                        emptyColumnView
                    } else {
                        ForEach(tasks) { task in
                            TaskCardView(task: task, onTap: { onTaskTap(task) })
                        }
                    }
                }
                .padding(8)
            }
        }
        .frame(maxHeight: .infinity, alignment: .top)
        .glassEffect(.regular, in: .rect(cornerRadius: 12))
    }

    private var emptyColumnView: some View {
        VStack(spacing: 8) {
            Image(systemName: "tray")
                .font(.title2)
                .foregroundStyle(.tertiary)
            Text("No tasks")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
    }
}
