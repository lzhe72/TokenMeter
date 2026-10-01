// TM002: exact-item metadata probe. Run only in a separate standard macOS test account.
// Electron 44.5.1 derives "<Browser Name> Safe Storage" / "<Browser Name>" for
// KeychainPassword. Async safeStorage must still be verified against the final App.
import Foundation
import Security
import CryptoKit
import LocalAuthentication
import Darwin

private struct ProbeError: Error {
    let reason: String
    init(_ reason: String) { self.reason = reason }
}

private struct OwnerState: Codable {
    let schema_version: Int
    let run_digest: String
    let uid: UInt32
    let user_digest: String
    let profile_digest: String
    let service_digest: String
    let account_digest: String
    let dmg_digest: String
    let app_signature_digest: String
    let first_call_absent: Bool
    let expect_created: Bool
    var stage: String
    var item_ref_digest: String?
    var acl_digest: String?
}

private struct Report: Codable {
    let schema_version: Int
    let mode: String
    let state: String
    let reason: String
    let uid: UInt32
    let service_digest: String
    let account_digest: String
    let dmg_digest: String
    let app_signature_digest: String
    let item_ref_digest: String?
    let first_call_absent: Bool
    let expected_item_created: Bool
    let item_created: Bool
    let exact_cleanup_ready: Bool
    let acl_bound_to_app: Bool
}

private struct Options {
    let mode: String
    let profile: String
    let state: String
    let output: String
    let app: String
    let dmg: String
    let runID: String
    let testUser: String
    let excludedUID: UInt32
    let expectCreated: Bool
}

private struct Signature {
    let digest: String
    let trustedData: Data
}

private struct ObservedItem {
    let ref: SecKeychainItem
    let persistentDigest: String
}

private struct DecisionInput {
    var itemCount = 0
    var attributesMatch = false
    var signatureValid = false
    var aclBound = false
    var ownerMatches = false
    var itemMatches = false
    var expectCreated = true
}

private func decision(_ mode: String, _ input: DecisionInput) -> String? {
    if !input.signatureValid { return "signature_unproven" }
    if mode == "preflight" {
        return input.itemCount == 0 ? nil : "preexisting_item"
    }
    if !input.ownerMatches { return "owner_unproven" }
    if !input.expectCreated {
        return input.itemCount == 0 ? nil : "unexpected_item"
    }
    if input.itemCount == 0 { return "item_missing" }
    if input.itemCount != 1 { return "duplicate_exact_items" }
    if !input.attributesMatch { return "item_attributes_mismatch" }
    if !input.aclBound { return "acl_unproven" }
    if mode == "cleanup" && !input.itemMatches { return "item_changed" }
    return nil
}

private func sha(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}
private func sha(_ text: String) -> String { sha(Data(text.utf8)) }
private func trustedAppsBound(_ entries: [Data]?, expected: Data) -> Bool {
    entries?.count == 1 && entries?[0] == expected
}
private func checked(_ condition: Bool, _ reason: String) throws {
    if !condition { throw ProbeError(reason) }
}

private func parse(_ args: [String]) throws -> Options {
    try checked(args.count == 20, "invalid_arguments")
    var values: [String: String] = [:]
    for index in stride(from: 0, to: args.count, by: 2) {
        let key = args[index]
        try checked(key.hasPrefix("--") && values[key] == nil, "invalid_arguments")
        values[key] = args[index + 1]
    }
    let keys: Set<String> = ["--mode", "--profile", "--state", "--output", "--app", "--dmg",
                             "--run-id", "--test-user", "--excluded-uid", "--expect-created"]
    try checked(Set(values.keys) == keys, "invalid_arguments")
    let mode = values["--mode"]!
    try checked(["preflight", "postflight", "cleanup"].contains(mode), "invalid_mode")
    let runID = values["--run-id"]!
    try checked(runID.range(of: "^[A-Za-z0-9_-]{8,100}$", options: .regularExpression) != nil,
                "invalid_run_id")
    let testUser = values["--test-user"]!
    try checked(testUser.range(of: "^[a-z_][a-z0-9_-]{2,63}$", options: .regularExpression) != nil,
                "invalid_test_user")
    guard let excludedUID = UInt32(values["--excluded-uid"]!), excludedUID != 0 else {
        throw ProbeError("invalid_excluded_uid")
    }
    let expected = values["--expect-created"]!
    try checked(expected == "true" || expected == "false", "invalid_expect_created")
    return Options(mode: mode, profile: values["--profile"]!, state: values["--state"]!,
                   output: values["--output"]!, app: values["--app"]!, dmg: values["--dmg"]!,
                   runID: runID, testUser: testUser, excludedUID: excludedUID,
                   expectCreated: expected == "true")
}

