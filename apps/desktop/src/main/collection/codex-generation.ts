import type {UsageStore} from './usage-store.ts';
import {scanCodexIncremental} from './codex-incremental.ts';

type Stage = {sourceKey: string; fileIdentity: string; bytes: Buffer};
type Options = {store: UsageStore; principalKey: string; secret: Buffer; rootKey: string;
  guard: () => void; onCancel: () => void};

/** Initial fixed-test binding. Full generation commit follows its red test. */
export class CodexGeneration {
  readonly #options: Options;
  readonly #files = new Map<string, ReturnType<typeof scanCodexIncremental>>();
  #complete = false;
  #cancelled = false;
  constructor(options: Options) { this.#options = options; }
  stage(input: Stage): void {
    if (this.#cancelled) throw new Error('scan_cancelled');
    const cursor = this.#options.store.loadCursor(this.#options.principalKey, input.sourceKey, this.#options.secret);
    this.#files.set(input.sourceKey, scanCodexIncremental(input.bytes, cursor, input.fileIdentity, this.#options.secret));
  }
  pageComplete(complete: boolean): void { this.#complete = complete; }
  cancel(): void { this.#cancelled = true; this.#files.clear(); this.#options.onCancel(); }
  finish(): boolean {
    if (this.#cancelled || !this.#complete) return false;
    throw new Error('generation_commit_not_implemented');
  }
}
