import Foundation
import Combine
import Sparkle

final class UpdateController: NSObject, ObservableObject, SPUUpdaterDelegate {
    @Published private(set) var canCheck = false
    @Published private(set) var status = "更新服务尚未配置"
    private var controller: SPUStandardUpdaterController?
    private var observation: NSKeyValueObservation?

    override init() {
        super.init()
        guard let feed = Bundle.main.object(forInfoDictionaryKey: "SUFeedURL") as? String,
              let url = URL(string: feed), url.scheme == "https", url.host != nil,
              let key = Bundle.main.object(forInfoDictionaryKey: "SUPublicEDKey") as? String,
              let bytes = Data(base64Encoded: key), bytes.count == 32 else { return }
        let updater = SPUStandardUpdaterController(startingUpdater: false, updaterDelegate: self, userDriverDelegate: nil)
        controller = updater
        observation = updater.updater.observe(\.canCheckForUpdates, options: [.initial, .new]) { [weak self] _, change in
            DispatchQueue.main.async { self?.canCheck = change.newValue ?? false }
        }
        updater.startUpdater()
        status = "可检查新版本"
    }

    func check() {
        guard canCheck, let controller else { return }
        status = "正在检查更新"
        controller.checkForUpdates(nil)
    }

    func updater(_ updater: SPUUpdater, didAbortWithError error: Error) {
        // Sparkle 2.10 SUErrors.h: 3001 signature, 3002 validation, 2001 download.
        // Inspect only domain/code, never local paths or URLs in the error text.
        var current: NSError? = error as NSError
        var codes: [Int] = []
        for _ in 0..<8 {
            guard let value = current else { break }
            if value.domain == SUSparkleErrorDomain { codes.append(value.code) }
            current = value.userInfo[NSUnderlyingErrorKey] as? NSError
        }
        let status: String
        if codes.contains(3001) || codes.contains(3002) {
            status = "更新包验证失败 (update_signature_rejected: \(codes.map(String.init).joined(separator: ",")))"
        } else if codes.contains(1001) {
            status = "当前已是最新版本"
        } else {
            status = "更新失败 (update_failed: \((error as NSError).code))"
        }
        DispatchQueue.main.async { self.status = status }
    }
}