private func assertSeparateStandardAccount(_ options: Options) throws -> UInt32 {
    let uid = getuid()
    try checked(uid != 0 && uid != options.excludedUID, "test_account_not_separate")
    guard let user = getpwuid(uid) else { throw ProbeError("test_account_unknown") }
    try checked(String(cString: user.pointee.pw_name) == options.testUser, "test_account_mismatch")
    let count = getgroups(0, nil)
    try checked(count >= 0, "test_account_groups_unknown")
    var groups = [gid_t](repeating: 0, count: Int(count))
    let got = groups.withUnsafeMutableBufferPointer { buffer in
        getgroups(count, buffer.baseAddress)
    }
    try checked(got == count, "test_account_groups_unknown")
    if let admin = getgrnam("admin") {
        try checked(!groups.contains(admin.pointee.gr_gid), "test_account_is_admin")
    } else { throw ProbeError("test_account_groups_unknown") }
    return uid
}

private func checkedPath(_ path: String) throws -> String {
    try checked(path.hasPrefix("/") && !path.contains("\0") &&
                URL(fileURLWithPath: path).standardizedFileURL.path == path, "invalid_path")
    try checked(URL(fileURLWithPath: path).resolvingSymlinksInPath().path == path,
                "linked_path")
    return path
}

private func privateDirectory(_ path: String, uid: UInt32) throws {
    let path = try checkedPath(path)
    var statValue = stat()
    try checked(lstat(path, &statValue) == 0, "private_directory_missing")
    try checked((statValue.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR) &&
                statValue.st_uid == uid && (statValue.st_mode & 0o777) == 0o700,
                "unsafe_private_directory")
}

private func privateFile(_ path: String, uid: UInt32) throws {
    let path = try checkedPath(path)
    var statValue = stat()
    try checked(lstat(path, &statValue) == 0, "owner_state_missing")
    try checked((statValue.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) &&
                statValue.st_uid == uid && statValue.st_nlink == 1 &&
                (statValue.st_mode & 0o777) == 0o600, "unsafe_owner_state")
}

private func pathAbsent(_ path: String) throws -> Bool {
    _ = try checkedPath(path)
    var statValue = stat()
    if lstat(path, &statValue) == 0 { return false }
    try checked(errno == ENOENT, "path_check_failed")
    return true
}

private func writeExclusive(_ path: String, _ data: Data) throws {
    let fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o600)
    try checked(fd >= 0, "private_write_failed")
    defer { close(fd) }
    try data.withUnsafeBytes { raw in
        var offset = 0
        while offset < raw.count {
            let written = write(fd, raw.baseAddress!.advanced(by: offset), raw.count - offset)
            try checked(written > 0, "private_write_failed")
            offset += written
        }
    }
    try checked(fsync(fd) == 0, "private_write_failed")
}

private func writeState(_ path: String, _ state: OwnerState, replace: Bool) throws {
    let data = try JSONEncoder().encode(state)
    if !replace { try writeExclusive(path, data); return }
    let temp = path + ".tmp-" + UUID().uuidString
    try writeExclusive(temp, data)
    if rename(temp, path) != 0 {
        unlink(temp)
        throw ProbeError("owner_state_write_failed")
    }
}

private func readState(_ path: String, uid: UInt32) throws -> OwnerState {
    try privateFile(path, uid: uid)
    let data = try Data(contentsOf: URL(fileURLWithPath: path))
    try checked(data.count > 0 && data.count <= 8192, "owner_state_invalid")
    guard let state = try? JSONDecoder().decode(OwnerState.self, from: data),
          state.schema_version == 1 else { throw ProbeError("owner_state_invalid") }
    return state
}

