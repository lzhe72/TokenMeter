import {randomUUID} from 'node:crypto';
import {isAbsolute, normalize} from 'node:path';
import type {ConfirmedSource, SourceIdentity, SourceStore, SourceTool, StoredSource} from './source-store.ts';
import type {SourceAuditEvent} from './source-helper.ts';
import type {SourceAuditEvent as SourceAuditRecord} from './source-audit.ts';
import {canonicalOrigin, ClientError} from './validation.ts';

export type SourceAccessIdentity = {origin: string; accountId: string | null; verified: boolean; epoch: number};
export type SourceCandidate = {relativeName: string; size: number; mtimeMs: number; fileIdentityDigest: string};
export type PublicSourceCandidate = Pick<SourceCandidate, 'relativeName' | 'size' | 'mtimeMs'>;
export type SourcePreview = {candidates: SourceCandidate[]; incomplete: boolean;
  reason?: 'candidate_limit'|'entry_limit'|'depth_limit'|'timeout'; inspectedEntries: number};
export type SourcePage = {candidates: Array<SourceCandidate & {candidateToken: string}>;
  complete: boolean; incompleteReason?: 'time_slice'};
export type SourceHelperLike = {
  rootIdentity: {dev: string; ino: string};
  preview(): Promise<SourcePreview>;
  beginCandidateScan(): Promise<SourcePage>;
  nextCandidatePage(): Promise<SourcePage>;
  readCandidateChunk(token: string, offset: number, maxBytes: number): Promise<Buffer>;
  close(): void;
};
export type SourceView = {
  confirmed: null | {sourceId: string; status: 'confirmed_enabled'|'confirmed_paused'|'needs_reselect';
    collectAllowed: boolean; syncIntent: boolean; reason?: string};
  pending: null | {selectionId: string; tool: SourceTool; label: string;
    candidates: PublicSourceCandidate[]; incomplete: boolean; reason?: string};
  candidates: PublicSourceCandidate[]; incomplete: boolean; reason?: string;
};
export type SourceAccessSnapshot = Record<SourceTool, SourceView>;
export type SourceAccessAudit = SourceAuditRecord;
export type SourceAccessOptions = {
  store: SourceStore;
  getIdentity(): SourceAccessIdentity;
  chooseDirectory(tool: SourceTool): Promise<{canceled: boolean; rootPath?: string}>;
  openHelper(path: string, options?: {expectedRoot?: {dev: string; ino: string};
    onAudit?: (event: SourceAuditEvent) => void}): Promise<SourceHelperLike>;
  onChange(): void;
  onAudit?(event: SourceAccessAudit): void;
};

type Context = SourceIdentity & {epoch: number; key: string};
type Ticket = {tool: SourceTool; key: string; generation: number};
type Pending = {selectionId: string; rootPath: string; label: string; helper: SourceHelperLike;
  candidates: SourceCandidate[]; incomplete: boolean; reason?: string};
type Slot = {record: StoredSource; revokeId: string | null; pending: Pending | null;
  candidates: SourceCandidate[]; incomplete: boolean; reason?: string; generation: number;
  active: Set<SourceHelperLike>; scans: Set<string>; replacement: Promise<void> | null; updating: boolean};
type Scan = {tool: SourceTool; sourceId: string; helper: SourceHelperLike; ticket: Ticket; complete: boolean};

