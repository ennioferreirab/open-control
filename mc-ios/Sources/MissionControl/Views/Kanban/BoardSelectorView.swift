import SwiftUI

struct BoardSelectorView: View {
    @Environment(TaskStore.self) private var taskStore
    @Environment(BoardStore.self) private var boardStore
    @AppStorage("selectedBoardId") private var selectedBoardId: String = ""

    private var currentBoardName: String {
        boardStore.boards.first { $0.id == selectedBoardId }?.displayName
            ?? boardStore.defaultBoard?.displayName
            ?? "Select Board"
    }

    var body: some View {
        Menu {
            ForEach(boardStore.boards) { board in
                Button {
                    selectedBoardId = board.id
                    taskStore.setBoard(board.id)
                } label: {
                    if selectedBoardId == board.id {
                        Label(board.displayName, systemImage: "checkmark")
                    } else {
                        Text(board.displayName)
                    }
                }
            }
        } label: {
            HStack(spacing: 4) {
                Text(currentBoardName)
                    .font(.headline)
                Image(systemName: "chevron.up.chevron.down")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .accessibilityHidden(true)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .glassEffect(.regular, in: .capsule)
        }
        .task {
            boardStore.startSubscription()
        }
        .onChange(of: boardStore.boards) { _, boards in
            guard !boards.isEmpty else { return }
            if selectedBoardId.isEmpty, let defaultBoard = boardStore.defaultBoard {
                selectedBoardId = defaultBoard.id
                taskStore.setBoard(defaultBoard.id)
            } else if !selectedBoardId.isEmpty, taskStore.currentBoardId == nil {
                taskStore.setBoard(selectedBoardId)
            }
        }
    }
}
