import SwiftUI

struct ConnectionStatusView: View {
    @Environment(ConvexClientManager.self) private var convex

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: symbolName)
                .symbolRenderingMode(.hierarchical)
                .foregroundStyle(statusColor)
                .symbolEffect(.pulse, isActive: isAnimating)
            Text(convex.connectionStatus.displayName)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .glassEffect(.regular.tint(statusColor), in: .capsule)
    }

    private var symbolName: String {
        switch convex.connectionStatus {
        case .connected: return "wifi"
        case .connecting: return "wifi.exclamationmark"
        case .disconnected: return "wifi.slash"
        case .error: return "exclamationmark.triangle"
        }
    }

    private var statusColor: Color {
        switch convex.connectionStatus {
        case .connected: return .green
        case .connecting: return .orange
        case .disconnected: return .secondary
        case .error: return .red
        }
    }

    private var isAnimating: Bool {
        if case .connecting = convex.connectionStatus { return true }
        return false
    }
}
