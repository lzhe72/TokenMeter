import XCTest
import CryptoKit
import Darwin

/// These cases run one at a time against a fresh database and isolated credential directory.
/// Direct API requests add server-side assertions; every case also drives the real UI.
final class TM001AccountUITests: XCTestCase {
    private var app: XCUIApplication!
    private var environment: [String: String] { ProcessInfo.processInfo.environment }
    private let changedPassword = "TEST-ONLY-Changed-42!"

    override func setUpWithError() throws {
        continueAfterFailure = false
        guard let api = environment["TM_TEST_API_URL"], URL(string: api) != nil,
              let run = environment["TM_TEST_RUN_ID"], !run.isEmpty,
              let credentials = environment["TM_TEST_CREDENTIALS_DIR"],
              credentials.hasPrefix("/"),
              canonicalPath(credentials) == credentials,
              credentials != FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Library/Application Support/TokenMeter/credentials").path else {
            throw NSError(domain: "TokenMeterE2E", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "Missing isolated API, run ID, or resolved credential directory"])
        }
        app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launchEnvironment["TM_TEST_API_URL"] = api
        app.launchEnvironment["TM_TEST_RUN_ID"] = run
        app.launchEnvironment["TM_TEST_CREDENTIALS_DIR"] = credentials
    }

    private func canonicalPath(_ path: String) -> String? {
        guard let resolved = realpath(path, nil) else { return nil }
        defer { free(resolved) }
        return String(cString: resolved)
    }

    override func tearDownWithError() throws {
        app?.terminate()
    }

    private func text(_ identifier: String, _ value: String, secure: Bool = false) {
        let field = secure ? app.secureTextFields[identifier] : app.textFields[identifier]
        XCTAssertTrue(field.waitForExistence(timeout: 15), "Missing \(identifier)")
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate(format: "enabled == YES"), object: field)
        XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 15), .completed)
        field.click()
        field.typeKey("a", modifierFlags: .command)
        field.typeText(value)
    }

    private func click(_ identifier: String) {
        let button = app.buttons[identifier]
        XCTAssertTrue(button.waitForExistence(timeout: 15), "Missing \(identifier)")
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate(format: "enabled == YES"), object: button)
        XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 15), .completed, "Disabled \(identifier)")
        button.click()
    }

    private func captureWindow(_ name: String) {
        // Capture only this real test app, after assertions establish the state.
        // Passwords use SecureField and credentials are never added as text attachments.
        let attachment = XCTAttachment(data: app.screenshot().pngRepresentation,
                                       uniformTypeIdentifier: "public.png")
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func loginUsername(_ username: String, password: String) {
        text("auth.username", username)
        text("auth.password", password, secure: true)
        click("auth.login")
    }

    private func login(_ name: String, password: String? = nil) {
        loginUsername("test-\(name)", password: password ?? "TEST-ONLY-\(name)-42!")
    }

    private func assertAutomaticLogin(_ enabled: Bool) {
        let checkbox = app.checkBoxes["auth.automatic-login"]
        XCTAssertTrue(checkbox.waitForExistence(timeout: 15))
        let selected = NSPredicate { object, _ in
            guard let checkbox = object as? XCUIElement, checkbox.isEnabled else { return false }
            if let number = checkbox.value as? NSNumber { return number.boolValue == enabled }
            return checkbox.value as? String == (enabled ? "1" : "0")
        }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: selected, object: checkbox)],
                                     timeout: 15), .completed)
    }

    private func credentialFile(baseURL: String? = nil) throws -> URL {
        let root = try XCTUnwrap(environment["TM_TEST_CREDENTIALS_DIR"])
        var origin = try XCTUnwrap(URLComponents(string: baseURL ?? environment["TM_TEST_API_URL"]!))
        origin.scheme = origin.scheme?.lowercased()
        origin.host = origin.host?.lowercased()
        if (origin.scheme == "http" && origin.port == 80) || (origin.scheme == "https" && origin.port == 443) {
            origin.port = nil
        }
        origin.path = ""
        let canonical = try XCTUnwrap(origin.string)
        let name = SHA256.hash(data: Data(canonical.utf8)).map { String(format: "%02x", $0) }.joined()
        return URL(fileURLWithPath: root, isDirectory: true).appendingPathComponent(name + ".token")
    }

    private func savedCredential(baseURL: String? = nil) throws -> String {
        let file = try credentialFile(baseURL: baseURL)
        let directory = try FileManager.default.attributesOfItem(atPath: file.deletingLastPathComponent().path)
        let attributes = try FileManager.default.attributesOfItem(atPath: file.path)
        XCTAssertEqual(directory[.type] as? FileAttributeType, .typeDirectory)
        XCTAssertEqual((directory[.posixPermissions] as? NSNumber)?.intValue, 0o700)
        XCTAssertEqual((directory[.ownerAccountID] as? NSNumber)?.intValue, Int(getuid()))
        XCTAssertEqual(attributes[.type] as? FileAttributeType, .typeRegular)
        XCTAssertEqual((attributes[.posixPermissions] as? NSNumber)?.intValue, 0o600)
        XCTAssertEqual((attributes[.ownerAccountID] as? NSNumber)?.intValue, Int(getuid()))
        let contents = try Data(contentsOf: file)
        let token = try XCTUnwrap(String(data: contents, encoding: .utf8))
        let valid = token.utf8.count == 43 && token.range(of: "^[A-Za-z0-9_-]{43}$", options: .regularExpression) != nil
        // Assert booleans only: never include a credential in failure values or attachments.
        XCTAssertTrue(valid, "Persist only the opaque session token")
        return token
    }

    private func assertNoSavedCredential(baseURL: String? = nil) throws {
        let file = try credentialFile(baseURL: baseURL)
        XCTAssertFalse(FileManager.default.fileExists(atPath: file.path), "Current origin credential must be removed")
    }

    private func changePassword(current: String, new: String) {
        text("password.current", current, secure: true)
        text("password.new", new, secure: true)
        text("password.confirm", new, secure: true)
        click("password.submit")
        XCTAssertTrue(app.staticTexts["password.status"].waitForExistence(timeout: 15))
    }

    private func assertIdentity(_ username: String) {
        let identity = app.staticTexts["session.username"]
        XCTAssertTrue(identity.waitForExistence(timeout: 15))
        // AppKit static text exposes its displayed string as AXValue. Its AXLabel
        // can be empty; reading label would not verify the visible account name.
        XCTAssertEqual(identity.value as? String, username,
                       "session.username value=\(String(describing: identity.value)), label=\(identity.label)")
    }

    private func refreshIdentity(_ username: String) throws {
        let verified = app.staticTexts["session.verified"]
        XCTAssertTrue(verified.waitForExistence(timeout: 15))
        let previous = try XCTUnwrap(verified.value as? String)
        click("session.refresh")
        expectation(for: NSPredicate(format: "exists == YES AND value != %@", previous), evaluatedWith: verified)
        waitForExpectations(timeout: 15)
        XCTAssertFalse(app.staticTexts["session.unverified"].exists)
        assertIdentity(username)
    }

    private func request(_ method: String, _ path: String, token: String? = nil,
                         body: [String: Any]? = nil, baseURL: String? = nil) throws -> (Int, [String: Any]) {
        let url = URL(string: (baseURL ?? environment["TM_TEST_API_URL"]!) + path)!
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 15
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let completed = expectation(description: "\(method) \(path)")
        var responseData: Data?
        var responseStatus = 0
        var responseError: Error?
        URLSession.shared.dataTask(with: request) { data, response, error in
            responseData = data
            responseStatus = (response as? HTTPURLResponse)?.statusCode ?? 0
            responseError = error
            completed.fulfill()
        }.resume()
        wait(for: [completed], timeout: 20)
        if let responseError { throw responseError }
        let json = (try responseData.flatMap { $0.isEmpty ? nil : try JSONSerialization.jsonObject(with: $0) }) as? [String: Any] ?? [:]
        return (responseStatus, json)
    }

    private func token(_ name: String, password: String? = nil) throws -> String {
        let (status, response) = try request("POST", "/v1/auth/login", body: [
            "username": "test-\(name)", "password": password ?? "TEST-ONLY-\(name)-42!"
        ])
        XCTAssertEqual(status, 200)
        return try XCTUnwrap(response["access_token"] as? String)
    }

    func testE2E_TM001_001() throws {
        let oldToken = try token("alice")
        app.launch()
        XCTAssertTrue(app.buttons["auth.login"].waitForExistence(timeout: 15))
        assertAutomaticLogin(true)
        captureWindow("TM001-001-01-login")
        login("alice")
        XCTAssertTrue(app.secureTextFields["password.new"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.buttons["admin.accounts"].exists)
        changePassword(current: "TEST-ONLY-alice-42!", new: changedPassword)
        assertIdentity("test-alice")
        let savedToken = try savedCredential()
        captureWindow("TM001-001-02-authenticated-account")
        XCTAssertEqual(try request("GET", "/v1/me", token: oldToken).0, 401)
        XCTAssertEqual(try request("POST", "/v1/auth/login", body: [
            "username": "test-alice", "password": "TEST-ONLY-alice-42!"
        ]).0, 401)
        app.terminate()
        app.launch()
        assertIdentity("test-alice")
        try refreshIdentity("test-alice")
        XCTAssertTrue(try savedCredential() == savedToken)
        let initialAdmin = try token("admin")
        let adminChanged = try request("POST", "/v1/auth/change-password", token: initialAdmin,
                                       body: ["current_password": "TEST-ONLY-admin-42!", "new_password": changedPassword])
        XCTAssertEqual(adminChanged.0, 200)
        let adminToken = try XCTUnwrap(adminChanged.1["access_token"] as? String)
        func aliceLogoutCount() throws -> Int {
            let result = try request("GET", "/v1/admin/audit", token: adminToken)
            XCTAssertEqual(result.0, 200)
            let events = try XCTUnwrap(result.1["events"] as? [[String: Any]])
            return events.filter { $0["action"] as? String == "logout" && $0["actor_id"] as? String == "00000000-0000-4000-8000-000000000002" }.count
        }
        let logoutCount = try aliceLogoutCount()
        click("session.logout")
        XCTAssertTrue(app.buttons["auth.login"].waitForExistence(timeout: 15))
        try assertNoSavedCredential()
        // The login form appears after local cleanup, before server revocation finishes.
        // Its username field becomes enabled when logout completes; the empty-password
        // login button remains disabled even when the form is otherwise ready.
        let logoutFinished = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "exists == YES AND enabled == YES"),
            object: app.textFields["auth.username"])
        XCTAssertEqual(XCTWaiter.wait(for: [logoutFinished], timeout: 30), .completed)
        XCTAssertEqual(try request("GET", "/v1/me", token: savedToken).0, 401)
        XCTAssertEqual(try aliceLogoutCount(), logoutCount + 1, "UI logout must reach the real session revocation endpoint")
        app.terminate()
        app.launch()
        XCTAssertTrue(app.buttons["auth.login"].waitForExistence(timeout: 15))
        assertAutomaticLogin(true)
        app.checkBoxes["auth.automatic-login"].click()
        assertAutomaticLogin(false)
        login("alice", password: changedPassword)
        assertIdentity("test-alice")
        try assertNoSavedCredential()
        app.terminate()
        app.launch()
        XCTAssertTrue(app.buttons["auth.login"].waitForExistence(timeout: 15))
        assertAutomaticLogin(false)
        app.checkBoxes["auth.automatic-login"].click()
        assertAutomaticLogin(true)
        login("alice", password: changedPassword)
        assertIdentity("test-alice")
        _ = try savedCredential()
    }

    func testE2E_TM001_002() throws {
        app.launch()
        login("bob", password: "TEST-ONLY-Wrong-42!")
        let incorrect = app.staticTexts["auth.error"]
        expectation(for: NSPredicate(format: "value CONTAINS %@", "invalid_credentials"), evaluatedWith: incorrect)
        waitForExpectations(timeout: 15)
        login("disabled")
        let error = app.staticTexts["auth.error"]
        expectation(for: NSPredicate(format: "value CONTAINS %@", "account_disabled"), evaluatedWith: error)
        waitForExpectations(timeout: 15)
        login("bob")
        changePassword(current: "TEST-ONLY-bob-42!", new: changedPassword)
        assertIdentity("test-bob")
        XCTAssertEqual(app.staticTexts["session.role"].value as? String, "member")
        XCTAssertFalse(app.buttons["admin.accounts"].exists)
        let memberToken = try token("bob", password: changedPassword)
        let me = try request("GET", "/v1/me", token: memberToken)
        XCTAssertEqual(me.0, 200)
        XCTAssertEqual(me.1["username"] as? String, "test-bob")
        for path in ["/v1/admin/users", "/v1/admin/audit"] {
            XCTAssertEqual(try request("GET", path, token: memberToken).0, 403)
        }
        XCTAssertEqual(try request("POST", "/v1/admin/users/00000000-0000-4000-8000-000000000002/disable", token: memberToken).0, 403)
        try refreshIdentity("test-bob")
        captureWindow("TM001-002-01-member-permissions")
    }

    func testE2E_TM001_003() throws {
        let oldMemberToken = try token("bob")
        app.launch()
        login("admin")
        changePassword(current: "TEST-ONLY-admin-42!", new: changedPassword)
        assertIdentity("test-admin")
        click("admin.accounts")
        click("admin.reset.test-bob")
        text("admin.temporary-password", "TEST-ONLY-Reset-42!", secure: true)
        click("admin.reset.confirm")
        let resetStatus = app.staticTexts["admin.status"]
        XCTAssertTrue(resetStatus.waitForExistence(timeout: 15))
        expectation(for: NSPredicate(format: "value CONTAINS %@", "password_reset"), evaluatedWith: resetStatus)
        waitForExpectations(timeout: 15)
        XCTAssertEqual(try request("GET", "/v1/me", token: oldMemberToken).0, 401)
        click("admin.disable.test-bob")
        let inactive = app.staticTexts["admin.state.test-bob"]
        let disabled = NSPredicate(format: "value == %@", "disabled")
        expectation(for: disabled, evaluatedWith: inactive)
        waitForExpectations(timeout: 15)
        XCTAssertEqual(try request("POST", "/v1/auth/login", body: [
            "username": "test-bob", "password": "TEST-ONLY-Reset-42!"
        ]).0, 403)
        click("admin.enable.test-bob")
        click("admin.audit")
        XCTAssertTrue(app.staticTexts["audit.action.password_reset"].firstMatch.waitForExistence(timeout: 15))
        XCTAssertTrue(app.staticTexts["audit.action.account_disabled"].firstMatch.exists)
        XCTAssertTrue(app.staticTexts["audit.action.account_enabled"].firstMatch.exists)
        XCTAssertTrue(app.staticTexts["audit.target.password_reset.00000000-0000-4000-8000-000000000003"].firstMatch.exists)
        XCTAssertTrue(app.staticTexts["audit.actor.password_reset.00000000-0000-4000-8000-000000000001"].firstMatch.exists)
        captureWindow("TM001-003-01-admin-audit")
        click("session.logout")
        login("bob", password: "TEST-ONLY-Reset-42!")
        changePassword(current: "TEST-ONLY-Reset-42!", new: "TEST-ONLY-Bob-New-42!")
        assertIdentity("test-bob")
        let savedBob = try savedCredential()
        let administrator = try token("admin", password: changedPassword)
        let endpoint = "/v1/admin/users/00000000-0000-4000-8000-000000000003"
        XCTAssertEqual(try request("POST", endpoint + "/reset-password", token: administrator,
                                   body: ["temporary_password": "TEST-ONLY-Reset-42!"]).0, 200)
        XCTAssertEqual(try request("GET", "/v1/me", token: savedBob).0, 401)
        app.terminate()
        app.launch()
        expectation(for: NSPredicate(format: "exists == YES AND value CONTAINS %@", "invalid_session"),
                    evaluatedWith: app.staticTexts["auth.error"])
        waitForExpectations(timeout: 15)
        XCTAssertTrue(app.buttons["auth.login"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["session.username"].exists)
        try assertNoSavedCredential()

        login("bob", password: "TEST-ONLY-Reset-42!")
        assertIdentity("test-bob")
        let beforeDisable = try savedCredential()
        XCTAssertEqual(try request("POST", endpoint + "/disable", token: administrator).0, 200)
        XCTAssertEqual(try request("GET", "/v1/me", token: beforeDisable).0, 401)
        app.terminate()
        app.launch()
        expectation(for: NSPredicate(format: "exists == YES AND value CONTAINS %@", "invalid_session"),
                    evaluatedWith: app.staticTexts["auth.error"])
        waitForExpectations(timeout: 15)
        XCTAssertTrue(app.buttons["auth.login"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["session.username"].exists)
        try assertNoSavedCredential()
        captureWindow("TM001-003-02-revoked-automatic-login")
    }

    func testE2E_TM001_004() throws {
        let controlURL = try XCTUnwrap(environment["TM_TEST_UPDATE_CONTROL_URL"])
        let controlToken = try XCTUnwrap(environment["TM_TEST_UPDATE_CONTROL_TOKEN"])
        let expectedBuild = try XCTUnwrap(environment["TM_TEST_EXPECTED_BUILD"])
        XCTAssertTrue(controlURL.hasPrefix("https://"))
        app.launch()
        login("alice")
        changePassword(current: "TEST-ONLY-alice-42!", new: changedPassword)
        assertIdentity("test-alice")
        let beforeUpgrade = try savedCredential()
        let originalBuild = try XCTUnwrap(app.staticTexts["app.build"].value as? String)
        XCTAssertFalse(originalBuild.isEmpty)
        XCTAssertNotEqual(originalBuild, expectedBuild)
        click("updates.check")
        let installInvalid = app.buttons["Install Update"].firstMatch
        XCTAssertTrue(installInvalid.waitForExistence(timeout: 30))
        installInvalid.click()
        let cancelInvalid = app.buttons["Cancel Update"].firstMatch
        XCTAssertTrue(cancelInvalid.waitForExistence(timeout: 45))
        cancelInvalid.click()
        let updateError = app.staticTexts["updates.status"]
        expectation(for: NSPredicate(format: "value CONTAINS %@", "update_signature_rejected"), evaluatedWith: updateError)
        waitForExpectations(timeout: 45)
        XCTAssertEqual(app.staticTexts["app.build"].value as? String, originalBuild)
        app.terminate()
        // Only the external fixture changes; the application keeps the exact same feed and trust policy.
        var control = URLRequest(url: try XCTUnwrap(URL(string: controlURL)))
        control.httpMethod = "POST"
        control.setValue("Bearer \(controlToken)", forHTTPHeaderField: "Authorization")
        let switched = expectation(description: "Switch isolated update feed to valid archive")
        var controlStatus = 0
        URLSession.shared.dataTask(with: control) { _, response, _ in
            controlStatus = (response as? HTTPURLResponse)?.statusCode ?? 0
            switched.fulfill()
        }.resume()
        wait(for: [switched], timeout: 15)
        XCTAssertEqual(controlStatus, 200)
        app.launch()
        assertIdentity("test-alice")
        click("updates.check")
        let installValid = app.buttons["Install Update"].firstMatch
        XCTAssertTrue(installValid.waitForExistence(timeout: 30))
        installValid.click()
        let relaunch = app.buttons["Install and Relaunch"].firstMatch
        XCTAssertTrue(relaunch.waitForExistence(timeout: 60))
        relaunch.click()
        // Sparkle must replace and relaunch the app; no test calls launch() here.
        expectation(for: NSPredicate(format: "value == %@", expectedBuild),
                    evaluatedWith: app.staticTexts["app.build"])
        waitForExpectations(timeout: 90)
        assertIdentity("test-alice")
        try refreshIdentity("test-alice")
        XCTAssertTrue(try savedCredential() == beforeUpgrade,
                      "The real upgraded application must restore the same persisted session")
        captureWindow("TM001-004-01-updated-account")
    }

    func testE2E_TM001_005() throws {
        let initialLogin = try request("POST", "/v1/auth/login", body: [
            "username": "admin", "password": "123456"
        ])
        XCTAssertEqual(initialLogin.0, 200)
        let initialUser = try XCTUnwrap(initialLogin.1["user"] as? [String: Any])
        XCTAssertEqual(initialUser["username"] as? String, "admin")
        XCTAssertEqual(initialUser["role"] as? String, "admin")
        XCTAssertEqual(initialUser["must_change_password"] as? Bool, true)
        let initialToken = try XCTUnwrap(initialLogin.1["access_token"] as? String)
        let denied = try request("GET", "/v1/admin/users", token: initialToken)
        XCTAssertEqual(denied.0, 403)
        XCTAssertEqual((denied.1["error"] as? [String: Any])?["code"] as? String,
                       "password_change_required")

        app.launch()
        XCTAssertTrue(app.buttons["auth.login"].waitForExistence(timeout: 15))
        loginUsername("admin", password: "123456")
        assertIdentity("admin")
        XCTAssertEqual(app.staticTexts["session.role"].value as? String, "admin")
        XCTAssertTrue(app.secureTextFields["password.new"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.buttons["admin.accounts"].exists)
        captureWindow("TM001-005-01-initial-password-change")

        changePassword(current: "123456", new: changedPassword)
        XCTAssertTrue(app.buttons["admin.accounts"].waitForExistence(timeout: 15))
        assertIdentity("admin")
        XCTAssertEqual(try request("GET", "/v1/me", token: initialToken).0, 401)
        XCTAssertEqual(try request("POST", "/v1/auth/login", body: [
            "username": "admin", "password": "123456"
        ]).0, 401)

        click("admin.accounts")
        XCTAssertTrue(app.staticTexts["admin.state.admin"].waitForExistence(timeout: 15))
        XCTAssertTrue(app.buttons["admin.reset.admin"].exists)
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "admin.reset.test-")).count, 0)
        let changedLogin = try request("POST", "/v1/auth/login", body: [
            "username": "admin", "password": changedPassword
        ])
        XCTAssertEqual(changedLogin.0, 200)
        let changedToken = try XCTUnwrap(changedLogin.1["access_token"] as? String)
        let accounts = try request("GET", "/v1/admin/users", token: changedToken)
        XCTAssertEqual(accounts.0, 200)
        let users = try XCTUnwrap(accounts.1["users"] as? [[String: Any]])
        XCTAssertEqual(users.count, 1)
        XCTAssertEqual(users.first?["id"] as? String, "00000000-0000-4000-8000-000000000005")
        XCTAssertEqual(users.first?["username"] as? String, "admin")
        XCTAssertEqual(users.first?["role"] as? String, "admin")
        XCTAssertEqual(users.first?["must_change_password"] as? Bool, false)
        captureWindow("TM001-005-02-production-admin-only")

        app.terminate()
        app.launch()
        assertIdentity("admin")
        XCTAssertTrue(app.buttons["admin.accounts"].waitForExistence(timeout: 15))
        click("session.logout")
        XCTAssertTrue(app.buttons["auth.login"].waitForExistence(timeout: 15))
        loginUsername("admin", password: changedPassword)
        assertIdentity("admin")
        XCTAssertTrue(app.buttons["admin.accounts"].waitForExistence(timeout: 15))
        try refreshIdentity("admin")
        captureWindow("TM001-005-03-admin-relogin")
    }

    func testE2E_TM001_006() throws {
        let first = try XCTUnwrap(environment["TM_TEST_API_URL"])
        let second = try XCTUnwrap(environment["TM_TEST_SECOND_API_URL"])
        XCTAssertEqual(first, "http://127.0.0.1:49176")
        XCTAssertTrue(second.hasPrefix("http://127.0.0.1:"))
        XCTAssertNotEqual(first, second)
        XCTAssertNotEqual(try credentialFile(baseURL: first), try credentialFile(baseURL: second))

        // The test process uses TM_TEST_API_URL for independent HTTP assertions.
        // The App itself must read its shipped default, with no test URL injection.
        app.launchEnvironment.removeValue(forKey: "TM_TEST_API_URL")
        app.launch()
        let serverField = app.textFields["auth.server"]
        XCTAssertTrue(serverField.waitForExistence(timeout: 15))
        XCTAssertEqual(serverField.value as? String, first)
        captureWindow("TM001-006-01-default-server")

        let firstToken = try token("alice")
        XCTAssertEqual(try request("GET", "/v1/me", token: firstToken).0, 200)
        XCTAssertEqual(try request("GET", "/v1/me", token: firstToken, baseURL: second).0, 401)
        login("alice")
        assertIdentity("test-alice")
        let savedFirst = try savedCredential(baseURL: first)
        XCTAssertEqual(try request("GET", "/v1/me", token: savedFirst, baseURL: first).0, 200)
        XCTAssertEqual(try request("GET", "/v1/me", token: savedFirst, baseURL: second).0, 401)
        app.terminate()
        app.launch()
        assertIdentity("test-alice")
        XCTAssertTrue(try savedCredential(baseURL: first) == savedFirst)
        click("session.logout")
        XCTAssertTrue(serverField.waitForExistence(timeout: 15))
        try assertNoSavedCredential(baseURL: first)

        text("auth.server", second)
        // The second database has the same account name but an independent seed.
        // This password cannot authenticate against the first service.
        XCTAssertEqual(try request("POST", "/v1/auth/login", body: [
            "username": "test-alice", "password": "TEST-ONLY-alice-43!"
        ]).0, 401)
        login("alice", password: "TEST-ONLY-alice-43!")
        assertIdentity("test-alice")
        changePassword(current: "TEST-ONLY-alice-43!", new: changedPassword)
        let savedSecond = try savedCredential(baseURL: second)
        XCTAssertEqual(try request("GET", "/v1/me", token: savedSecond, baseURL: second).0, 200)
        XCTAssertEqual(try request("GET", "/v1/me", token: savedSecond, baseURL: first).0, 401)
        try assertNoSavedCredential(baseURL: first)
        app.terminate()
        app.launch()
        assertIdentity("test-alice")
        try refreshIdentity("test-alice")
        XCTAssertTrue(try savedCredential(baseURL: second) == savedSecond)
        captureWindow("TM001-006-02-second-server-restored")
        click("session.logout")
        XCTAssertTrue(app.buttons["auth.login"].waitForExistence(timeout: 15))
        XCTAssertEqual(app.textFields["auth.server"].value as? String, second)
        try assertNoSavedCredential(baseURL: second)

        text("auth.server", "http://192.0.2.1:49176")
        login("bob")
        let error = app.staticTexts["auth.error"]
        expectation(for: NSPredicate(format: "value CONTAINS %@", "invalid_server"), evaluatedWith: error)
        waitForExpectations(timeout: 15)
        XCTAssertTrue(app.buttons["auth.login"].exists)

        // A local HTTPS endpoint with an HTTP server proves the URL passes the
        // address validator, then fails at TLS/network rather than invalid_server.
        text("auth.server", second.replacingOccurrences(of: "http://", with: "https://"))
        login("bob")
        expectation(for: NSPredicate(format: "value CONTAINS %@", "无法连接服务"), evaluatedWith: error)
        waitForExpectations(timeout: 30)
        XCTAssertTrue(app.buttons["auth.login"].exists)
    }
}