private func digestFile(_ path: String) throws -> String {
    _ = try checkedPath(path)
    var statValue = stat()
    try checked(lstat(path, &statValue) == 0 &&
                (statValue.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) &&
                statValue.st_nlink == 1, "dmg_unavailable")
    let handle = try FileHandle(forReadingFrom: URL(fileURLWithPath: path))
    defer { try? handle.close() }
    var hasher = SHA256()
    while true {
        let data = try handle.read(upToCount: 1024 * 1024) ?? Data()
        if data.isEmpty { break }
        hasher.update(data: data)
    }
    return hasher.finalize().map { String(format: "%02x", $0) }.joined()
}

private func signature(_ appPath: String) throws -> Signature {
    _ = try checkedPath(appPath)
    try checked(appPath.hasSuffix(".app"), "invalid_app")
    let appURL = URL(fileURLWithPath: appPath)
    guard let executable = Bundle(url: appURL)?.executableURL,
          executable.path.hasPrefix(appPath + "/Contents/MacOS/") else {
        throw ProbeError("app_executable_unproven")
    }
    var code: SecStaticCode?
    try checked(SecStaticCodeCreateWithPath(appURL as CFURL, [], &code) == errSecSuccess &&
                code != nil, "signature_unproven")
    let validationFlags = SecCSFlags(rawValue: kSecCSCheckAllArchitectures |
                                           kSecCSCheckNestedCode | kSecCSStrictValidate)
    try checked(SecStaticCodeCheckValidity(code!, validationFlags, nil) == errSecSuccess,
                "signature_unproven")
    var requirement: SecRequirement?
    try checked(SecCodeCopyDesignatedRequirement(code!, [], &requirement) == errSecSuccess &&
                requirement != nil, "signature_unproven")
    var requirementData: CFData?
    try checked(SecRequirementCopyData(requirement!, [], &requirementData) == errSecSuccess &&
                requirementData != nil, "signature_unproven")
    var info: CFDictionary?
    try checked(SecCodeCopySigningInformation(code!, SecCSFlags(rawValue: kSecCSSigningInformation),
                                              &info) == errSecSuccess && info != nil,
                "signature_unproven")
    let details = info! as NSDictionary
    guard let cdhash = details[kSecCodeInfoUnique] as? Data,
          let identifier = details[kSecCodeInfoIdentifier] as? String,
          let flags = details[kSecCodeInfoFlags] as? NSNumber,
          let certificates = details[kSecCodeInfoCertificates] as? NSArray,
          !identifier.isEmpty && certificates.count > 0 &&
          (flags.uint32Value & SecCodeSignatureFlags.adhoc.rawValue) == 0 else {
        throw ProbeError("signature_unproven")
    }
    var trusted: SecTrustedApplication?
    let createStatus = executable.path.withCString { SecTrustedApplicationCreateFromPath($0, &trusted) }
    try checked(createStatus == errSecSuccess && trusted != nil, "trusted_app_unproven")
    var opaque: CFData?
    try checked(SecTrustedApplicationCopyData(trusted!, &opaque) == errSecSuccess &&
                opaque != nil, "trusted_app_unproven")
    let trustedData = opaque! as Data
    try checked(!trustedData.isEmpty, "trusted_app_unproven")
    return Signature(digest: sha(cdhash + (requirementData! as Data) + Data(identifier.utf8)),
                     trustedData: trustedData)
}

