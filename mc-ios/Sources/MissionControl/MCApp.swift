import SwiftUI

@main
struct MCApp: App {
    @State private var authManager = AuthManager()
    @State private var convexManager = ConvexClientManager.shared

    var body: some Scene {
        WindowGroup {
            AppRootView()
                .environment(authManager)
                .environment(convexManager)
        }
    }
}
