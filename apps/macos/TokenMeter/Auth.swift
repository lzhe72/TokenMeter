import Foundation
import Darwin
import CryptoKit

struct Account: Codable, Identifiable {
    let id: String
    let username: String
    let role: String
    let isActive: Bool
    let mustChangePassword: Bool
    enum CodingKeys: String, CodingKey {
        case id, username, role
        case isActive = "is_active", mustChangePassword = "must_change_password"
    }
}

struct AuthSession: Decodable {
    let accessToken: String
    let user: Account
    enum CodingKeys: String, CodingKey { case accessToken = "access_token", user }
}
struct AccountsResponse: Decodable { let users: [Account] }
struct AuditEvent: Decodable, Identifiable {
    let id: String
    let action: String
    let actorID: String?
    let targetID: String?
    let occurredAt: String
    enum CodingKeys: String, CodingKey {
        case id, action
        case actorID = "actor_id", targetID = "target_id", occurredAt = "occurred_at"
    }
}
struct AuditResponse: Decodable { let events: [AuditEvent] }
struct APIError: LocalizedError {
    let code: String
    let message: String
    var errorDescription: String? { "\(message) (\(code))" }
}
private struct ErrorResponse: Decodable {
    struct Details: Decodable { let code: String; let message: String }
    let error: Details
}

/// The API and updater share a transport policy. Only literal loopback hosts
/// and localhost may use HTTP; HTTPS always retains normal system TLS checks.
enum EndpointPolicy {
    static func url(_ input: String, serviceOrigin: Bool) throws -> URL {
        let value = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let code = serviceOrigin ? "invalid_server" : "invalid_update_source"
        let message = serviceOrigin
            ? "请输入本机回环 HTTP 或 HTTPS 服务地址；不能包含账号、路径或查询参数"
            : "请输入本机回环 HTTP 或 HTTPS 更新地址；不能包含账号、查询参数或片段"
        func invalid() -> APIError { APIError(code: code, message: message) }
        guard var components = URLComponents(string: value),
              let host = components.host, !host.isEmpty,
              components.user == nil, components.password == nil,
              components.query == nil, components.fragment == nil,
              !serviceOrigin || components.path.isEmpty || components.path == "/",
              components.scheme?.lowercased() == "https" ||
                (components.scheme?.lowercased() == "http" &&
                 ["localhost", "127.0.0.1", "::1", "[::1]"].contains(host.lowercased())) else { throw invalid() }
        if let port = components.port, !(1...65535).contains(port) { throw invalid() }
        // An explicit colon with no port is not an absent, default port.
        if let authority = value.split(separator: "/", omittingEmptySubsequences: false).dropFirst(2).first,
           authority.hasSuffix(":") {
            throw invalid()
        }
        components.scheme = components.scheme?.lowercased()
        components.host = host.lowercased()
        if (components.scheme == "https" && components.port == 443) ||
            (components.scheme == "http" && components.port == 80) { components.port = nil }
        if serviceOrigin { components.path = "" }
        guard let url = components.url else { throw invalid() }
        return url
    }
}

struct UpdateConfiguration {
    static let localFeed = "http://127.0.0.1:49177/appcast.xml"
    let defaults: UserDefaults
    let bundledFeed: String
    var initialFeed: String { defaults.string(forKey: "updateFeedURLOverride") ?? bundledFeed }

    init(defaults: UserDefaults = AppConfiguration().defaults,
         bundledFeed: String? = Bundle.main.object(forInfoDictionaryKey: "SUFeedURL") as? String) {
        self.defaults = defaults
        self.bundledFeed = bundledFeed.flatMap { $0.isEmpty ? nil : $0 } ?? Self.localFeed
    }

    func feedURL(_ input: String) throws -> URL { try EndpointPolicy.url(input, serviceOrigin: false) }
    func rememberFeed(_ url: URL) {
        if url == (try? feedURL(bundledFeed)) { defaults.removeObject(forKey: "updateFeedURLOverride") }
        else { defaults.set(url.absoluteString, forKey: "updateFeedURLOverride") }
    }
    func resetFeed() { defaults.removeObject(forKey: "updateFeedURLOverride") }
}

