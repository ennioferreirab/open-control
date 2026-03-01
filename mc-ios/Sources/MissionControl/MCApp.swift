import SwiftUI

@main
struct MCApp: App {
    @State private var authManager = AuthManager()
    @State private var convexManager = ConvexClientManager.shared
    @State private var boardStore = BoardStore()
    @State private var tagStore = TagStore()
    @State private var settingsStore = SettingsStore()
    @State private var agentStore = AgentStore()
    @State private var chatStore = ChatStore()

    var body: some Scene {
        WindowGroup {
            AppRootView()
                .environment(authManager)
                .environment(convexManager)
                .environment(boardStore)
                .environment(tagStore)
                .environment(settingsStore)
                .environment(agentStore)
                .environment(chatStore)
        }
    }
}