const TOOLS: SourceTool[] = ['codex', 'claude_code'];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TOKEN = /^[a-f0-9]{32}$/;
const ROOT_ERRORS = new Set(['root_changed', 'access_denied', 'unsafe_root', 'source_unavailable']);
const PREVIEW_REASONS = new Set(['candidate_limit', 'entry_limit', 'depth_limit', 'timeout']);
function emptySlot(): Slot {
  return {record: {kind: 'none'}, revokeId: null, pending: null, candidates: [], incomplete: false,
    generation: 0, active: new Set(), scans: new Set(), replacement: null, updating: false};
}
function error(code: string): ClientError { return new ClientError(code, '来源操作未完成'); }
function codeOf(value: unknown): string {
  const code = (value as {code?: unknown})?.code;
  return typeof code === 'string' && /^[a-z_]{3,60}$/.test(code) ? code : 'source_unavailable';
}
function candidate(value: SourceCandidate): SourceCandidate {
  if (!value || typeof value.relativeName !== 'string' || !value.relativeName ||
      value.relativeName.length > 4096 || value.relativeName.startsWith('/') ||
      value.relativeName.includes('\\') || /[\x00-\x1f\x7f]/.test(value.relativeName) ||
      value.relativeName.split('/').some(part => !part || part === '.' || part === '..') ||
      !Number.isSafeInteger(value.size) || value.size < 0 || !Number.isFinite(value.mtimeMs) ||
      typeof value.fileIdentityDigest !== 'string' || !/^[a-f0-9]{1,128}$/.test(value.fileIdentityDigest))
    throw error('invalid_source_metadata');
  return {relativeName: value.relativeName, size: value.size, mtimeMs: value.mtimeMs,
    fileIdentityDigest: value.fileIdentityDigest};
}
function previewValue(value: SourcePreview): SourcePreview {
  if (!value || !Array.isArray(value.candidates) || value.candidates.length > 1000 ||
      typeof value.incomplete !== 'boolean' || !Number.isSafeInteger(value.inspectedEntries) ||
      value.inspectedEntries < 0 || value.inspectedEntries > 5000 ||
      (value.reason !== undefined && !PREVIEW_REASONS.has(value.reason))) throw error('invalid_source_metadata');
  return {candidates: value.candidates.map(candidate), incomplete: value.incomplete,
    inspectedEntries: value.inspectedEntries, ...(value.reason ? {reason: value.reason} : {})};
}
function pageValue(value: SourcePage): SourcePage {
  if (!value || !Array.isArray(value.candidates) || value.candidates.length > 256 ||
      typeof value.complete !== 'boolean' ||
      (value.incompleteReason !== undefined && (value.incompleteReason !== 'time_slice' || value.complete)))
    throw error('invalid_source_metadata');
  const candidates = value.candidates.map(item => {
    if (!TOKEN.test(item?.candidateToken)) throw error('invalid_source_metadata');
    return {...candidate(item), candidateToken: item.candidateToken};
  });
  return {candidates, complete: value.complete,
    ...(value.incompleteReason ? {incompleteReason: value.incompleteReason} : {})};
}