private func exactItems(service: String, account: String) throws -> [ObservedItem] {
    let context = LAContext()
    context.interactionNotAllowed = true
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: account,
        kSecAttrSynchronizable as String: kSecAttrSynchronizableAny,
        kSecMatchLimit as String: kSecMatchLimitAll,
        kSecReturnRef as String: true,
        kSecReturnAttributes as String: true,
        kSecReturnPersistentRef as String: true,
        kSecUseAuthenticationContext as String: context,
    ]
    var result: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &result)
    if status == errSecItemNotFound { return [] }
    try checked(status == errSecSuccess, "exact_query_failed")
    guard let rows = result as? [[String: Any]] else { throw ProbeError("exact_result_invalid") }
    return try rows.map { row in
        guard let foundService = row[kSecAttrService as String] as? String,
              let foundAccount = row[kSecAttrAccount as String] as? String,
              foundService == service, foundAccount == account,
              let rawItem = row[kSecValueRef as String],
              let persistent = row[kSecValuePersistentRef as String] as? Data,
              !persistent.isEmpty else { throw ProbeError("item_attributes_mismatch") }
        try checked((row[kSecAttrSynchronizable as String] as? Bool) != true,
                    "synchronized_item_unowned")
        try checked(CFGetTypeID(rawItem as CFTypeRef) == SecKeychainItemGetTypeID(),
                    "item_attributes_mismatch")
        let item = rawItem as! SecKeychainItem
        return ObservedItem(ref: item, persistentDigest: sha(persistent))
    }
}

private func aclDigest(_ item: ObservedItem, expectedTrustedData: Data) throws -> String {
    var access: SecAccess?
    try checked(SecKeychainItemCopyAccess(item.ref, &access) == errSecSuccess &&
                access != nil, "acl_unproven")
    var list: CFArray?
    try checked(SecAccessCopyACLList(access!, &list) == errSecSuccess && list != nil,
                "acl_unproven")
    guard let entries = list as? [SecACL], !entries.isEmpty else { throw ProbeError("acl_unproven") }
    let readTags: Set<String> = [kSecACLAuthorizationAny, kSecACLAuthorizationDecrypt,
                                 kSecACLAuthorizationExportClear, kSecACLAuthorizationKeychainItemRead]
        .map { $0 as String }.reduce(into: Set<String>()) { $0.insert($1) }
    var readEntries = 0
    var components: [String] = []
    for acl in entries {
        guard let authorizations = SecACLCopyAuthorizations(acl) as? [String],
              !authorizations.isEmpty else { throw ProbeError("acl_unproven") }
        if authorizations.contains(kSecACLAuthorizationPartitionID as String) {
            throw ProbeError("acl_partition_unproven")
        }
        if readTags.isDisjoint(with: authorizations) { continue }
        readEntries += 1
        var apps: CFArray?
        var description: CFString?
        var selector = SecKeychainPromptSelector()
        try checked(SecACLCopyContents(acl, &apps, &description, &selector) == errSecSuccess,
                    "acl_unproven")
        // nil means any application can use this ACL; empty means no trusted application.
        guard let trustedApps = apps as? [SecTrustedApplication] else {
            throw ProbeError("acl_unbounded")
        }
        var trustedData: [Data] = []
        for application in trustedApps {
            var opaque: CFData?
            try checked(SecTrustedApplicationCopyData(application, &opaque) == errSecSuccess &&
                        opaque != nil, "acl_unproven")
            trustedData.append(opaque! as Data)
        }
        try checked(trustedAppsBound(trustedData, expected: expectedTrustedData),
                    trustedData.count == 1 ? "acl_wrong_application" : "acl_unbounded")
        components.append(sha(authorizations.sorted().joined(separator: ",") + ":" +
                              sha(trustedData[0])))
    }
    try checked(readEntries > 0, "acl_read_boundary_missing")
    return sha(components.sorted().joined(separator: ":"))
}

private func ownerMatches(_ state: OwnerState, _ options: Options, uid: UInt32,
                          service: String, account: String, dmgDigest: String,
                          signatureDigest: String) -> Bool {
    state.schema_version == 1 && state.run_digest == sha(options.runID) && state.uid == uid &&
    state.user_digest == sha(options.testUser) && state.profile_digest == sha(options.profile) &&
    state.service_digest == sha(service) && state.account_digest == sha(account) &&
    state.dmg_digest == dmgDigest && state.app_signature_digest == signatureDigest &&
    state.first_call_absent && state.expect_created == options.expectCreated
}

