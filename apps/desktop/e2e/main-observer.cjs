/* Fixed evidence collector injected while the installed main entry is paused.
 * Every wrapper delegates unchanged arguments and returns the original result.
 * No credential, request body, query string or response content is recorded. */
module.exports = function installMainObserver(options) {
  const fs = require('node:fs');
  const dc = require('node:diagnostics_channel');
  const electron = require('electron');
  let sequence = 0;
  function record(kind, detail) {
    fs.appendFileSync(options.path, JSON.stringify({run_id: options.run_id, case_id: options.case_id,
      launch_id: options.launch_id, pid: process.pid, sequence: ++sequence,
      time: new Date().toISOString(), kind, ...detail}) + '\n', {mode: 0o600});
  }
  function address(value) {
    try { const url = new URL(String(value)); return {origin: url.origin, path: url.pathname}; }
    catch { return {origin: '[unparseable]', path: '[unparseable]'}; }
  }
  // Emitted by the real undici client for fetch, before socket dispatch.
  dc.channel('undici:request:create').subscribe(({request}) => record('request', {
    transport: 'undici', method: request.method, ...address(String(request.origin) + request.path)}));
  for (const scheme of ['http', 'https']) {
    const api = require('node:' + scheme);
    for (const name of ['request', 'get']) {
      const original = api[name];
      api[name] = function (...args) {
        const first = args[0];
        let target = first;
        if (first && typeof first === 'object' && !(first instanceof URL)) {
          target = (first.protocol || scheme + ':') + '//' + (first.hostname || first.host || 'localhost') +
            (first.port ? ':' + first.port : '') + (first.path || '/');
        }
        record('request', {transport: 'node-' + scheme, method: args[1]?.method || first?.method || 'GET', ...address(target)});
        return Reflect.apply(original, this, args);
      };
    }
  }
  for (const method of ['setFeedURL', 'checkForUpdates', 'quitAndInstall']) {
    const original = electron.autoUpdater[method];
    if (typeof original !== 'function') throw Error('Required native update method absent: ' + method);
    electron.autoUpdater[method] = function (...args) {
      record('native-updater', {method});
      return Reflect.apply(original, this, args);
    };
    if (electron.autoUpdater[method] === original) throw Error('Native observer failed to attach: ' + method);
  }
  const seen = new WeakSet();
  electron.app.on('web-contents-created', (_event, contents) => {
    const session = contents.session;
    if (seen.has(session)) return;
    seen.add(session);
    session.webRequest.onBeforeRequest({urls: ['http://*/*', 'https://*/*']}, (details, callback) => {
      record('request', {transport: 'chromium', method: details.method, ...address(details.url)});
      callback({cancel: false});
    });
  });
  record('installed-before-entry', {source_sha256: options.source_sha256,
    paused_function: options.paused_function, paused_url: options.paused_url,
    transports: ['undici', 'node-http', 'node-https', 'chromium'],
    native_methods: ['setFeedURL', 'checkForUpdates', 'quitAndInstall']});
  return {installed: true, pid: process.pid};
};
