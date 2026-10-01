#!/usr/bin/env node
// Render the original vector with the pinned Electron runtime, then use macOS
// iconutil. This is asset generation, never product E2E evidence.
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, copyFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(join(root, 'apps/desktop/package.json'));
const { _electron: electron } = require('@playwright/test');
const resources = join(root, 'apps/desktop/resources');
const source = readFileSync(join(resources, 'TokenMeter.svg'), 'utf8');
const work = mkdtempSync(join(tmpdir(), 'tokenmeter-icon-'));
const icons = join(work, 'TokenMeter.iconset');
mkdirSync(icons);
writeFileSync(join(work, 'main.cjs'), `const {app,BrowserWindow}=require('electron');
app.whenReady().then(()=>{const w=new BrowserWindow({show:false,width:1024,height:1024,
webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false}});w.loadURL('about:blank');});`);
let app;
try {
  app = await electron.launch({ executablePath: require('electron'),
    args: [join(work, 'main.cjs'), '--user-data-dir='+join(work, 'profile')], chromiumSandbox: true });
  const page = await app.firstWindow();
  await page.setContent(`<html><head><style>html,body{margin:0;background:transparent;overflow:hidden}svg{width:100vw;height:100vh;display:block}</style></head><body>${source}</body></html>`);
  for (const size of [16, 32, 128, 256, 512]) {
    for (const scale of [1, 2]) {
      const pixels = size*scale;
      await page.setViewportSize({width:pixels,height:pixels});
      const file = join(icons, `icon_${size}x${size}${scale===2?'@2x':''}.png`);
      await page.screenshot({path:file,omitBackground:true,scale:'css'});
      if (pixels===1024) copyFileSync(file,join(resources,'TokenMeter.png'));
    }
  }
  execFileSync('/usr/bin/iconutil',['-c','icns',icons,'-o',join(resources,'TokenMeter.icns')]);
  console.log('Created TokenMeter.png and TokenMeter.icns from TokenMeter.svg');
} finally {
  if (app) await app.close();
  rmSync(work,{recursive:true,force:true});
}
