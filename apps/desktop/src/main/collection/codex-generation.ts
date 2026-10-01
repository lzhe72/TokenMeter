import type {UsageStore} from './usage-store.ts';
import {scanCodexIncremental} from './codex-incremental.ts';

type Stage = {sourceKey: string; fileIdentity: string; bytes: Buffer};
type Options = {store: UsageStore; principalKey: string; secret: Buffer; rootKey: string;
  guard: () => void; onCancel: () => void};

/** Stages a complete candidate generation in memory until its final page is verified. */
export class CodexGeneration {
  readonly #options: Options;
  readonly #files = new Map<string, {sourceKey: string; fileIdentity: string;
    scan: ReturnType<typeof scanCodexIncremental>}>();
  #complete = false;
  #cancelled = false;
  #finished = false;
  constructor(options: Options) { this.#options = options; }
  stage(input: Stage): void {
    if (this.#cancelled || this.#complete || this.#finished || this.#files.has(input.sourceKey)) throw new Error('invalid_scan_stage');
    const cursor = this.#options.store.loadCursor(this.#options.principalKey, input.sourceKey, this.#options.secret);
    this.#files.set(input.sourceKey, {sourceKey: input.sourceKey, fileIdentity: input.fileIdentity,
      scan: scanCodexIncremental(input.bytes, cursor, input.fileIdentity, this.#options.secret)});
  }
  pageComplete(complete: boolean): void {
    if (this.#cancelled || this.#complete || this.#finished) throw new Error('invalid_scan_page');
    this.#complete = complete;
  }
  cancel(): void {
    if (this.#cancelled) return;
    this.#cancelled = true; this.#files.clear(); this.#options.onCancel();
  }
  finish(): boolean {
    if (this.#cancelled || this.#finished || !this.#complete) return false;
    this.#options.guard();
    const files = [...this.#files.values()];
    this.#options.store.commitScanBatch({principalKey: this.#options.principalKey,
      secret: this.#options.secret, source: 'codex', rootKey: this.#options.rootKey,
      files: files.map(({sourceKey, fileIdentity, scan}) => ({sourceKey, fileIdentity,
        committedByteOffset: scan.committedByteOffset, prefixMac: scan.prefixMac,
        events: scan.events, diagnostics: scan.diagnostics})),
      coverage: {missingBefore: files.some(file => file.scan.missingBefore), scanIncomplete: false},
      guard: this.#options.guard});
    this.#files.clear();
    this.#finished = true;
    return true;
  }
}
