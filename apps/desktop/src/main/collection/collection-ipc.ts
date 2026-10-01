import type {CodexRuntime} from './codex-runtime.ts';
import {runCodexCollection} from './codex-runtime.ts';
import {codexRootKey} from './codex-collector.ts';

export type CollectionEvent = {sender: object; senderFrame: {url: string}};
export type CollectionHandlerPorts = {
  runtime(): CodexRuntime;
  mainSender(): object;
  mainFrame(): object;
  mainUrl: string;
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function createCollectionHandler(ports: CollectionHandlerPorts) {
  return async (event: CollectionEvent, method: unknown, input?: unknown): Promise<unknown> => {
    if (!event || event.sender !== ports.mainSender() || event.senderFrame !== ports.mainFrame() ||
        event.senderFrame.url !== ports.mainUrl) throw new Error('ipc_sender_rejected');
    if (method !== 'collection:getState' && method !== 'collection:refresh')
      throw new Error('invalid_collection_method');
    if (method === 'collection:getState' && input !== undefined)
      throw new Error('invalid_collection_input');
    if (method === 'collection:refresh' && (!input || typeof input !== 'object' || Array.isArray(input) ||
        Object.keys(input).length !== 1 || !Object.hasOwn(input, 'sourceId') ||
        typeof (input as {sourceId?: unknown}).sourceId !== 'string' ||
        !UUID.test((input as {sourceId: string}).sourceId)))
      throw new Error('invalid_collection_input');

    const runtime = ports.runtime();
    const identity = runtime.getIdentity();
    if (!identity.verified || typeof identity.accountId !== 'string' || !identity.accountId)
      throw new Error('invalid_principal');
    const confirmed = runtime.access.snapshot().codex.confirmed;
    if (method === 'collection:refresh') {
      const sourceId = (input as {sourceId: string}).sourceId;
      if (confirmed?.sourceId !== sourceId || confirmed.status !== 'confirmed_enabled' ||
          !confirmed.collectAllowed) throw new Error('source_access_denied');
      await runCodexCollection(sourceId, runtime);
    }
    const current = runtime.getIdentity();
    if (!current.verified || current.origin !== identity.origin || current.accountId !== identity.accountId)
      throw new Error('invalid_principal');
    const principal = runtime.profile.principalKey(identity.origin, identity.accountId);
    const view = runtime.access.snapshot().codex.confirmed;
    const rootKey = view?.sourceId && UUID.test(view.sourceId)
      ? codexRootKey(runtime.profile.secret, view.sourceId) : null;
    const stored = runtime.profile.store.codexState(principal, rootKey);
    const enabled = view?.status === 'confirmed_enabled' && view.collectAllowed;
    return {status: !stored.usage ? 'unverified' : enabled ? 'available' : 'unavailable',
      usage: stored.usage,
      coverage: enabled ? stored.coverage : {...stored.coverage, complete: false, scanIncomplete: true},
      diagnostics: stored.diagnostics};
  };
}
