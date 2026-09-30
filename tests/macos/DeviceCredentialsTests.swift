import Foundation
import Darwin

// A small throwing-assertion harness keeps these component tests runnable with
// Command Line Tools, which do not ship XCTest. Product E2E still uses XCUITest.
private var failureCount = 0
private func fail(_ message: String, file: StaticString = #filePath, line: UInt = #line) {
    failureCount += 1
    print("FAIL \(file):\(line): \(message)")
}
private func XCTAssertTrue(_ value: @autoclosure () throws -> Bool, file: StaticString = #filePath, line: UInt = #line) {
    do { if try !value() { fail("expected true", file: file, line: line) } }
    catch { fail("unexpected storage error", file: file, line: line) }
}
private func XCTAssertFalse(_ value: @autoclosure () throws -> Bool, file: StaticString = #filePath, line: UInt = #line) {
    do { if try value() { fail("expected false", file: file, line: line) } }
    catch { fail("unexpected storage error", file: file, line: line) }
}
private func XCTAssertEqual<T: Equatable>(_ left: @autoclosure () throws -> T, _ right: @autoclosure () throws -> T,
                                         file: StaticString = #filePath, line: UInt = #line) {
    do { if try left() != right() { fail("values differ", file: file, line: line) } }
    catch { fail("unexpected storage error", file: file, line: line) }
}
private func XCTAssertNotEqual<T: Equatable>(_ left: @autoclosure () -> T, _ right: @autoclosure () -> T,
                                            file: StaticString = #filePath, line: UInt = #line) {
    if left() == right() { fail("values unexpectedly equal", file: file, line: line) }
}
private func XCTAssertNil<T>(_ value: @autoclosure () throws -> T?, file: StaticString = #filePath, line: UInt = #line) {
    do { if try value() != nil { fail("expected no value", file: file, line: line) } }
    catch { fail("unexpected storage error", file: file, line: line) }
}
private func XCTAssertThrowsError<T>(_ operation: @autoclosure () throws -> T, file: StaticString = #filePath, line: UInt = #line) {
    do { _ = try operation(); fail("unsafe operation was accepted", file: file, line: line) }
    catch { }
}

final class DeviceCredentialsTests {
    private var root: URL!
    private var directory: URL { root.appendingPathComponent("credentials") }
    private let firstToken = String(repeating: "a", count: 43)
    private let secondToken = String(repeating: "b", count: 43)
    private func store(_ origin: String = "https://example.com") -> DeviceCredentialStore {
        DeviceCredentialStore(directory: directory, origin: URL(string: origin)!)
    }
    func setUpWithError() throws {
        // Foundation keeps the macOS /var alias; use the OS canonical path so
        // the real store can reject every symlink component without exceptions.
        guard let resolved = realpath(FileManager.default.temporaryDirectory.path, nil) else {
            throw NSError(domain: "FixtureDirectory", code: 1)
        }
        defer { free(resolved) }
        root = URL(fileURLWithPath: String(cString: resolved), isDirectory: true)
            .appendingPathComponent("tokenmeter-credentials-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: false,
                                               attributes: [.posixPermissions: 0o700])
    }
    func tearDownWithError() throws { try FileManager.default.removeItem(at: root) }

