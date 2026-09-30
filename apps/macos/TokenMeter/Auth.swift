import Foundation
import Security
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

struct AppConfiguration {
    static let localServer = "http://127.0.0.1:49176"
    let defaults: UserDefaults
    let initialServer: String
    let bundledServer: String
    let isolationID: String

    init() {
        #if UITESTING
        let environment = ProcessInfo.processInfo.environment
        let run = environment["TM_TEST_RUN_ID"] ?? Bundle.main.object(forInfoDictionaryKey: "TMTestRunID") as? String ?? ""
        if !run.isEmpty, run.range(of: "^[A-Za-z0-9_-]+$", options: .regularExpression) != nil {
            isolationID = run
            defaults = UserDefaults(suiteName: "org.tokenmeter.TokenMeter.UITesting.\(run)")!
            let injected = environment["TM_TEST_API_URL"].flatMap { $0.isEmpty ? nil : $0 }
                ?? (Bundle.main.object(forInfoDictionaryKey: "TMTestAPIURL") as? String).flatMap { $0.isEmpty ? nil : $0 }
            bundledServer = injected ?? Self.localServer
            let legacy = defaults.string(forKey: "serviceURL")
            initialServer = defaults.string(forKey: "serviceURLOverride")
                ?? (legacy == bundledServer ? nil : legacy)
                ?? bundledServer
            return
        }
        #endif
        isolationID = "production"
        defaults = .standard
        bundledServer = Self.localServer
        let legacy = defaults.string(forKey: "serviceURL")
        initialServer = defaults.string(forKey: "serviceURLOverride")
            ?? (legacy == bundledServer ? nil : legacy)
            ?? bundledServer
    }

    func serverURL(_ input: String) throws -> URL {
        let value = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard var components = URLComponents(string: value), let host = components.host,
              components.user == nil, components.password == nil,
              components.query == nil, components.fragment == nil,
              components.path.isEmpty || components.path == "/",
              components.scheme == "https" || (components.scheme == "http" && ["localhost", "127.0.0.1", "::1"].contains(host)) else {
            throw APIError(code: "invalid_server", message: "请输入本机回环 HTTP 或 HTTPS 服务地址；不能包含账号、路径或查询参数")
        }
        if components.path == "/" { components.path = "" }
        guard let url = components.url else {
            throw APIError(code: "invalid_server", message: "服务地址无效")
        }
        return url
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
}

struct TokenKeychain {
    let service: String
    init(origin: URL, isolationID: String) {
        let normalized = origin.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let digest = SHA256.hash(data: Data(normalized.utf8)).map { String(format: "%02x", $0) }.joined()
        service = "org.tokenmeter.session.\(isolationID).\(digest)"
    }
    private var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service, kSecAttrAccount as String: "access-token"]
    }
    func read() throws -> String? {
        var lookup = query
        lookup[kSecReturnData as String] = true
        lookup[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(lookup as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data,
              let token = String(data: data, encoding: .utf8) else { throw keychainError(status) }
        return token
    }
    func save(_ token: String) throws {
        let attributes: [String: Any] = [kSecValueData as String: Data(token.utf8)]
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            var item = query
            item[kSecValueData as String] = Data(token.utf8)
            item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            let addStatus = SecItemAdd(item as CFDictionary, nil)
            guard addStatus == errSecSuccess else { throw keychainError(addStatus) }
        } else if status != errSecSuccess { throw keychainError(status) }
    }
    func clear() throws {
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw keychainError(status) }
    }
    private func keychainError(_ status: OSStatus) -> APIError {
        APIError(code: "keychain_\(status)", message: "无法访问安全凭据存储，请解锁钥匙串后重试")
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