private func selfTest() throws {
    let base = DecisionInput(itemCount: 1, attributesMatch: true, signatureValid: true,
                             aclBound: true, ownerMatches: true, itemMatches: true)
    var cases: [(String, String, DecisionInput)] = []
    var value = base; value.itemCount = 1; cases.append(("preexisting_item", "preflight", value))
    value = base; value.itemCount = 0; cases.append(("missing_postflight_item", "postflight", value))
    value = base; value.itemCount = 2; cases.append(("duplicate_exact_items", "postflight", value))
    value = base; value.attributesMatch = false; cases.append(("wrong_item_attributes", "postflight", value))
    value = base; value.signatureValid = false; cases.append(("unsigned_app", "postflight", value))
    value = base; value.aclBound = false; cases.append(("unbounded_acl", "postflight", value))
    value = base; value.aclBound = false; cases.append(("wrong_acl_application", "postflight", value))
    value = base; value.ownerMatches = false; cases.append(("wrong_owner", "cleanup", value))
    value = base; value.itemMatches = false; cases.append(("changed_item_before_cleanup", "cleanup", value))
    value = base; value.expectCreated = false; cases.append(("unexpected_item_for_absent_case", "postflight", value))
    let expected = Data([0x10, 0x20])
    try checked(!trustedAppsBound(nil, expected: expected) &&
                !trustedAppsBound([], expected: expected) &&
                !trustedAppsBound([Data([0x10, 0x21])], expected: expected) &&
                !trustedAppsBound([expected, expected], expected: expected) &&
                trustedAppsBound([expected], expected: expected), "self_test_failed")
    for (_, mode, input) in cases { try checked(decision(mode, input) != nil, "self_test_failed") }
    try checked(decision("preflight", DecisionInput(itemCount: 0, signatureValid: true)) == nil,
                "self_test_failed")
    try checked(decision("postflight", base) == nil && decision("cleanup", base) == nil,
                "self_test_failed")
    let absent = DecisionInput(itemCount: 0, signatureValid: true, ownerMatches: true,
                               expectCreated: false)
    try checked(decision("postflight", absent) == nil && decision("cleanup", absent) == nil,
                "self_test_failed")
    let output: [String: Any] = ["schema_version": 1, "mode": "self_test", "state": "PASS",
                                 "blocked_cases": cases.map { $0.0 }]
    let data = try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
    print(String(decoding: data, as: UTF8.self))
}