enum UpdateFailureReason: Equatable {
    static let policyDomain = "org.tokenmeter.UpdatePolicy"
    case sourceRejected, transportRejected, signatureRejected([Int]), noUpdate, other(Int)

    static func classify(_ error: Error, sparkleDomain: String) -> UpdateFailureReason {
        var current: NSError? = error as NSError
        var codes: [Int] = []
        var sourceRejected = false
        var transportRejected = false
        for _ in 0..<8 {
            guard let value = current else { break }
            if value.domain == sparkleDomain { codes.append(value.code) }
            if value.domain == policyDomain && value.code == 1 { sourceRejected = true }
            if value.domain == NSURLErrorDomain && value.code == NSURLErrorAppTransportSecurityRequiresSecureConnection {
                transportRejected = true
            }
            current = value.userInfo[NSUnderlyingErrorKey] as? NSError
        }
        if sourceRejected { return .sourceRejected }
        if transportRejected { return .transportRejected }
        if codes.contains(3001) || codes.contains(3002) { return .signatureRejected(codes) }
        if codes.contains(1001) { return .noUpdate }
        return .other((error as NSError).code)
    }

    var message: String {
        switch self {
        case .sourceRejected: return "更新包地址不符合安全要求 (update_source_rejected)"
        case .transportRejected: return "更新连接被系统安全策略拒绝 (update_transport_rejected: -1022)"
        case .signatureRejected(let codes):
            return "更新包验证失败 (update_signature_rejected: \(codes.map(String.init).joined(separator: ",")))"
        case .noUpdate: return "当前已是最新版本"
        case .other(let code): return "更新失败 (update_failed: \(code))"
        }
    }
}

struct AppConfiguration {
    static let localServer = "http://127.0.0.1:49176"
    let defaults: UserDefaults
    let initialServer: String
    let bundledServer: String
    let isolationID: String
    let credentialDirectory: URL?

    init() {
        #if UITESTING
        let environment = ProcessInfo.processInfo.environment
        let run = environment["TM_TEST_RUN_ID"] ?? Bundle.main.object(forInfoDictionaryKey: "TMTestRunID") as? String ?? ""
        if !run.isEmpty, run.range(of: "^[A-Za-z0-9_-]+$", options: .regularExpression) != nil {
            isolationID = run
            defaults = UserDefaults(suiteName: "org.tokenmeter.TokenMeter.UITesting.\(run)")!
            let path = environment["TM_TEST_CREDENTIALS_DIR"]
                ?? Bundle.main.object(forInfoDictionaryKey: "TMTestCredentialsDirectory") as? String ?? ""
            credentialDirectory = Self.testCredentialDirectory(path)
            let injected = environment["TM_TEST_API_URL"].flatMap { $0.isEmpty ? nil : $0 }
                ?? (Bundle.main.object(forInfoDictionaryKey: "TMTestAPIURL") as? String).flatMap { $0.isEmpty ? nil : $0 }
            bundledServer = injected ?? Self.localServer
            let legacy = defaults.string(forKey: "serviceURL")
            initialServer = defaults.string(forKey: "serviceURLOverride")
                ?? (legacy == bundledServer ? nil : legacy)
                ?? bundledServer
            return
        }
        // A misconfigured test build must never read the real user's credentials.
        isolationID = "invalid-test-configuration"
        credentialDirectory = nil
        defaults = UserDefaults(suiteName: "org.tokenmeter.TokenMeter.UITesting.invalid")!
        bundledServer = Self.localServer
        initialServer = Self.localServer
        #else
        isolationID = "production"
        credentialDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)
            .first?.appendingPathComponent("TokenMeter/credentials", isDirectory: true)
        defaults = .standard
        bundledServer = Self.localServer
        let legacy = defaults.string(forKey: "serviceURL")
        initialServer = defaults.string(forKey: "serviceURLOverride")
            ?? (legacy == bundledServer ? nil : legacy)
            ?? bundledServer
        #endif
    }

    #if UITESTING
    private static func testCredentialDirectory(_ path: String) -> URL? {
        guard path.hasPrefix("/"), let resolved = realpath(path, nil) else { return nil }
        defer { free(resolved) }
        guard String(cString: resolved) == path else { return nil }
        let production = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)
            .first?.appendingPathComponent("TokenMeter/credentials", isDirectory: true).path
        guard path != production else { return nil }
        var info = stat()
        guard lstat(path, &info) == 0, info.st_mode & mode_t(S_IFMT) == mode_t(S_IFDIR),
              info.st_uid == getuid(), info.st_mode & 0o7777 == 0o700 else { return nil }
        return URL(fileURLWithPath: path, isDirectory: true)
    }
    #endif

    func serverURL(_ input: String) throws -> URL {
        try EndpointPolicy.url(input, serviceOrigin: true)
    }

    func rememberServer(_ url: URL) {
        // A saved override is distinct from the app's bundled default. A later
        // version may update that default without replacing an explicit choice.
        if url.absoluteString == bundledServer {
            defaults.removeObject(forKey: "serviceURLOverride")
        } else {
            defaults.set(url.absoluteString, forKey: "serviceURLOverride")
        }
        defaults.removeObject(forKey: "serviceURL")
    }

    func resetServer() {
        defaults.removeObject(forKey: "serviceURLOverride")
        defaults.removeObject(forKey: "serviceURL")
    }
}

