import SwiftUI
@preconcurrency import ConvexMobile
import Combine

// Replace this with your actual Convex deployment URL
private let CONVEX_URL = "https://your-deployment.convex.cloud"

enum ConnectionStatus {
    case disconnected
    case connecting
    case connected
    case error(String)

    var displayName: String {
        switch self {
        case .disconnected: return "Disconnected"
        case .connecting: return "Connecting..."
        case .connected: return "Connected"
        case .error(let msg): return "Error: \(msg)"
        }
    }

    var isConnected: Bool {
        if case .connected = self { return true }
        return false
    }
}

@Observable
@MainActor
final class ConvexClientManager {
    static let shared = ConvexClientManager()

    private(set) var connectionStatus: ConnectionStatus = .disconnected
    private(set) var client: ConvexClient?
    private var cancellable: AnyCancellable?

    private init() {
        connect()
    }

    func connect() {
        connectionStatus = .connecting
        let newClient = ConvexClient(deploymentUrl: CONVEX_URL)
        client = newClient
        cancellable = newClient.watchWebSocketState()
            .receive(on: DispatchQueue.main)
            .sink { [weak self] state in
                switch state {
                case .connecting:
                    self?.connectionStatus = .connecting
                case .connected:
                    self?.connectionStatus = .connected
                @unknown default:
                    self?.connectionStatus = .disconnected
                }
            }
    }

    func disconnect() {
        cancellable = nil
        client = nil
        connectionStatus = .disconnected
    }

    func reconnect() {
        disconnect()
        connect()
    }
}