private func run(_ options: Options) throws {
    // This account check precedes every Security.framework Keychain call.
    let uid = try assertSeparateStandardAccount(options)
    try privateDirectory(options.profile, uid: uid)
    try privateDirectory((options.state as NSString).deletingLastPathComponent, uid: uid)
    try privateDirectory((options.output as NSString).deletingLastPathComponent, uid: uid)
    _ = try checkedPath(options.state)
    _ = try checkedPath(options.output)
    let outputAbsent = try pathAbsent(options.output)
    try checked(options.state != options.output && outputAbsent,
                "output_already_exists")
    let appName = "TokenMeter-Test-" + String(sha(options.profile).prefix(24))
    let service = appName + " Safe Storage"
    let account = appName
    let dmgDigest = try digestFile(options.dmg)
    let signed = try signature(options.app)
    try checked(SecKeychainSetUserInteractionAllowed(false) == errSecSuccess,
                "noninteractive_keychain_unavailable")
    let absentState = try pathAbsent(options.state)
    if options.mode == "preflight" {
        try checked(absentState, "owner_state_already_exists")
    } else { try checked(!absentState, "owner_state_missing") }

    var reason = "ok"
    var firstAbsent = false
    var itemCreated = false
    var cleanupReady = false
    var aclBound = false
    var itemDigest: String?
    var state = options.mode == "preflight" ? nil : try readState(options.state, uid: uid)
    do {
        if let owner = state {
            try checked(ownerMatches(owner, options, uid: uid, service: service, account: account,
                                     dmgDigest: dmgDigest, signatureDigest: signed.digest),
                        "owner_unproven")
            let expectedStage = options.mode == "postflight" ? "preflight" :
                (options.expectCreated ? "postflight" : "postflight_absent")
            try checked(owner.stage == expectedStage, "owner_stage_invalid")
        }
        let observed = try exactItems(service: service, account: account)
        let ownerOK = state != nil
        var input = DecisionInput(itemCount: observed.count, attributesMatch: true,
                                  signatureValid: true, aclBound: false,
                                  ownerMatches: ownerOK, itemMatches: false,
                                  expectCreated: options.expectCreated)
        if let initial = decision(options.mode, input),
           (options.mode == "preflight" || !["acl_unproven", "item_changed"].contains(initial)) {
            throw ProbeError(initial)
        }
        if options.mode == "preflight" {
            firstAbsent = true
            let initial = OwnerState(schema_version: 1, run_digest: sha(options.runID), uid: uid,
                                     user_digest: sha(options.testUser), profile_digest: sha(options.profile),
                                     service_digest: sha(service), account_digest: sha(account),
                                     dmg_digest: dmgDigest, app_signature_digest: signed.digest,
                                     first_call_absent: true, expect_created: options.expectCreated,
                                     stage: "preflight")
            try writeState(options.state, initial, replace: false)
        } else if !options.expectCreated {
            if let rejected = decision(options.mode, input) { throw ProbeError(rejected) }
            state!.stage = options.mode == "postflight" ? "postflight_absent" : "cleaned"
            try writeState(options.state, state!, replace: true)
            firstAbsent = true
        } else {
            guard let item = observed.first else { throw ProbeError("item_missing") }
            itemDigest = item.persistentDigest
            let acl = try aclDigest(item, expectedTrustedData: signed.trustedData)
            aclBound = true
            input.aclBound = true
            input.itemMatches = state?.item_ref_digest == item.persistentDigest &&
                                state?.acl_digest == acl && state?.stage == "postflight"
            if let rejected = decision(options.mode, input) { throw ProbeError(rejected) }
            if options.mode == "postflight" {
                state!.stage = "postflight"
                state!.item_ref_digest = item.persistentDigest
                state!.acl_digest = acl
                try writeState(options.state, state!, replace: true)
                firstAbsent = true; itemCreated = true; cleanupReady = true
            } else {
                // Delete only the one transient reference whose exact service/account,
                // persistent identity, ACL, signature, owner and prior absence matched.
                let deleteQuery: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                    kSecAttrService as String: service, kSecAttrAccount as String: account,
                    kSecMatchItemList as String: [item.ref],
                    kSecUseAuthenticationContext as String: {
                        let context = LAContext(); context.interactionNotAllowed = true; return context
                    }()]
                try checked(SecItemDelete(deleteQuery as CFDictionary) == errSecSuccess,
                            "exact_delete_failed")
                try checked(try exactItems(service: service, account: account).isEmpty,
                            "exact_delete_unverified")
                state!.stage = "cleaned"
                try writeState(options.state, state!, replace: true)
                firstAbsent = true; itemCreated = true
            }
        }
    } catch let failure as ProbeError {
        reason = failure.reason
    }
    let report = Report(schema_version: 1, mode: options.mode,
                        state: reason == "ok" ? "PASS" : "BLOCKED", reason: reason, uid: uid,
                        service_digest: sha(service), account_digest: sha(account),
                        dmg_digest: dmgDigest, app_signature_digest: signed.digest,
                        item_ref_digest: itemDigest, first_call_absent: firstAbsent,
                        expected_item_created: options.expectCreated,
                        item_created: itemCreated, exact_cleanup_ready: cleanupReady,
                        acl_bound_to_app: aclBound)
    let data = try JSONEncoder().encode(report)
    try writeExclusive(options.output, data + Data([0x0a]))
    print(String(decoding: data, as: UTF8.self))
    if reason != "ok" { exit(2) }
}

if CommandLine.arguments.count == 2 && CommandLine.arguments[1] == "--self-test" {
    do { try selfTest() } catch { fputs("self_test_failed\n", stderr); exit(3) }
} else {
    do {
        let options = try parse(Array(CommandLine.arguments.dropFirst()))
        try run(options)
    } catch let failure as ProbeError {
        let report: [String: Any] = ["schema_version": 1, "state": "BLOCKED", "reason": failure.reason]
        if let data = try? JSONSerialization.data(withJSONObject: report, options: [.sortedKeys]) {
            print(String(decoding: data, as: UTF8.self))
        }
        exit(2)
    } catch {
        print("{\"schema_version\":1,\"state\":\"BLOCKED\",\"reason\":\"probe_error\"}")
        exit(2)
    }
}
