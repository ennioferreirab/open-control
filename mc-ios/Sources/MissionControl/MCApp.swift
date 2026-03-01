import SwiftUI
import UserNotifications

@main
struct MCApp: App {
    @State private var authManager = AuthManager()
    @State private var convexManager = ConvexClientManager.shared
    @State private var boardStore = BoardStore()
    @State private var tagStore = TagStore()
    @State private var settingsStore = SettingsStore()
    @State private var agentStore = AgentStore()
    @State private var chatStore = ChatStore()
    @State private var taskStore = TaskStore()
    @State private var activityStore = ActivityStore()
    @State private var messageStore = MessageStore()
    @State private var stepStore = StepStore()
    @State private var notificationManager = NotificationManager()
    @State private var deepLinkHandler = DeepLinkHandler()

    @Environment(\.scenePhase) private var scenePhase

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
                .environment(taskStore)
                .environment(activityStore)
                .environment(messageStore)
                .environment(stepStore)
                .environment(notificationManager)
                .environment(deepLinkHandler)
                .task {
                    await notificationManager.requestPermission()
                }
                .onChange(of: taskStore.tasks) { _, newTasks in
                    notificationManager.checkForStatusChanges(
                        tasks: newTasks,
                        scenePhase: scenePhase
                    )
                }
        }
        .commands {
            CommandGroup(after: .newItem) {
                Button("New Task") {
                    NotificationCenter.default.post(name: .createNewTask, object: nil)
                }
                .keyboardShortcut("n")
            }
        }
    }
}

extension Notification.Name {
    static let createNewTask = Notification.Name("MCCreateNewTask")
    static let refreshTasks = Notification.Name("MCRefreshTasks")
}
