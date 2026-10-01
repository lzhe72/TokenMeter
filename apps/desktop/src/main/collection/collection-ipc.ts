import type {CodexRuntime} from './codex-runtime.ts';

export type CollectionEvent = {sender: object; senderFrame: {url: string}};
export type CollectionHandlerPorts = {
  runtime(): CodexRuntime;
  mainSender(): object;
  mainFrame(): object;
  mainUrl: string;
};

export function createCollectionHandler(_ports: CollectionHandlerPorts) {
  return async (_event: CollectionEvent, _method: unknown, _input?: unknown): Promise<unknown> => {
    throw new Error('collection_ipc_not_implemented');
  };
}
