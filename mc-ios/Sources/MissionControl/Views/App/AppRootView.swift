import SwiftUI

struct AppRootView: View {
    @Environment(AuthManager.self) private var auth
    @Environment(\.horizontalSizeClass) private var sizeClass

    var body: some View {
        if auth.isAuthenticated {
            if sizeClass == .compact {
                CompactTabView()
            } else {
                SplitNavView()
            }
        } else {
            LoginView()
        }
    }
}
