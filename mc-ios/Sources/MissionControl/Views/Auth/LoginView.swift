import SwiftUI

struct LoginView: View {
    @Environment(AuthManager.self) private var auth

    @State private var token: String = ""
    @State private var showError: Bool = false
    @State private var errorMessage: String = ""
    @State private var isSubmitting: Bool = false

    var body: some View {
        VStack(spacing: 32) {
            Spacer()

            // App identity
            VStack(spacing: 12) {
                Image(systemName: "cpu.fill")
                    .font(.system(size: 64))
                    .foregroundStyle(.tint)
                    .symbolEffect(.pulse)

                Text("Mission Control")
                    .font(.largeTitle.bold())

                Text("Enter your access token to continue")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            Spacer()

            // Login form
            VStack(spacing: 16) {
                SecureField("Access Token", text: $token)
                    .textContentType(.password)
                    .font(.body)
                    .padding()
                    .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
                    .submitLabel(.go)
                    .onSubmit { submitLogin() }

                Button {
                    submitLogin()
                } label: {
                    Group {
                        if auth.isLoading {
                            ProgressView()
                                .controlSize(.small)
                        } else {
                            Text("Sign In")
                                .fontWeight(.semibold)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(token.trimmingCharacters(in: .whitespaces).isEmpty || auth.isLoading)
            }
            .padding(.horizontal, 24)

            Spacer()
        }
        .alert("Sign In Failed", isPresented: $showError) {
            Button("OK") { token = "" }
        } message: {
            Text(errorMessage)
        }
    }

    private func submitLogin() {
        let trimmed = token.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }

        Task {
            do {
                try await auth.login(token: trimmed)
            } catch {
                errorMessage = error.localizedDescription
                showError = true
            }
        }
    }
}
