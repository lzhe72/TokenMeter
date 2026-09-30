import Foundation
import Darwin

private var failures = 0
private var assertions = 0
private func expect(_ condition: @autoclosure () throws -> Bool, _ label: String) {
    assertions += 1
    do {
        if try !condition() { failures += 1; print("FAIL: \(label)") }
    } catch { failures += 1; print("FAIL: \(label) (unexpected error)") }
}
private func rejects(_ label: String, _ operation: () throws -> Void) {
    assertions += 1
    do { try operation(); failures += 1; print("FAIL: \(label) was accepted") }
    catch { }
}

@main struct RunEndpointConfigurationTests {
    static func main() {
        let run = "endpoint-" + UUID().uuidString
        setenv("TM_TEST_RUN_ID", run, 1)
        unsetenv("TM_TEST_API_URL")
        let configuration = AppConfiguration()
        let defaults = configuration.defaults
        let suiteName = "org.tokenmeter.TokenMeter.UITesting." + run
        expect(try configuration.serverURL("http://127.0.0.1:49176").absoluteString == "http://127.0.0.1:49176", "local API")
        for value in ["https://", "https://:443", "http://127.0.0.1:0", "http://127.0.0.1:65536"] {
            rejects("invalid API address") { _ = try configuration.serverURL(value) }
        }
        let updates = UpdateConfiguration(defaults: defaults, bundledFeed: nil)
        expect(updates.initialFeed == "http://127.0.0.1:49177/appcast.xml", "shipped update default")
        expect(UpdateConfiguration(defaults: defaults, bundledFeed: "").initialFeed == updates.initialFeed, "empty build setting uses shipped default")
        let valid: [(String, String)] = [
            ("http://127.0.0.1:49177/appcast.xml", "http://127.0.0.1:49177/appcast.xml"),
            ("HTTP://LOCALHOST:80/appcast.xml", "http://localhost/appcast.xml"),
            ("http://[::1]:49177/appcast.xml", "http://[::1]:49177/appcast.xml"),
            ("HTTPS://UPDATES.EXAMPLE.COM:443/stable/appcast.xml", "https://updates.example.com/stable/appcast.xml"),
            ("https://updates.example.com:8443/appcast.xml", "https://updates.example.com:8443/appcast.xml"),
        ]
        for (input, expected) in valid {
            expect(try updates.feedURL(input).absoluteString == expected, "update URL normalization")
        }
        for value in [
            "https://", "https://:443", "http://127.0.0.1:0/appcast.xml", "http://127.0.0.1:65536/appcast.xml",
            "http://127.0.0.1:/appcast.xml", "https://example.com:/appcast.xml",
            "http://192.0.2.1/appcast.xml", "http://updates.example.com/appcast.xml",
            "http://localhost.evil.example/appcast.xml", "http://127.1/appcast.xml", "http://2130706433/appcast.xml",
            "http://[::ffff:127.0.0.1]/appcast.xml", "https://user:secret@example.com/appcast.xml",
            "http://127.0.0.1@appcast.example/appcast.xml", "https://@example.com/appcast.xml",
            "file:///tmp/appcast.xml", "ftp://localhost/appcast.xml", "/appcast.xml",
            "https://example.com/appcast.xml?secret=value", "https://example.com/appcast.xml#fragment",
        ] {
            rejects("unsafe update URL") { _ = try updates.feedURL(value) }
        }
        do {
            defaults.set("immutable-key-sentinel", forKey: "SUPublicEDKey")
            let explicit = try updates.feedURL("https://updates.example.com/appcast.xml")
            updates.rememberFeed(explicit)
            expect(UpdateConfiguration(defaults: defaults, bundledFeed: nil).initialFeed == explicit.absoluteString,
                   "explicit update source survives new configuration instance")
            let next = UpdateConfiguration(defaults: defaults, bundledFeed: "https://future.example.com/appcast.xml")
            expect(next.initialFeed == explicit.absoluteString, "later default does not replace explicit source")
            next.resetFeed()
            expect(next.initialFeed == "https://future.example.com/appcast.xml", "reset selects current bundle default")
            expect(defaults.string(forKey: "updateFeedURLOverride") == nil, "reset removes override")
            expect(defaults.string(forKey: "SUPublicEDKey") == "immutable-key-sentinel", "URL changes never replace public key")
            updates.rememberFeed(try updates.feedURL(updates.bundledFeed))
            expect(defaults.string(forKey: "updateFeedURLOverride") == nil, "saving default is not an override")
            configuration.rememberServer(try configuration.serverURL("https://api.example.com"))
            expect(AppConfiguration().initialServer == "https://api.example.com", "API override survives new instance")
            configuration.resetServer()
            expect(AppConfiguration().initialServer == AppConfiguration.localServer, "API reset uses built-in default")
            expect(defaults.string(forKey: "serviceURLOverride") == nil, "API reset removes override")
        } catch { failures += 1; print("FAIL: persistence setup") }
        let sparkleDomain = "ComponentTestSparkleDomain"
        let atsError = NSError(domain: NSURLErrorDomain, code: -1022)
        let wrappedATS = NSError(domain: sparkleDomain, code: 2001, userInfo: [NSUnderlyingErrorKey: atsError])
        expect(UpdateFailureReason.classify(wrappedATS, sparkleDomain: sparkleDomain) == .transportRejected,
               "underlying real ATS code is classified")
        expect(UpdateFailureReason.classify(NSError(domain: NSURLErrorDomain, code: -1003), sparkleDomain: sparkleDomain) == .other(-1003),
               "DNS failure is never an ATS rejection")
        expect(UpdateFailureReason.classify(NSError(domain: "WrongDomain", code: -1022), sparkleDomain: sparkleDomain) == .other(-1022),
               "ATS classification requires Foundation domain")
        expect(UpdateFailureReason.classify(NSError(domain: UpdateFailureReason.policyDomain, code: 1), sparkleDomain: sparkleDomain) == .sourceRejected,
               "source policy has an explicit domain and code")
        expect(UpdateFailureReason.classify(NSError(domain: sparkleDomain, code: 2001), sparkleDomain: sparkleDomain) == .other(2001),
               "download failure is not signature rejection")
        expect(UpdateFailureReason.classify(NSError(domain: sparkleDomain, code: 3001), sparkleDomain: sparkleDomain) == .signatureRejected([3001]),
               "Sparkle signature error remains specific")
        expect(UpdateFailureReason.classify(NSError(domain: sparkleDomain, code: 1001), sparkleDomain: sparkleDomain) == .noUpdate,
               "no update is distinct from failed source")
        defaults.removePersistentDomain(forName: suiteName)
        print("Swift endpoint component checks: \(assertions) assertions, \(failures) failures")
        exit(failures == 0 ? 0 : 1)
    }
}