/// App-owned storage for a revocable bearer token, never an account password.
/// Permissions isolate other OS users; this is not hardware-bound or encrypted.
struct DeviceCredentialStore {
    let directory: URL
    let filename: String
    init(directory: URL, origin: URL) {
        self.directory = directory
        var components = URLComponents(url: origin, resolvingAgainstBaseURL: false)!
        components.scheme = components.scheme?.lowercased()
        components.host = components.host?.lowercased()
        if (components.scheme == "https" && components.port == 443) || (components.scheme == "http" && components.port == 80) {
            components.port = nil
        }
        components.path = ""
        let normalized = components.string!
        let digest = SHA256.hash(data: Data(normalized.utf8)).map { String(format: "%02x", $0) }.joined()
        filename = digest + ".token"
    }
    private var storageError: APIError {
        APIError(code: "credential_storage_unavailable", message: "无法访问本机登录凭据，请检查应用数据目录的所有者和权限后重试")
    }
    private func validToken(_ token: String) -> Bool {
        token.utf8.count == 43 && token.utf8.allSatisfy {
            (65...90).contains($0) || (97...122).contains($0) || (48...57).contains($0) || $0 == 45 || $0 == 95
        }
    }
    private func openDirectory(create: Bool) throws -> Int32? {
        let parts = directory.path.split(separator: "/").map(String.init)
        guard directory.isFileURL, !parts.isEmpty, !parts.contains("."), !parts.contains("..") else { throw storageError }
        var current = Darwin.open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC)
        guard current >= 0 else { throw storageError }
        var retained = false
        defer { if !retained { Darwin.close(current) } }
        for (index, part) in parts.enumerated() {
            var next = openat(current, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            if next < 0 && errno == ENOENT {
                if !create { return nil }
                guard mkdirat(current, part, 0o700) == 0 || errno == EEXIST else { throw storageError }
                next = openat(current, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            }
            guard next >= 0 else { throw storageError }
            Darwin.close(current)
            current = next
            var info = stat()
            guard fstat(current, &info) == 0, info.st_mode & mode_t(S_IFMT) == mode_t(S_IFDIR) else { throw storageError }
            if index == parts.count - 1 {
                guard info.st_uid == getuid(), info.st_mode & 0o7777 == 0o700 else { throw storageError }
            } else {
                // A sticky system temp directory is allowed; writable shared parents are not.
                guard info.st_uid == 0 || info.st_uid == getuid(),
                      info.st_mode & 0o022 == 0 || info.st_mode & mode_t(S_ISVTX) != 0 else { throw storageError }
            }
        }
        retained = true
        return current
    }
    private func openCredential(_ directoryFD: Int32) throws -> Int32? {
        // O_NONBLOCK prevents a substituted FIFO from hanging before fstat rejects it.
        let descriptor = openat(directoryFD, filename, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        if descriptor < 0 && errno == ENOENT { return nil }
        guard descriptor >= 0 else { throw storageError }
        var info = stat()
        guard fstat(descriptor, &info) == 0, info.st_mode & mode_t(S_IFMT) == mode_t(S_IFREG),
              info.st_uid == getuid(), info.st_mode & 0o7777 == 0o600, info.st_nlink <= 1 else {
            Darwin.close(descriptor)
            throw storageError
        }
        // A concurrent atomic replacement can unlink this already-open inode
        // (nlink == 0). The fd still owns its complete contents; >1 is a hardlink.
        return descriptor
    }
    func read() throws -> String? {
        guard let directoryFD = try openDirectory(create: false) else { return nil }
        defer { Darwin.close(directoryFD) }
        guard let descriptor = try openCredential(directoryFD) else { return nil }
        defer { Darwin.close(descriptor) }
        var info = stat()
        guard fstat(descriptor, &info) == 0, info.st_size == 43 else { throw storageError }
        var bytes = [UInt8](repeating: 0, count: 44)
        let count = bytes.withUnsafeMutableBytes { Darwin.read(descriptor, $0.baseAddress, $0.count) }
        guard count == 43, let token = String(bytes: bytes.prefix(count), encoding: .utf8), validToken(token) else { throw storageError }
        return token
    }
    func save(_ token: String) throws {
        guard validToken(token), let directoryFD = try openDirectory(create: true) else { throw storageError }
        defer { Darwin.close(directoryFD) }
        if let existing = try openCredential(directoryFD) { Darwin.close(existing) }
        let temporary = "." + UUID().uuidString + ".tmp"
        let descriptor = openat(directoryFD, temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard descriptor >= 0 else { throw storageError }
        var moved = false
        defer {
            Darwin.close(descriptor)
            if !moved { unlinkat(directoryFD, temporary, 0) }
        }
        try Data(token.utf8).withUnsafeBytes { buffer in
            var written = 0
            while written < buffer.count {
                let count = Darwin.write(descriptor, buffer.baseAddress!.advanced(by: written), buffer.count - written)
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else { throw storageError }
                written += count
            }
        }
        guard fsync(descriptor) == 0, renameat(directoryFD, temporary, directoryFD, filename) == 0 else { throw storageError }
        moved = true
        guard fsync(directoryFD) == 0 else {
            unlinkat(directoryFD, filename, 0)
            throw storageError
        }
    }
    func clear() throws {
        guard let directoryFD = try openDirectory(create: false) else { return }
        defer { Darwin.close(directoryFD) }
        guard let descriptor = try openCredential(directoryFD) else { return }
        Darwin.close(descriptor)
        guard unlinkat(directoryFD, filename, 0) == 0 || errno == ENOENT else { throw storageError }
        guard fsync(directoryFD) == 0 else { throw storageError }
    }
}

private final class RejectRedirects: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}

final class AuthAPI {
    let baseURL: URL
    private let session: URLSession
    init(baseURL: URL) {
        self.baseURL = baseURL
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 20
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        session = URLSession(configuration: configuration, delegate: RejectRedirects(), delegateQueue: nil)
    }
    func request<T: Decodable>(_ method: String, _ path: String, token: String? = nil,
                               body: [String: String]? = nil) async throws -> T {
        let data = try await perform(method, path, token: token, body: body)
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw APIError(code: "invalid_response", message: "服务返回了无法识别的数据") }
    }
    func logout(token: String) async throws { _ = try await perform("POST", "/v1/auth/logout", token: token) }
    private func perform(_ method: String, _ path: String, token: String?, body: [String: String]? = nil) async throws -> Data {
        let origin = baseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: origin + path) else { throw APIError(code: "invalid_server", message: "服务地址无效") }
        var request = URLRequest(url: url)
        request.httpMethod = method
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else {
            throw APIError(code: "invalid_response", message: "服务没有返回有效响应")
        }
        guard (200..<300).contains(response.statusCode) else {
            if let error = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError(code: error.error.code, message: error.error.message)
            }
            throw APIError(code: "http_\(response.statusCode)", message: "服务请求失败，请稍后重试")
        }
        return data
    }
}
