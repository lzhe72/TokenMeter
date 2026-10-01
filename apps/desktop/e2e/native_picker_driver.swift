// Fixed macOS Accessibility driver for the real NSOpenPanel used by TM-002.
// It never substitutes dialog.showOpenDialog's return value or reads files.
import AppKit
import ApplicationServices
import CryptoKit
import Foundation

struct DriverError: Error, CustomStringConvertible {
    let description: String
    init(_ message: String) { description = message }
}

func parse(_ args: [String]) throws -> (String, [String: String]) {
    guard let operation = args.first, ["probe", "select", "cancel"].contains(operation) else {
        throw DriverError("Expected probe, select or cancel")
    }
    var options: [String: String] = [:]
    var index = 1
    while index < args.count {
        guard args[index].hasPrefix("--"), index + 1 < args.count else { throw DriverError("Invalid option") }
        let key = String(args[index].dropFirst(2))
        guard !options.keys.contains(key) else { throw DriverError("Duplicate option") }
        options[key] = args[index + 1]
        index += 2
    }
    return (operation, options)
}

func trusted() -> Bool {
    AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: false] as CFDictionary)
}

func attribute(_ element: AXUIElement, _ name: CFString) -> AnyObject? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name, &value) == .success else { return nil }
    return value
}

func string(_ element: AXUIElement, _ name: CFString) -> String {
    attribute(element, name) as? String ?? ""
}

func children(_ element: AXUIElement) -> [AXUIElement] {
    attribute(element, kAXChildrenAttribute as CFString) as? [AXUIElement] ?? []
}

func descendants(_ root: AXUIElement, maxDepth: Int = 12) -> [AXUIElement] {
    var queue: [(AXUIElement, Int)] = [(root, 0)]
    var result: [AXUIElement] = []
    while !queue.isEmpty {
        let (element, depth) = queue.removeFirst()
        result.append(element)
        if depth < maxDepth { queue.append(contentsOf: children(element).map { ($0, depth + 1) }) }
    }
    return result
}

let chooserConfirmTitles: Set<String> = ["Choose", "Open", "Select", "选择", "打开"]
let chooserCancelTitles: Set<String> = ["Cancel", "取消"]

func chooserWitness(_ element: AXUIElement) -> String? {
    let titles = Set(descendants(element)
        .filter { string($0, kAXRoleAttribute as CFString) == "AXButton" }
        .map { string($0, kAXTitleAttribute as CFString).trimmingCharacters(in: .whitespacesAndNewlines) })
    guard !titles.isDisjoint(with: chooserCancelTitles),
          let confirmation = chooserConfirmTitles.sorted().first(where: { titles.contains($0) }) else { return nil }
    return confirmation
}

func panel(_ application: AXUIElement) -> AXUIElement? {
    let windows = attribute(application, kAXWindowsAttribute as CFString) as? [AXUIElement] ?? []
    for window in windows {
        for item in descendants(window, maxDepth: 4) {
            let role = string(item, kAXRoleAttribute as CFString)
            if role == "AXSheet" || role == "AXDialog" {
                if chooserWitness(item) != nil { return item }
            }
        }
    }
    return nil
}

func waitPanel(_ application: AXUIElement, seconds: TimeInterval = 15) throws -> AXUIElement {
    let deadline = Date().addingTimeInterval(seconds)
    repeat {
        if let found = panel(application) { return found }
        Thread.sleep(forTimeInterval: 0.1)
    } while Date() < deadline
    throw DriverError("No owned native chooser sheet was visible")
}

func press(_ element: AXUIElement, titles: Set<String>) throws -> String {
    let buttons = descendants(element).filter { string($0, kAXRoleAttribute as CFString) == "AXButton" }
    for button in buttons {
        let title = string(button, kAXTitleAttribute as CFString).trimmingCharacters(in: .whitespacesAndNewlines)
        if titles.contains(title), AXUIElementPerformAction(button, kAXPressAction as CFString) == .success {
            return title
        }
    }
    throw DriverError("Native chooser required button was unavailable")
}

