import Foundation
import Combine
import Sparkle

final class UpdateController: NSObject, ObservableObject, SPUUpdaterDelegate {
    @Published private(set) var canCheck = false
    @Published private(set) var status = "更新服务尚未配置"
    @Published private(set) var feed: String
    @Published private(set) var sessionInProgress = false
    private let configuration: UpdateConfiguration
    private let hasValidPublicKey: Bool
    private var controller: SPUStandardUpdaterController?
    private var observation: NSKeyValueObservation?
    private var sessionObservation: NSKeyValueObservation?

    override init() {
        let configuration = UpdateConfiguration()
        self.configuration = configuration
        feed = configuration.initialFeed
        let key = Bundle.main.object(forInfoDictionaryKey: "SUPublicEDKey") as? String ?? ""
        hasValidPublicKey = Data(base64Encoded: key)?.count == 32
        super.init()
        configureUpdater()
    }

    var defaultFeed: String { configuration.bundledFeed }
    var canConfigure: Bool { !sessionInProgress }

    func validateFeedConfiguration(_ input: String) throws -> URL {
        guard controller?.updater.sessionInProgress != true else {
            throw APIError(code: "update_configuration_locked", message: "请在本次更新检查或安装结束后修改更新地址")
        }
        return try configuration.feedURL(input)
    }

    func saveFeedConfiguration(_ url: URL) {
        configuration.rememberFeed(url)
        feed = url.absoluteString
        configureUpdater()
    }

    func restoreDefaultFeed() throws {
        let url = try validateFeedConfiguration(defaultFeed)
        configuration.resetFeed()
        feed = url.absoluteString
        configureUpdater()
    }

    private func configureUpdater() {
        guard hasValidPublicKey else {
            canCheck = false
            status = "更新签名公钥尚未配置"
            return
        }
        guard (try? configuration.feedURL(feed)) != nil else {
            canCheck = false
            status = "更新地址无效 (invalid_update_source)"
            return
        }
        if let controller {
            controller.updater.resetUpdateCycle()
            status = "可检查新版本"
            return
        }
        let updater = SPUStandardUpdaterController(startingUpdater: false, updaterDelegate: self, userDriverDelegate: nil)
        controller = updater
        observation = updater.updater.observe(\.canCheckForUpdates, options: [.initial, .new]) { [weak self] _, change in
            DispatchQueue.main.async { self?.canCheck = change.newValue ?? false }
        }
        sessionObservation = updater.updater.observe(\.sessionInProgress, options: [.initial, .new]) { [weak self] _, change in
            DispatchQueue.main.async { self?.sessionInProgress = change.newValue ?? false }
        }
        updater.startUpdater()
        status = "可检查新版本"
    }

    func feedURLString(for updater: SPUUpdater) -> String? { try? configuration.feedURL(feed).absoluteString }

    func updater(_ updater: SPUUpdater, mayPerform updateCheck: SPUUpdateCheck) throws {
        _ = try configuration.feedURL(feed)
    }

    func updater(_ updater: SPUUpdater, shouldProceedWithUpdate item: SUAppcastItem, updateCheck: SPUUpdateCheck) throws {
        guard let url = item.fileURL, (try? configuration.feedURL(url.absoluteString)) != nil else {
            throw NSError(domain: UpdateFailureReason.policyDomain, code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "更新包地址不符合安全要求"])
        }
    }

    func check() {
        guard canCheck, let controller else { return }
        status = "正在检查更新"
        controller.checkForUpdates(nil)
    }

    func updater(_ updater: SPUUpdater, didAbortWithError error: Error) {
        // Sparkle 2.10 SUErrors.h: 3001 signature, 3002 validation, 2001 download.
        // Inspect only domain/code, never local paths or URLs in the error text.
        let status = UpdateFailureReason.classify(error, sparkleDomain: SUSparkleErrorDomain).message
        DispatchQueue.main.async { self.status = status }
    }
}
