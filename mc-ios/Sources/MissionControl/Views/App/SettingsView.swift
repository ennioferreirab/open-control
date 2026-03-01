import SwiftUI

struct SettingsView: View {
    @Environment(AuthManager.self) private var auth
    @Environment(ConvexClientManager.self) private var convex

    @State private var showLogoutConfirmation: Bool = false

    var body: some View {
        List {
            Section("Connection") {
                HStack {
                    Label("Status", systemImage: "wifi")
                    Spacer()
                    ConnectionStatusView()
                }
            }

            Section("Account") {
                Button(role: .destructive) {
                    showLogoutConfirmation = true
                } label: {
                    Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                }
            }
        }
        .navigationTitle("Settings")
        .confirmationDialog(
            "Sign Out",
            isPresented: $showLogoutConfirmation,
            titleVisibility: .visible
        ) {
            Button("Sign Out", role: .destructive) {
                auth.logout()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("You will need your access token to sign in again.")
        }
    }
}