func key(_ code: CGKeyCode, modifiers: CGEventFlags = []) throws {
    guard let down = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: false) else {
        throw DriverError("Could not create a native keyboard event")
    }
    down.flags = modifiers
    up.flags = modifiers
    down.post(tap: .cghidEventTap)
    up.post(tap: .cghidEventTap)
}

func goToFolder(_ path: String, application: AXUIElement) throws {
    // The fixed keyboard shortcut opens NSOpenPanel's own Go To Folder sheet.
    try key(5, modifiers: [.maskCommand, .maskShift])
    let deadline = Date().addingTimeInterval(10)
    var textField: AXUIElement?
    repeat {
        if let candidate = attribute(application, kAXFocusedUIElementAttribute as CFString) {
            let focused = candidate as! AXUIElement
            if !["AXTextField", "AXComboBox"].contains(string(focused, kAXRoleAttribute as CFString)) {
                Thread.sleep(forTimeInterval: 0.1)
                continue
            }
            textField = focused
            break
        }
        Thread.sleep(forTimeInterval: 0.1)
    } while Date() < deadline
    guard let target = textField,
          AXUIElementSetAttributeValue(target, kAXValueAttribute as CFString, path as CFString) == .success else {
        throw DriverError("Native Go To Folder field could not be set")
    }
    try key(36) // Return commits the path in the actual system sheet.
    Thread.sleep(forTimeInterval: 0.35)
}

func writeEvent(_ path: String, _ value: [String: Any]) throws {
    let destination = URL(fileURLWithPath: path)
    if FileManager.default.fileExists(atPath: destination.path) { throw DriverError("Event path already exists") }
    let data = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    guard FileManager.default.createFile(atPath: destination.path, contents: data + Data([10]),
                                         attributes: [.posixPermissions: 0o600]) else {
        throw DriverError("Could not create private picker event")
    }
}

func main() throws {
    let (operation, options) = try parse(Array(CommandLine.arguments.dropFirst()))
    if operation == "probe" {
        let result: [String: Any] = ["trusted": trusted(), "prompted": false,
                                     "platform": "macos_ax", "operation": "probe"]
        let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
        print(String(data: data, encoding: .utf8)!)
        return
    }
    guard let pidText = options["pid"], let pid = Int32(pidText), pid > 0,
          let eventPath = options["event"] else { throw DriverError("Owned PID and private event path are required") }
    guard trusted() else { throw DriverError("Accessibility permission is unavailable; no UI action performed") }
    guard let running = NSRunningApplication(processIdentifier: pid),
          running.activate(options: []) else {
        throw DriverError("Owned App could not be activated for native panel input")
    }
    let application = AXUIElementCreateApplication(pid)
    let initial = try waitPanel(application)
    let role = string(initial, kAXRoleAttribute as CFString)
    guard let confirmWitness = chooserWitness(initial) else {
        throw DriverError("Visible sheet is not a native directory chooser")
    }
    var button = ""
    var label = ""
    var pathHash = ""
    if operation == "cancel" {
        button = try press(initial, titles: chooserCancelTitles)
    } else {
        guard let path = options["path"], path.hasPrefix("/"), !path.contains("\0"),
              FileManager.default.fileExists(atPath: path) else {
            throw DriverError("Owned selection directory is missing")
        }
        let resolved = URL(fileURLWithPath: path).resolvingSymlinksInPath().path
        guard resolved == path else { throw DriverError("Selection path contains a symlink") }
        label = URL(fileURLWithPath: path).lastPathComponent
        pathHash = SHA256.hash(data: Data(path.utf8)).map { String(format: "%02x", $0) }.joined()
        try goToFolder(path, application: application)
        let chooser = try waitPanel(application)
        button = try press(chooser, titles: chooserConfirmTitles)
    }
    try writeEvent(eventPath, ["operation": operation, "owner_pid": pid, "panel_role": role,
                               "chooser_confirm_button": confirmWitness,
                               "native_button": button, "selection_label": label,
                               "selection_path_sha256": pathHash,
                               "completed_at": ISO8601DateFormatter().string(from: Date()),
                               "real_ax_action": true])
}

do { try main() }
catch {
    fputs("native_picker_driver: \(error)\n", stderr)
    exit(75)
}
