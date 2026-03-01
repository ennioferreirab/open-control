import Foundation

enum AuthError: LocalizedError {
    case invalidToken
    case keychainError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidToken: return "Invalid access token. Please check and try again."
        case .keychainError(let error): return "Keychain error: \(error.localizedDescription)"
        }
    }
}

@Observable
@MainActor
final class AuthManager {
    private(set) var isAuthenticated: Bool = false
    private(set) var isLoading: Bool = false

    init() {
        checkSession()
    }

    func checkSession() {
        do {
            let token = try KeychainManager.loadToken()
            isAuthenticated = token != nil
        } catch {
            isAuthenticated = false
        }
    }

    func login(token: String) async throws {
        isLoading = true
        defer { isLoading = false }

        let trimmed = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw AuthError.invalidToken
        }

        do {
            try KeychainManager.saveToken(trimmed)
        } catch {
            throw AuthError.keychainError(error)
        }

        isAuthenticated = true
    }

    func logout() {
        do {
            try KeychainManager.deleteToken()
        } catch {
            // Best-effort delete
        }
        isAuthenticated = false
        ConvexClientManager.shared.reconnect()
    }
}
