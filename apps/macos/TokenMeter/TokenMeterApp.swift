import SwiftUI

@main
struct TokenMeterApp: App {
    @StateObject private var store = AccountStore()
    @StateObject private var updates = UpdateController()

    var body: some Scene {
        WindowGroup("TokenMeter") {
            AccountView(store: store, updates: updates)
                .frame(minWidth: 650, minHeight: 540)
                .task { await store.restore() }
        }
        .commands {
            CommandGroup(after: .appInfo) {
                Button("检查更新…") { updates.check() }
                    .disabled(!updates.canCheck)
            }
        }
    }
}

struct AccountView: View {
    @ObservedObject var store: AccountStore
    @ObservedObject var updates: UpdateController
    @State private var username = ""
    @State private var password = ""
    @State private var currentPassword = ""
    @State private var newPassword = ""
    @State private var confirmation = ""
    @State private var showAccounts = false
    @State private var showAudit = false
    @State private var resetAccount: Account?
    @State private var temporaryPassword = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack {
                VStack(alignment: .leading) {
                    Text("TokenMeter").font(.largeTitle.bold())
                    Text("团队模型用量").foregroundStyle(.secondary)
                }
                Spacer()
                Text(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "")
                Text(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "")
                    .accessibilityIdentifier("app.build")
            }
            Divider()
            if let account = store.account {
                HStack {
                    Text(account.username).font(.headline).accessibilityIdentifier("session.username")
                    Text(account.role).foregroundStyle(.secondary).accessibilityIdentifier("session.role")
                    Spacer()
                    Button("刷新身份") { Task { await store.refresh() } }.accessibilityIdentifier("session.refresh")
                    Button("退出登录") { Task { await store.logout() } }.accessibilityIdentifier("session.logout")
                }
                if store.identityVerified {
                    Text("身份已由服务端确认").font(.caption).foregroundStyle(.secondary)
                        .accessibilityIdentifier("session.verified").accessibilityValue(store.lastIdentityCheck)
                }
                if !store.identityVerified {
                    Text("当前身份尚未重新确认。请检查服务连接，再刷新身份。")
                        .foregroundStyle(.orange).accessibilityIdentifier("session.unverified")
                } else if account.mustChangePassword {
                    Text("首次登录，请修改初始密码").font(.title2)
                    passwordForm
                } else {
                    HStack {
                        Button("修改密码") { showAccounts = false; showAudit = false }
                        if account.role == "admin" {
                            Button("管理账号") { showAccounts = true; showAudit = false; Task { await store.loadAccounts() } }
                                .accessibilityIdentifier("admin.accounts")
                            Button("审计记录") { showAudit = true; showAccounts = false; Task { await store.loadAudit() } }
                                .accessibilityIdentifier("admin.audit")
                        }
                    }
                    if showAccounts && account.role == "admin" { accountsView }
                    else if showAudit && account.role == "admin" { auditView }
                    else { passwordForm }
                }
            } else { loginForm }
            if let error = store.errorMessage {
                Text(error).foregroundStyle(.red).textSelection(.enabled).accessibilityIdentifier("auth.error")
            }
            if store.hasPendingLogout {
                Button("重试服务端退出") { Task { await store.retryLogout() } }
                    .accessibilityIdentifier("session.retry-logout")
            }
            if store.busy { ProgressView().controlSize(.small) }
            Spacer(minLength: 8)
            Divider()
            HStack {
                Button("检查更新…") { updates.check() }
                    .disabled(!updates.canCheck).accessibilityIdentifier("updates.check")
                Text(updates.status).font(.caption).foregroundStyle(.secondary).accessibilityIdentifier("updates.status")
            }
        }
        .padding(28)
        .disabled(store.busy)
        .sheet(item: $resetAccount) { account in
            VStack(alignment: .leading, spacing: 16) {
                Text("重置 \(account.username) 的密码").font(.headline)
                Text("此操作会撤销该账号的全部会话，下次登录须再次改密。")
                SecureField("临时密码（12–128 位）", text: $temporaryPassword)
                    .accessibilityIdentifier("admin.temporary-password")
                HStack {
                    Button("取消") { temporaryPassword = ""; resetAccount = nil }
                    Spacer()
                    Button("重置密码") {
                        let value = temporaryPassword
                        temporaryPassword = ""
                        resetAccount = nil
                        Task { await store.manage(account, action: "reset-password", temporaryPassword: value) }
                    }
                    .disabled(temporaryPassword.count < 12 || temporaryPassword.count > 128)
                    .accessibilityIdentifier("admin.reset.confirm")
                }
            }.padding(24).frame(width: 440)
        }
        .onChange(of: store.account?.id) { _, _ in
            password = ""; currentPassword = ""; newPassword = ""; confirmation = ""
            showAccounts = false; showAudit = false
        }
    }

    private var loginForm: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("登录团队账号").font(.title2)
            TextField("HTTPS 服务地址", text: $store.server).accessibilityIdentifier("auth.server")
            TextField("账号", text: $username).accessibilityIdentifier("auth.username")
            SecureField("密码", text: $password).accessibilityIdentifier("auth.password")
            Button("登录") {
                let secret = password
                password = ""
                Task { await store.login(username: username, password: secret) }
            }.disabled(username.isEmpty || password.isEmpty || store.server.isEmpty)
                .accessibilityIdentifier("auth.login")
            Text("账号由团队管理员预置。忘记密码请联系管理员重置。")
                .font(.caption).foregroundStyle(.secondary)
        }.textFieldStyle(.roundedBorder)
    }

    private var passwordForm: some View {
        VStack(alignment: .leading, spacing: 12) {
            SecureField("当前密码", text: $currentPassword).accessibilityIdentifier("password.current")
            SecureField("新密码（12–128 位）", text: $newPassword).accessibilityIdentifier("password.new")
            SecureField("确认新密码", text: $confirmation).accessibilityIdentifier("password.confirm")
            Button("保存新密码") {
                let old = currentPassword, new = newPassword
                currentPassword = ""; newPassword = ""; confirmation = ""
                Task { await store.changePassword(current: old, new: new) }
            }.disabled(currentPassword.isEmpty || newPassword.count < 12 || newPassword.count > 128 || newPassword != confirmation)
                .accessibilityIdentifier("password.submit")
            Text("改密后，其他设备的旧会话将失效。")
                .font(.caption).foregroundStyle(.secondary)
            if let status = store.passwordStatus {
                Text(status).accessibilityIdentifier("password.status")
            }
        }.textFieldStyle(.roundedBorder)
    }

    private var accountsView: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let status = store.adminStatus { Text(status).accessibilityIdentifier("admin.status") }
            ScrollView {
                VStack(spacing: 12) {
                    ForEach(store.accounts) { user in
                        HStack {
                            Text(user.username).frame(width: 130, alignment: .leading)
                            Text(user.role).frame(width: 60)
                            Text(user.isActive ? "active" : "disabled")
                                .accessibilityIdentifier("admin.state.\(user.username)")
                            Spacer()
                            Button(user.isActive ? "停用" : "启用") {
                                Task { await store.manage(user, action: user.isActive ? "disable" : "enable") }
                            }.accessibilityIdentifier("admin.\(user.isActive ? "disable" : "enable").\(user.username)")
                            Button("重置密码") { temporaryPassword = ""; resetAccount = user }
                                .accessibilityIdentifier("admin.reset.\(user.username)")
                        }
                    }
                }
            }
        }
    }

    private var auditView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(store.audit) { event in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(event.action).accessibilityIdentifier("audit.action.\(event.action)")
                            Spacer()
                            Text(event.occurredAt).font(.caption).foregroundStyle(.secondary)
                        }
                        Text("操作者：\(event.actorID ?? "系统")")
                            .font(.caption).accessibilityIdentifier("audit.actor.\(event.action).\(event.actorID ?? "system")")
                        Text("对象：\(event.targetID ?? "无")")
                            .font(.caption).accessibilityIdentifier("audit.target.\(event.action).\(event.targetID ?? "none")")
                    }
                }
            }
        }
    }
}