export class SourceAccess {
  readonly #options: SourceAccessOptions;
  readonly #slots: Record<SourceTool, Slot> = {codex: emptySlot(), claude_code: emptySlot()};
  readonly #scans = new Map<string, Scan>();
  #context: Context | null = null;
  #key: string | null = null;
  #restore: Promise<void> = Promise.resolve();
  #disposed = false;
  constructor(options: SourceAccessOptions) { this.#options = options; }
  #identity(): Context | null {
    if (this.#disposed) return null;
    try {
      const value = this.#options.getIdentity();
      if (!value?.verified || typeof value.accountId !== 'string' || !value.accountId ||
          value.accountId.length > 128 || !Number.isSafeInteger(value.epoch) || value.epoch < 0)
        return null;
      const origin = canonicalOrigin(value.origin);
      return {origin, accountId: value.accountId, epoch: value.epoch,
        key: JSON.stringify([origin, value.accountId, value.epoch])};
    } catch { return null; }
  }
  #audit(event: SourceAccessAudit): void { try { this.#options.onAudit?.(event); } catch {} }
  #close(helper: SourceHelperLike): void { try { helper.close(); } catch {} }
  #assert(ticket: Ticket): void {
    if (this.#disposed || this.#key !== ticket.key || this.#identity()?.key !== ticket.key ||
        this.#slots[ticket.tool].generation !== ticket.generation) throw error('source_operation_stale');
  }
  #ticket(tool: SourceTool): Ticket {
    if (!TOOLS.includes(tool)) throw error('invalid_source_tool');
    const current = this.#identity();
    if (!current || current.key !== this.#key || !this.#context) throw error('invalid_session');
    return {tool, key: current.key, generation: this.#slots[tool].generation};
  }
  #dropPending(tool: SourceTool): void {
    const value = this.#slots[tool];
    if (value.pending) {
      this.#close(value.pending.helper);
      this.#audit({operation: 'cancel', decision: 'denied', reason: 'selection_invalidated',
        tool, generation: value.generation});
    }
    value.pending = null;
  }
  #abort(tool: SourceTool): void {
    const value = this.#slots[tool];
    const active = value.active.size > 0 || value.scans.size > 0;
    value.generation++;
    for (const helper of value.active) this.#close(helper);
    value.active.clear();
    for (const id of value.scans) {
      const scan = this.#scans.get(id);
      if (scan) this.#close(scan.helper);
      this.#scans.delete(id);
    }
    value.scans.clear(); value.candidates = []; value.incomplete = false; value.reason = undefined;
    if (active) this.#audit({operation: 'cancel', decision: 'denied', reason: 'capability_invalidated',
      tool, generation: value.generation});
  }
  #reset(tool: SourceTool): void {
    this.#abort(tool); this.#dropPending(tool);
    const value = this.#slots[tool]; value.record = {kind: 'none'};
    value.revokeId = null; value.replacement = null; value.updating = false;
  }
  #open(path: string, tool: SourceTool, _sourceId: string | null,
        expectedRoot?: {dev: string; ino: string}): Promise<SourceHelperLike> {
    const generation = this.#slots[tool].generation;
    return this.#options.openHelper(path, {expectedRoot, onAudit: event => {
      const root = event.rootIdentity;
      this.#audit({operation: event.action === 'enumerated' ? 'enumerate' :
        event.action === 'rejected' ? 'reject' : event.action,
        decision: event.action === 'rejected' ? 'denied' : 'allowed',
        tool, generation, rootDev: root.dev, rootIno: root.ino,
        ...('relativeName' in event ? {relativeName: event.relativeName} : {})});
    }});
  }
  async syncIdentity(): Promise<void> {
    const current = this.#identity();
    if ((current?.key ?? null) === this.#key) return this.#restore;
    this.#context = current; this.#key = current?.key ?? null;
    for (const tool of TOOLS) this.#reset(tool);
    if (!current) { this.#restore = Promise.resolve(); this.#options.onChange(); return; }
    const key = current.key;
    this.#restore = Promise.all(TOOLS.map(async tool => {
      const stored = await this.#options.store.load(current, tool);
      if (this.#key !== key || this.#identity()?.key !== key) return;
      let record: StoredSource = stored;
      if (stored.kind === 'needs_reselect' && stored.sourceId &&
          ['key_unavailable', 'decrypt_failed', 'corrupt_locator'].includes(stored.reason)) {
        try {
          const state = this.#options.store.markNeedsReselect(current, tool, stored.sourceId, 'source_unavailable');
          record = state === 'removed' ? {kind: 'none'} :
            {kind: 'needs_reselect', sourceId: stored.sourceId, reason: 'source_unavailable'};
        } catch {
          record = {kind: 'needs_reselect', sourceId: stored.sourceId,
            reason: 'source_invalidation_failed'};
        }
      }
      if (stored.kind === 'ready' && stored.source.collectAllowed) {
        try {
          const helper = await this.#open(stored.source.rootPath, tool, stored.source.sourceId,
            {dev: stored.source.rootDev, ino: stored.source.rootIno});
          this.#close(helper);
        } catch (cause) {
          if (this.#key !== key || this.#identity()?.key !== key) return;
          const reason = ROOT_ERRORS.has(codeOf(cause)) ? codeOf(cause) : 'source_unavailable';
          try {
            const state = this.#options.store.markNeedsReselect(current, tool, stored.source.sourceId, reason);
            record = state === 'removed' ? {kind: 'none'} :
              {kind: 'needs_reselect', reason, sourceId: stored.source.sourceId};
          } catch { record = {kind: 'needs_reselect', reason: 'source_invalidation_failed',
            sourceId: stored.source.sourceId}; }
        }
      }
      if (this.#key !== key || this.#identity()?.key !== key) return;
      this.#slots[tool].record = record;
      this.#slots[tool].revokeId = record.kind === 'needs_reselect' && !record.sourceId ? randomUUID() : null;
      this.#options.onChange();
    })).then(() => undefined);
    this.#options.onChange();
    return this.#restore;
  }
  snapshot(): SourceAccessSnapshot {
    const view = (tool: SourceTool): SourceView => {
      const value = this.#slots[tool]; const record = value.record;
      const confirmed = record.kind === 'ready' ? {sourceId: record.source.sourceId,
        status: record.source.collectAllowed ? 'confirmed_enabled' as const : 'confirmed_paused' as const,
        collectAllowed: record.source.collectAllowed, syncIntent: record.source.syncIntent} :
        record.kind === 'needs_reselect' ? {sourceId: record.sourceId ?? value.revokeId ?? '',
          status: 'needs_reselect' as const, collectAllowed: false, syncIntent: false, reason: record.reason} : null;
      const publicCandidate = (item: SourceCandidate): PublicSourceCandidate => ({
        relativeName: item.relativeName, size: item.size, mtimeMs: item.mtimeMs});
      const pending = value.pending ? {selectionId: value.pending.selectionId, tool, label: value.pending.label,
        candidates: value.pending.candidates.map(publicCandidate), incomplete: value.pending.incomplete,
        ...(value.pending.reason ? {reason: value.pending.reason} : {})} : null;
      return {confirmed, pending, candidates: value.candidates.map(publicCandidate),
        incomplete: value.incomplete, ...(value.reason ? {reason: value.reason} : {})};
    };
    return {codex: view('codex'), claude_code: view('claude_code')};
  }
  async choose(tool: SourceTool): Promise<void> {
    await this.syncIdentity(); const ticket = this.#ticket(tool);
    this.#audit({operation: 'picker_open', decision: 'allowed', tool,
      generation: ticket.generation});
    let picked: {canceled: boolean; rootPath?: string};
    try { picked = await this.#options.chooseDirectory(tool); }
    catch { this.#audit({operation: 'picker_result', decision: 'denied', reason: 'error', tool,
      generation: ticket.generation}); this.#assert(ticket); throw error('picker_failed'); }
    try { this.#assert(ticket); }
    catch (cause) {
      this.#audit({operation: 'picker_result', decision: 'denied', reason: 'stale', tool,
        generation: ticket.generation});
      throw cause;
    }
    if (!picked || typeof picked.canceled !== 'boolean') {
      this.#audit({operation: 'picker_result', decision: 'denied', reason: 'invalid_selection',
        tool, generation: ticket.generation});
      throw error('invalid_selection');
    }
    if (picked.canceled) {
      this.#audit({operation: 'picker_result', decision: 'denied', reason: 'canceled', tool,
        generation: ticket.generation});
      return;
    }
    if (typeof picked.rootPath !== 'string' || !isAbsolute(picked.rootPath) ||
        picked.rootPath.length > 4096 || picked.rootPath.includes('\0')) {
      this.#audit({operation: 'picker_result', decision: 'denied', reason: 'invalid_selection',
        tool, generation: ticket.generation});
      throw error('invalid_selection');
    }
    const path = normalize(picked.rootPath);
    let helper: SourceHelperLike;
    try { helper = await this.#open(path, tool, null); }
    catch (cause) {
      this.#assert(ticket);
      this.#audit({operation: 'picker_result', decision: 'denied', reason: codeOf(cause),
        tool, generation: ticket.generation});
      throw error(codeOf(cause));
    }
    try { this.#assert(ticket); } catch (cause) { this.#close(helper); throw cause; }
    this.#dropPending(tool);
    this.#slots[tool].pending = {selectionId: randomUUID(), rootPath: path, helper,
      label: '已选择目录',
      candidates: [], incomplete: false};
    this.#audit({operation: 'picker_result', decision: 'allowed', reason: 'selected', tool,
      generation: ticket.generation,
      rootDev: helper.rootIdentity.dev, rootIno: helper.rootIdentity.ino});
    this.#options.onChange();
  }
  #pending(selectionId: string): {tool: SourceTool; pending: Pending; ticket: Ticket} {
    if (typeof selectionId !== 'string' || !UUID.test(selectionId)) throw error('invalid_selection');
    const tool = TOOLS.find(item => this.#slots[item].pending?.selectionId === selectionId);
    if (!tool) throw error('invalid_selection');
    return {tool, pending: this.#slots[tool].pending!, ticket: this.#ticket(tool)};
  }
  async preview(selectionId: string): Promise<void> {
    await this.syncIdentity();
    const {tool, pending, ticket} = this.#pending(selectionId);
    let result: SourcePreview;
    try { result = previewValue(await pending.helper.preview()); }
    catch (cause) { this.#assert(ticket); throw error(codeOf(cause)); }
    this.#assert(ticket);
    if (this.#slots[tool].pending !== pending) throw error('source_operation_stale');
    pending.candidates = result.candidates; pending.incomplete = result.incomplete;
    pending.reason = result.reason === 'timeout' ? 'time_limit' : result.reason;
    this.#audit({operation: 'preview_complete', decision: 'allowed', tool,
      generation: ticket.generation, rootDev: pending.helper.rootIdentity.dev,
      rootIno: pending.helper.rootIdentity.ino, inspectedEntries: result.inspectedEntries,
      candidateCount: result.candidates.length, ...(pending.reason ? {reason: pending.reason} : {})});
    this.#options.onChange();
  }
  async #latch(tool: SourceTool, source: ConfirmedSource, reason: string): Promise<void> {
    const context = this.#context;
    this.#abort(tool);
    const value = this.#slots[tool];
    value.record = {kind: 'needs_reselect', sourceId: source.sourceId, reason};
    this.#options.onChange();
    if (!context || this.#identity()?.key !== context.key) throw error('source_operation_stale');
    try {
      const state = this.#options.store.markNeedsReselect(context, tool, source.sourceId,
        ROOT_ERRORS.has(reason) ? reason : 'source_unavailable');
      if (state === 'removed') value.record = {kind: 'none'};
      this.#options.onChange();
    } catch {
      value.record = {kind: 'needs_reselect', sourceId: source.sourceId,
        reason: 'source_invalidation_failed'};
      this.#options.onChange(); throw error('source_invalidation_failed');
    }
  }
  async confirm(selectionId: string, collectAllowed: boolean, syncIntent: boolean): Promise<void> {
    if (typeof collectAllowed !== 'boolean' || typeof syncIntent !== 'boolean') throw error('invalid_source_consent');
    await this.syncIdentity();
    const {tool, pending, ticket} = this.#pending(selectionId);
    const value = this.#slots[tool];
    if (value.replacement) throw error('operation_busy');
    let verifier: SourceHelperLike;
    try { verifier = await this.#open(pending.rootPath, tool, null, pending.helper.rootIdentity); }
    catch (cause) { this.#assert(ticket); throw error(codeOf(cause)); }
    this.#close(verifier); this.#assert(ticket);
    if (value.pending !== pending || !this.#context) throw error('source_operation_stale');
    const source: ConfirmedSource = {sourceId: randomUUID(), tool, rootPath: pending.rootPath,
      rootDev: pending.helper.rootIdentity.dev, rootIno: pending.helper.rootIdentity.ino,
      collectAllowed, syncIntent};
    let finish!: () => void;
    value.replacement = new Promise(resolve => { finish = resolve; });
    try {
      await this.#options.store.commit(this.#context, source,
        () => this.#key === ticket.key && value.generation === ticket.generation &&
          this.#identity()?.key === ticket.key && value.pending === pending);
      this.#assert(ticket);
      this.#abort(tool); this.#dropPending(tool);
      value.record = {kind: 'ready', source}; value.revokeId = null;
      this.#options.onChange();
    } catch (cause) {
      if (codeOf(cause) === 'source_key_unavailable' && value.record.kind === 'ready')
        await this.#latch(tool, value.record.source, 'source_unavailable');
      throw cause;
    } finally { value.replacement = null; finish(); }
  }
  #toolFor(sourceId: string): SourceTool {
    if (typeof sourceId !== 'string' || !UUID.test(sourceId)) throw error('invalid_source_id');
    const tool = TOOLS.find(item => {
      const value = this.#slots[item]; const record = value.record;
      return record.kind === 'ready' ? record.source.sourceId === sourceId :
        record.kind === 'needs_reselect' && (record.sourceId ?? value.revokeId) === sourceId;
    });
    if (!tool) throw error('source_access_denied');
    return tool;
  }
  async #currentSource(tool: SourceTool, sourceId: string, ticket: Ticket): Promise<ConfirmedSource> {
    this.#assert(ticket);
    const value = this.#slots[tool];
    if (value.updating || value.record.kind !== 'ready' || value.record.source.sourceId !== sourceId ||
        !value.record.source.collectAllowed) throw error('source_access_denied');
    const source = value.record.source;
    const stored = await this.#options.store.load(this.#context!, tool);
    this.#assert(ticket);
    if (stored.kind !== 'ready') {
      if (stored.kind === 'needs_reselect') await this.#latch(tool, source, 'source_unavailable');
      else { this.#abort(tool); value.record = {kind: 'none'}; this.#options.onChange(); }
      throw error('source_access_denied');
    }
    if (stored.source.sourceId !== source.sourceId || stored.source.rootDev !== source.rootDev ||
        stored.source.rootIno !== source.rootIno || stored.source.rootPath !== source.rootPath ||
        stored.source.collectAllowed !== source.collectAllowed || stored.source.syncIntent !== source.syncIntent) {
      this.#abort(tool); value.record = stored; this.#options.onChange();
      throw error('source_operation_stale');
    }
    return source;
  }
  async #openConfirmed(tool: SourceTool, sourceId: string, ticket: Ticket): Promise<SourceHelperLike> {
    const source = await this.#currentSource(tool, sourceId, ticket);
    let helper: SourceHelperLike;
    try { helper = await this.#open(source.rootPath, tool, sourceId,
      {dev: source.rootDev, ino: source.rootIno}); }
    catch (cause) {
      this.#assert(ticket);
      if (ROOT_ERRORS.has(codeOf(cause))) await this.#latch(tool, source, codeOf(cause));
      throw error(codeOf(cause));
    }
    try { this.#assert(ticket); } catch (cause) { this.#close(helper); throw cause; }
    this.#slots[tool].active.add(helper);
    return helper;
  }
  async #accessError(tool: SourceTool, sourceId: string, ticket: Ticket, cause: unknown): Promise<never> {
    this.#assert(ticket);
    const code = codeOf(cause); const value = this.#slots[tool];
    if (ROOT_ERRORS.has(code) && value.record.kind === 'ready' && value.record.source.sourceId === sourceId)
      await this.#latch(tool, value.record.source, code);
    else if (code === 'tree_changed') {
      this.#abort(tool); value.incomplete = true; value.reason = 'tree_changed'; this.#options.onChange();
    }
    throw error(code);
  }
  async refresh(sourceId: string): Promise<void> {
    await this.syncIdentity(); const tool = this.#toolFor(sourceId);
    const ticket = this.#ticket(tool);
    const helper = await this.#openConfirmed(tool, sourceId, ticket);
    try {
      const result = previewValue(await helper.preview());
      const replacement = this.#slots[tool].replacement;
      if (replacement) await replacement;
      this.#assert(ticket);
      const value = this.#slots[tool];
      if (value.record.kind !== 'ready' || value.record.source.sourceId !== sourceId) throw error('source_operation_stale');
      value.candidates = result.candidates; value.incomplete = result.incomplete;
      value.reason = result.reason === 'timeout' ? 'time_limit' : result.reason;
      this.#audit({operation: 'preview_complete', decision: 'allowed', tool,
        generation: ticket.generation, rootDev: helper.rootIdentity.dev,
        rootIno: helper.rootIdentity.ino, inspectedEntries: result.inspectedEntries,
        candidateCount: result.candidates.length, ...(value.reason ? {reason: value.reason} : {})});
      this.#options.onChange();
    } catch (cause) { await this.#accessError(tool, sourceId, ticket, cause); }
    finally { this.#slots[tool].active.delete(helper); this.#close(helper); }
  }
  async updateConsent(sourceId: string, collectAllowed: boolean, syncIntent: boolean): Promise<void> {
    if (typeof collectAllowed !== 'boolean' || typeof syncIntent !== 'boolean') throw error('invalid_source_consent');
    await this.syncIdentity(); const tool = this.#toolFor(sourceId);
    const value = this.#slots[tool];
    if (value.record.kind !== 'ready' || value.replacement || value.updating) throw error('source_access_denied');
    const previous = value.record.source;
    this.#abort(tool);
    if (!collectAllowed) this.#dropPending(tool);
    const ticket = this.#ticket(tool);
    value.updating = true;
    try {
      const stored = await this.#options.store.load(this.#context!, tool);
      this.#assert(ticket);
      if (stored.kind !== 'ready') {
        if (stored.kind === 'needs_reselect') await this.#latch(tool, previous, 'source_unavailable');
        throw error('source_access_denied');
      }
      if (stored.source.sourceId !== sourceId ||
          stored.source.rootPath !== previous.rootPath || stored.source.rootDev !== previous.rootDev ||
          stored.source.rootIno !== previous.rootIno ||
          stored.source.collectAllowed !== previous.collectAllowed || stored.source.syncIntent !== previous.syncIntent)
        throw error('source_operation_stale');
      if (collectAllowed) {
        let helper: SourceHelperLike;
        try { helper = await this.#open(previous.rootPath, tool, sourceId,
          {dev: previous.rootDev, ino: previous.rootIno}); }
        catch (cause) {
          this.#assert(ticket);
          if (ROOT_ERRORS.has(codeOf(cause))) await this.#latch(tool, previous, codeOf(cause));
          throw error(codeOf(cause));
        }
        this.#close(helper); this.#assert(ticket);
      }
      const updated = {...previous, collectAllowed, syncIntent};
      await this.#options.store.commit(this.#context!, updated,
        () => this.#key === ticket.key && value.generation === ticket.generation &&
          this.#identity()?.key === ticket.key && value.record.kind === 'ready' &&
          value.record.source.sourceId === sourceId);
      this.#assert(ticket);
      value.record = {kind: 'ready', source: updated}; this.#options.onChange();
    } catch (cause) {
      if (codeOf(cause) === 'source_key_unavailable' && value.record.kind === 'ready')
        await this.#latch(tool, value.record.source, 'source_unavailable');
      throw cause;
    } finally { value.updating = false; }
  }
  async revoke(sourceId: string): Promise<void> {
    await this.syncIdentity(); const tool = this.#toolFor(sourceId);
    const context = this.#context!; const value = this.#slots[tool];
    this.#abort(tool); this.#dropPending(tool);
    value.record = {kind: 'none'}; value.revokeId = null; value.replacement = null;
    this.#options.onChange();
    try { this.#options.store.revoke(context, tool); }
    catch {
      try {
        const state = this.#options.store.markNeedsReselect(context, tool, sourceId, 'source_unavailable');
        if (state === 'latched') value.record = {kind: 'needs_reselect', sourceId, reason: 'source_unavailable'};
      } catch {
        value.record = {kind: 'needs_reselect', sourceId, reason: 'source_invalidation_failed'};
        this.#options.onChange(); throw error('source_invalidation_failed');
      }
      this.#options.onChange(); throw error('source_unavailable');
    }
  }
  async beginCandidateScan(sourceId: string): Promise<SourcePage & {scanId: string}> {
    await this.syncIdentity(); const tool = this.#toolFor(sourceId); const ticket = this.#ticket(tool);
    const helper = await this.#openConfirmed(tool, sourceId, ticket);
    try {
      const page = pageValue(await helper.beginCandidateScan()); this.#assert(ticket);
      const scanId = randomUUID();
      this.#scans.set(scanId, {tool, sourceId, helper, ticket, complete: page.complete});
      this.#slots[tool].scans.add(scanId);
      return {...page, scanId};
    } catch (cause) {
      this.#slots[tool].active.delete(helper); this.#close(helper);
      return this.#accessError(tool, sourceId, ticket, cause);
    }
  }
  #scan(scanId: string): Scan {
    if (typeof scanId !== 'string' || !UUID.test(scanId)) throw error('invalid_scan');
    const scan = this.#scans.get(scanId);
    if (!scan) throw error('invalid_scan');
    return scan;
  }
  async nextCandidatePage(scanId: string): Promise<SourcePage> {
    const scan = this.#scan(scanId); this.#assert(scan.ticket);
    if (scan.complete) throw error('invalid_scan');
    await this.#currentSource(scan.tool, scan.sourceId, scan.ticket);
    try {
      const page = pageValue(await scan.helper.nextCandidatePage());
      this.#assert(scan.ticket); scan.complete = page.complete;
      return page;
    } catch (cause) { this.cancelScan(scanId); return this.#accessError(scan.tool, scan.sourceId, scan.ticket, cause); }
  }
  async readCandidateChunk(scanId: string, candidateToken: string, offset: number,
                           maxBytes: number): Promise<Buffer> {
    const scan = this.#scan(scanId); this.#assert(scan.ticket);
    if (!TOKEN.test(candidateToken) || !Number.isSafeInteger(offset) || offset < 0 ||
        !Number.isSafeInteger(maxBytes) || maxBytes < 1 || maxBytes > 65536) throw error('invalid_source_read');
    await this.#currentSource(scan.tool, scan.sourceId, scan.ticket);
    try {
      const chunk = await scan.helper.readCandidateChunk(candidateToken, offset, maxBytes);
      this.#assert(scan.ticket);
      if (!Buffer.isBuffer(chunk) || chunk.length > maxBytes) throw error('invalid_source_read');
      return chunk;
    } catch (cause) { this.cancelScan(scanId); return this.#accessError(scan.tool, scan.sourceId, scan.ticket, cause); }
  }
  cancelScan(scanId: string): void {
    const scan = this.#scans.get(scanId); if (!scan) return;
    this.#scans.delete(scanId); this.#slots[scan.tool].scans.delete(scanId);
    this.#slots[scan.tool].active.delete(scan.helper); this.#close(scan.helper);
    this.#audit({operation: 'cancel', decision: 'denied', reason: 'scan_closed',
      tool: scan.tool, generation: scan.ticket.generation});
  }
  dispose(): void {
    if (this.#disposed) return;
    this.#disposed = true; for (const tool of TOOLS) this.#reset(tool);
    this.#context = null; this.#key = null;
  }
}