    func testMissingStorageIsEmpty() throws {
        XCTAssertNil(try store().read())
        try store().clear()
        XCTAssertFalse(FileManager.default.fileExists(atPath: directory.path))
    }
    func testPersistReplaceAndClear() throws {
        let target = store()
        try target.save(firstToken)
        XCTAssertTrue(try store().read() == firstToken)
        let file = directory.appendingPathComponent(target.filename)
        let attributes = try FileManager.default.attributesOfItem(atPath: file.path)
        XCTAssertEqual(attributes[.posixPermissions] as? Int, 0o600)
        XCTAssertEqual(attributes[.ownerAccountID] as? UInt32, getuid())
        XCTAssertEqual(try FileManager.default.attributesOfItem(atPath: directory.path)[.posixPermissions] as? Int, 0o700)
        try target.save(secondToken)
        XCTAssertTrue(try target.read() == secondToken)
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: directory.path), [target.filename])
        try target.clear()
        XCTAssertNil(try target.read())
    }
    func testOriginNormalizationAndIsolation() throws {
        try store("HTTPS://EXAMPLE.COM:443/").save(firstToken)
        XCTAssertTrue(try store().read() == firstToken)
        XCTAssertNil(try store("https://example.com:8443").read())
        XCTAssertNil(try store("http://example.com").read())
        try store("https://example.com:8443").save(secondToken)
        try store().clear()
        XCTAssertTrue(try store("https://example.com:8443").read() == secondToken)
    }
    func testRejectInsecureDirectory() throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false,
                                               attributes: [.posixPermissions: 0o755])
        XCTAssertThrowsError(try store().save(firstToken))
        XCTAssertThrowsError(try store().read())
    }
    func testRejectDirectorySymlinksIncludingParent() throws {
        let outside = root.appendingPathComponent("outside")
        try FileManager.default.createDirectory(at: outside, withIntermediateDirectories: false,
                                               attributes: [.posixPermissions: 0o700])
        try FileManager.default.createSymbolicLink(at: directory, withDestinationURL: outside)
        XCTAssertThrowsError(try store().save(firstToken))
        let nested = DeviceCredentialStore(directory: directory.appendingPathComponent("nested"),
                                            origin: URL(string: "https://example.com")!)
        XCTAssertThrowsError(try nested.save(firstToken))
        XCTAssertTrue(try FileManager.default.contentsOfDirectory(atPath: outside.path).isEmpty)
    }
    func testRejectFileSymlinkAndHardlink() throws {
        let target = store()
        try target.save(firstToken)
        let file = directory.appendingPathComponent(target.filename)
        let outside = root.appendingPathComponent("outside-token")
        try FileManager.default.moveItem(at: file, to: outside)
        try FileManager.default.createSymbolicLink(at: file, withDestinationURL: outside)
        XCTAssertThrowsError(try target.read())
        XCTAssertThrowsError(try target.save(secondToken))
        XCTAssertThrowsError(try target.clear())
        try FileManager.default.removeItem(at: file)
        try FileManager.default.linkItem(at: outside, to: file)
        XCTAssertThrowsError(try target.read())
        XCTAssertThrowsError(try target.save(secondToken))
        XCTAssertTrue(try String(contentsOf: outside, encoding: .utf8) == firstToken)
    }
    func testRejectFilePermissionsAndType() throws {
        let target = store()
        try target.save(firstToken)
        let file = directory.appendingPathComponent(target.filename)
        try FileManager.default.setAttributes([.posixPermissions: 0o644], ofItemAtPath: file.path)
        XCTAssertThrowsError(try target.read())
        XCTAssertThrowsError(try target.save(secondToken))
        try FileManager.default.removeItem(at: file)
        XCTAssertEqual(mkfifo(file.path, 0o600), 0)
        XCTAssertThrowsError(try target.read())
        XCTAssertThrowsError(try target.save(secondToken))
    }
    func testRejectMalformedOrOversizedToken() throws {
        let target = store()
        for invalid in ["", "short", String(repeating: "a", count: 44), String(repeating: "!", count: 43)] {
            XCTAssertThrowsError(try target.save(invalid))
        }
        try target.save(firstToken)
        let file = directory.appendingPathComponent(target.filename)
        for invalid in [Data(), Data(repeating: 97, count: 65536), Data(repeating: 255, count: 43)] {
            try invalid.write(to: file)
            XCTAssertThrowsError(try target.read())
        }
        // A fresh login may replace corrupt content only if ownership/type/mode remain valid.
        try target.save(secondToken)
        XCTAssertTrue(try target.read() == secondToken)
    }
    func testInterruptedTemporaryWriteCannotReplaceCredential() throws {
        try store().save(firstToken)
        let unfinished = directory.appendingPathComponent(".interrupted.tmp")
        try Data("incomplete".utf8).write(to: unfinished)
        XCTAssertTrue(try store().read() == firstToken)
        try store().save(secondToken)
        XCTAssertTrue(try store().read() == secondToken)
        XCTAssertEqual(try String(contentsOf: unfinished, encoding: .utf8), "incomplete")
    }
    func testMissingUITestConfigurationNeverSelectsProductionStorage() {
        // The harness has no test App Info.plist or injected run/directory.
        XCTAssertNil(AppConfiguration().credentialDirectory)
        XCTAssertNotEqual(AppConfiguration().isolationID, "production")
    }
    func testConcurrentReplacementNeverExposesPartialToken() throws {
        let target = store()
        try target.save(firstToken)
        let lock = NSLock()
        var invalidReads = 0
        DispatchQueue.concurrentPerform(iterations: 30) { index in
            var failed = false
            do {
                try target.save(index % 2 == 0 ? firstToken : secondToken)
                let value = try target.read()
                failed = value != firstToken && value != secondToken
            } catch { failed = true }
            if failed { lock.lock(); invalidReads += 1; lock.unlock() }
        }
        XCTAssertEqual(invalidReads, 0)
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: directory.path), [target.filename])
    }
    func testUITestConfigurationRequiresExistingPrivateCanonicalDirectory() throws {
        let keys = ["TM_TEST_RUN_ID", "TM_TEST_CREDENTIALS_DIR"]
        let previous = ProcessInfo.processInfo.environment
        let run = "component-" + UUID().uuidString
        defer {
            for key in keys {
                if let value = previous[key] { setenv(key, value, 1) } else { unsetenv(key) }
            }
            UserDefaults.standard.removePersistentDomain(forName: "org.tokenmeter.TokenMeter.UITesting." + run)
        }
        setenv("TM_TEST_RUN_ID", run, 1)
        setenv("TM_TEST_CREDENTIALS_DIR", directory.path, 1)
        XCTAssertNil(AppConfiguration().credentialDirectory)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false,
                                               attributes: [.posixPermissions: 0o700])
        XCTAssertEqual(AppConfiguration().credentialDirectory?.path, directory.path)
        let alias = root.appendingPathComponent("alias")
        try FileManager.default.createSymbolicLink(at: alias, withDestinationURL: directory)
        setenv("TM_TEST_CREDENTIALS_DIR", alias.path, 1)
        XCTAssertNil(AppConfiguration().credentialDirectory)
        setenv("TM_TEST_CREDENTIALS_DIR", directory.path, 1)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: directory.path)
        XCTAssertNil(AppConfiguration().credentialDirectory)
        unsetenv("TM_TEST_RUN_ID")
        XCTAssertNil(AppConfiguration().credentialDirectory)
    }
    func testServiceOriginValidationAndNormalization() throws {
        let configuration = AppConfiguration()
        XCTAssertEqual(try configuration.serverURL("HTTPS://EXAMPLE.COM:443/").absoluteString, "https://example.com")
        XCTAssertEqual(try configuration.serverURL("http://localhost:80/").absoluteString, "http://localhost")
        XCTAssertEqual(try configuration.serverURL("http://[::1]:49176").absoluteString, "http://[::1]:49176")
        for invalid in ["http://example.com", "https://user:secret@example.com", "https://example.com/path", "https://example.com?key=value"] {
            XCTAssertThrowsError(try configuration.serverURL(invalid))
        }
    }
    static let allTests: [(String, (DeviceCredentialsTests) -> () throws -> Void)] = [
        ("testMissingStorageIsEmpty", testMissingStorageIsEmpty),
        ("testPersistReplaceAndClear", testPersistReplaceAndClear),
        ("testOriginNormalizationAndIsolation", testOriginNormalizationAndIsolation),
        ("testRejectInsecureDirectory", testRejectInsecureDirectory),
        ("testRejectDirectorySymlinksIncludingParent", testRejectDirectorySymlinksIncludingParent),
        ("testRejectFileSymlinkAndHardlink", testRejectFileSymlinkAndHardlink),
        ("testRejectFilePermissionsAndType", testRejectFilePermissionsAndType),
        ("testRejectMalformedOrOversizedToken", testRejectMalformedOrOversizedToken),
        ("testInterruptedTemporaryWriteCannotReplaceCredential", testInterruptedTemporaryWriteCannotReplaceCredential),
        ("testMissingUITestConfigurationNeverSelectsProductionStorage", testMissingUITestConfigurationNeverSelectsProductionStorage),
        ("testConcurrentReplacementNeverExposesPartialToken", testConcurrentReplacementNeverExposesPartialToken),
        ("testUITestConfigurationRequiresExistingPrivateCanonicalDirectory", testUITestConfigurationRequiresExistingPrivateCanonicalDirectory),
        ("testServiceOriginValidationAndNormalization", testServiceOriginValidationAndNormalization),
    ]
}

@main struct RunCredentialTests {
    static func main() {
        for (name, run) in DeviceCredentialsTests.allTests {
            let before = failureCount
            let test = DeviceCredentialsTests()
            do { try test.setUpWithError(); try run(test)() }
            catch { fail("\(name): unexpected error") }
            do { try test.tearDownWithError() }
            catch { fail("\(name): cleanup failed") }
            print("\(name): \(failureCount == before ? "PASS" : "FAIL")")
        }
        print("Swift credential component checks: \(DeviceCredentialsTests.allTests.count) tests, \(failureCount) failures")
        exit(failureCount == 0 ? 0 : 1)
    }
}
