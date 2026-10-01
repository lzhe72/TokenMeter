import { contextBridge, ipcRenderer } from 'electron';
import type { Bridge, Snapshot } from '../shared/types';
const call = (method: string, input?: unknown): Promise<Snapshot> => ipcRenderer.invoke('tokenmeter:invoke', method, input);
const bridge: Bridge = {
  snapshot: () => call('snapshot'), login: input => call('login', input), changePassword: input => call('changePassword', input),
  logout: () => call('logout'), retryLogout: () => call('retryLogout'), refresh: () => call('refresh'),
  listUsers: () => call('listUsers'), listAudit: () => call('listAudit'), manageUser: input => call('manageUser', input),
  saveConfiguration: input => call('saveConfiguration', input), resetConfiguration: () => call('resetConfiguration'),
  setAutomaticLogin: value => call('setAutomaticLogin', value), checkUpdates: () => call('checkUpdates'),
  installUpdate: () => call('installUpdate'), cancelUpdate: () => call('cancelUpdate'),
  onOpenConfiguration(callback) { const listener = () => callback(); ipcRenderer.on('tokenmeter:open-configuration', listener); return () => ipcRenderer.removeListener('tokenmeter:open-configuration', listener); },
  onState(callback) { const listener = (_event: Electron.IpcRendererEvent, state: Snapshot) => callback(state); ipcRenderer.on('tokenmeter:state', listener); return () => ipcRenderer.removeListener('tokenmeter:state', listener); }
};
contextBridge.exposeInMainWorld('tokenmeter', bridge);
