import SwiftUI

struct SettingsView: View {
    @Environment(AuthManager.self) private var auth
    @Environment(ConvexClientManager.self) private var convex

    @State private var showLogoutConfirmation = false

    var body: some View {
        List {
            // MARK: Boards
            Section("Boards") {
                NavigationLink {
                    BoardSettingsView()
                } label: {
                    Label("Manage Boards", systemImage: "square.grid.2x2")
                }
            }

            // MARK: Tags
            Section("Tags") {
                NavigationLink {
                    TagSettingsView()
                } label: {
                    Label("Manage Tags", systemImage: "tag")
                }
            }

            // MARK: Model Tiers
            Section("AI Models") {
                NavigationLink {
                    ModelTierSettingsView()
                } label: {
                    Label("Model Tiers", systemImage: "cpu")
                }
            }

            // MARK: Connection
            Section("Connection") {
                HStack {
                    Label("Status", systemImage: "wifi")
                    Spacer()
                    ConnectionStatusView()
                }
                LabeledContent("Convex URL") {
                    Text(convexURL)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            }

            // MARK: Account
            Section("Account") {
                Button(role: .destructive) {
                    showLogoutConfirmation = true
                } label: {
                    Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                }
            }

            // MARK: App Info
            Section {
                LabeledContent("Version", value: appVersion)
                LabeledContent("Build", value: buildNumber)
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

    private var convexURL: String {
        // Read from ConvexClientManager if exposed; fallback to placeholder
        "your-deployment.convex.cloud"
    }

    private var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "—"
    }

    private var buildNumber: String {
        Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "—"
    }
}
