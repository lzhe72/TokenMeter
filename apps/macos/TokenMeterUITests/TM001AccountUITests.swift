import XCTest

/// These cases run one at a time against a fresh database and Keychain namespace.
/// Direct API requests add server-side assertions; every case also drives the real UI.
final class TM001AccountUITests: XCTestCase {
    private var app: XCUIApplication!
    private var environment: [String: String] { ProcessInfo.processInfo.environment }
    private let changedPassword = "TEST-ONLY-Changed-42!"

    override func setUpWithError() throws {
        continueAfterFailure = false
        guard let api = environment["TM_TEST_API_URL"], URL(string: api) != nil,
              let run = environment["TM_TEST_RUN_ID"], !run.isEmpty else {
            throw NSError(domain: "TokenMeterE2E", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "Missing isolated API URL or run ID"])
        }
        app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launchEnvironment["TM_TEST_API_URL"] = api
        app.launchEnvironment["TM_TEST_RUN_ID"] = run
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

    private func login(_ name: String, password: String? = nil) {
        text("auth.username", "test-\(name)")
        text("auth.password", password ?? "TEST-ONLY-\(name)-42!", secure: true)
        click("auth.login")
    }

    private func changePassword(current: String, new: String) {
        text("password.current", current, secure: true)
        text("password.new", new, secure: true)
        text("password.confirm", new, secure: true)
        click("password.submit")
        XCTAssertTrue(app.staticTexts["password.status"].waitForExistence(timeout: 15))
    }

    private func assertIdentity(_ username: String) {
        let label = app.staticTexts["session.username"]
        XCTAssertTrue(label.waitForExistence(timeout: 15))
        XCTAssertEqual(label.label, username)
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
                         body: [String: Any]? = nil) throws -> (Int, [String: Any]) {
        let url = URL(string: environment["TM_TEST_API_URL"]! + path)!
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
        login("alice")
        XCTAssertTrue(app.secureTextFields["password.new"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.buttons["admin.accounts"].exists)
        changePassword(current: "TEST-ONLY-alice-42!", new: changedPassword)
        assertIdentity("test-alice")
        XCTAssertEqual(try request("GET", "/v1/me", token: oldToken).0, 401)
        XCTAssertEqual(try request("POST", "/v1/auth/login", body: [
            "username": "test-alice", "password": "TEST-ONLY-alice-42!"
        ]).0, 401)
        app.terminate()
        app.launch()
        assertIdentity("test-alice")
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
        XCTAssertEqual(try aliceLogoutCount(), logoutCount + 1, "UI logout must reach the real session revocation endpoint")
        app.terminate()
        app.launch()
        XCTAssertTrue(app.buttons["auth.login"].waitForExistence(timeout: 15))
        login("alice", password: changedPassword)
        assertIdentity("test-alice")
    }

    func testE2E_TM001_002() throws {
        app.launch()
        login("bob", password: "TEST-ONLY-Wrong-42!")
        let incorrect = app.staticTexts["auth.error"]
        expectation(for: NSPredicate(format: "label CONTAINS %@", "invalid_credentials"), evaluatedWith: incorrect)
        waitForExpectations(timeout: 15)
        login("disabled")
        let error = app.staticTexts["auth.error"]
        expectation(for: NSPredicate(format: "label CONTAINS %@", "account_disabled"), evaluatedWith: error)
        waitForExpectations(timeout: 15)
        login("bob")
        changePassword(current: "TEST-ONLY-bob-42!", new: changedPassword)
        assertIdentity("test-bob")
        XCTAssertEqual(app.staticTexts["session.role"].label, "member")
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
        XCTAssertTrue(resetStatus.label.contains("password_reset"))
        XCTAssertEqual(try request("GET", "/v1/me", token: oldMemberToken).0, 401)
        click("admin.disable.test-bob")
        let inactive = app.staticTexts["admin.state.test-bob"]
        let disabled = NSPredicate(format: "label == %@", "disabled")
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
        click("session.logout")
        login("bob", password: "TEST-ONLY-Reset-42!")
        changePassword(current: "TEST-ONLY-Reset-42!", new: "TEST-ONLY-Bob-New-42!")
        assertIdentity("test-bob")
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
        let originalBuild = app.staticTexts["app.build"].label
        XCTAssertNotEqual(originalBuild, expectedBuild)
        click("updates.check")
        let installInvalid = app.buttons["Install Update"].firstMatch
        XCTAssertTrue(installInvalid.waitForExistence(timeout: 30))
        installInvalid.click()
        let cancelInvalid = app.buttons["Cancel Update"].firstMatch
        XCTAssertTrue(cancelInvalid.waitForExistence(timeout: 45))
        cancelInvalid.click()
        let updateError = app.staticTexts["updates.status"]
        expectation(for: NSPredicate(format: "label CONTAINS %@", "update_signature_rejected"), evaluatedWith: updateError)
        waitForExpectations(timeout: 45)
        XCTAssertEqual(app.staticTexts["app.build"].label, originalBuild)
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
        expectation(for: NSPredicate(format: "label == %@", expectedBuild),
                    evaluatedWith: app.staticTexts["app.build"])
        waitForExpectations(timeout: 90)
        assertIdentity("test-alice")
        try refreshIdentity("test-alice")
    }
}
