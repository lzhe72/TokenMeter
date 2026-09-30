import Foundation
import Combine

@MainActor
final class AccountStore: ObservableObject {
    @Published var server: String
    @Published private(set) var account: Account?
    @Published private(set) var accounts: [Account] = []
    @Published private(set) var audit: [AuditEvent] = []
    @Published private(set) var busy = false
    @Published private(set) var identityVerified = false
    @Published private(set) var lastIdentityCheck = ""
    @Published private(set) var hasPendingLogout = false
    @Published var errorMessage: String?
    @Published var adminStatus: String?
    @Published var passwordStatus: String?
    private let configuration: AppConfiguration
    private var api: AuthAPI?
    private var keychain: TokenKeychain?
    private var token: String?
    private var pendingLogout: (AuthAPI, String)?

    init() {
        let configuration = AppConfiguration()
        self.configuration = configuration
        server = configuration.initialServer
    }

    private func connect() throws {
        let url = try configuration.serverURL(server)
        api = AuthAPI(baseURL: url)
        keychain = TokenKeychain(origin: url, isolationID: configuration.isolationID)
        configuration.rememberServer(url)
    }

    func restore() async {
        guard !server.isEmpty else { return }
        await perform {
            try self.connect()
            self.token = try self.keychain?.read()
            if self.token != nil { try await self.loadIdentity() }
        }
    }

    func login(username: String, password: String) async {
        await perform {
            try self.connect()
            let session: AuthSession = try await self.api!.request("POST", "/v1/auth/login", body: ["username": username, "password": password])
            try self.accept(session)
        }
    }

    func changePassword(current: String, new: String) async {
        passwordStatus = nil
        await perform {
            let (api, token) = try self.authenticated()
            let session: AuthSession = try await api.request("POST", "/v1/auth/change-password", token: token,
                                                           body: ["current_password": current, "new_password": new])
            try self.accept(session)
            self.passwordStatus = "密码已更新；旧会话已撤销"
        }
    }

    func logout() async {
        await perform {
            let (api, token) = try self.authenticated()
            var unconfirmed = false
            do { try await api.logout(token: token) }
            catch let error as APIError where error.code == "invalid_session" || error.code == "account_disabled" { }
            catch {
                self.pendingLogout = (api, token)
                self.hasPendingLogout = true
                unconfirmed = true
            }
            try self.keychain?.clear()
            self.clearIdentity()
            if unconfirmed {
                self.errorMessage = "已清除本机登录凭据；服务端会话撤销尚未确认，请恢复网络后重试。退出 App 会丢弃本次重试凭据。"
            }
        }
    }

    func retryLogout() async {
        await perform {
            guard let (api, token) = self.pendingLogout else { return }
            do { try await api.logout(token: token) }
            catch let error as APIError where error.code == "invalid_session" || error.code == "account_disabled" { }
            self.pendingLogout = nil
            self.hasPendingLogout = false
        }
    }

    func refresh() async { await perform { try await self.loadIdentity() } }

    func loadAccounts() async {
        await perform {
            let (api, token) = try self.authenticated()
            let response: AccountsResponse = try await api.request("GET", "/v1/admin/users", token: token)
            self.accounts = response.users
        }
    }

    func manage(_ account: Account, action: String, temporaryPassword: String? = nil) async {
        await perform {
            let (api, token) = try self.authenticated()
            let body = temporaryPassword.map { ["temporary_password": $0] }
            let updated: Account = try await api.request("POST", "/v1/admin/users/\(account.id)/\(action)", token: token, body: body)
            if updated.id == self.account?.id && action == "reset-password" {
                defer { self.clearIdentity() }
                try self.keychain?.clear()
                return
            }
            if let index = self.accounts.firstIndex(where: { $0.id == updated.id }) { self.accounts[index] = updated }
            self.adminStatus = action == "reset-password" ? "password_reset" : "account_\(action == "disable" ? "disabled" : "enabled")"
        }
    }

    func loadAudit() async {
        await perform {
            let (api, token) = try self.authenticated()
            let response: AuditResponse = try await api.request("GET", "/v1/admin/audit", token: token)
            self.audit = response.events
        }
    }

    private func authenticated() throws -> (AuthAPI, String) {
        guard let api, let token else { throw APIError(code: "invalid_session", message: "请重新登录") }
        return (api, token)
    }

    private func loadIdentity() async throws {
        identityVerified = false
        let (api, token) = try authenticated()
        let user: Account = try await api.request("GET", "/v1/me", token: token)
        account = user
        identityVerified = true
        lastIdentityCheck = String(Date().timeIntervalSince1970)
    }

    private func accept(_ session: AuthSession) throws {
        do { try keychain?.save(session.accessToken) }
        catch {
            clearIdentity()
            throw error
        }
        token = session.accessToken
        account = session.user
        identityVerified = true
        lastIdentityCheck = String(Date().timeIntervalSince1970)
        accounts = []
        audit = []
        adminStatus = nil
        passwordStatus = nil
    }

    private func clearIdentity() {
        token = nil
        account = nil
        identityVerified = false
        lastIdentityCheck = ""
        accounts = []
        audit = []
        adminStatus = nil
        passwordStatus = nil
    }

    private func perform(_ operation: () async throws -> Void) async {
        guard !busy else { return }
        busy = true
        errorMessage = nil
        defer { busy = false }
        do { try await operation() }
        catch {
            if !(error is APIError) { identityVerified = false }
            var cleanupMessage: String?
            if let apiError = error as? APIError,
               ["invalid_session", "account_disabled"].contains(apiError.code), token != nil {
                do { try keychain?.clear() }
                catch { cleanupMessage = "会话已失效，安全凭据清理失败，请解锁钥匙串后重试" }
                clearIdentity()
            }
            errorMessage = cleanupMessage ?? (error as? APIError)?.errorDescription ?? "无法连接服务，请检查网络后重试"
        }
    }
}
