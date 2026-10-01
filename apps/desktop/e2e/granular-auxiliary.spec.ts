/** Fixed, independent UI assertions on one installed App and owned service. */
import {test, expect, _electron as electron, type ElectronApplication, type Page} from '@playwright/test';
import {appendFileSync, existsSync, readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {join, resolve} from 'node:path';
import {contrastRatio} from './granular-auxiliary-color';

type Context = {run_id:string;case_id:string;app_path:string;profile_path:string;service_url:string};
const input = process.env.TM_E2E_CONTEXT, output = process.env.TM_E2E_CASE_OUTPUT;
if (!input || !output) throw Error('Owned auxiliary UI context is missing');
const c = JSON.parse(readFileSync(input, 'utf8')) as Context;
const codeRoot = resolve(process.cwd(), '../..');
const catalog = JSON.parse(readFileSync(join(codeRoot, 'tests/test_cases.json'), 'utf8')) as
  {cases:Array<{id:string;steps:Array<{step:number;action:string;expected:string}>}>};
const baseline = catalog.cases.find(item => item.id === c.case_id);
if (!baseline || baseline.steps.length !== 1) throw Error('Auxiliary UI TC has no single frozen step');
const executable = join(c.app_path, 'Contents/MacOS/TokenMeter');
const events = join(output, 'events.jsonl');
let app:ElectronApplication|null = null, page:Page|null = null, tracing = false;
function sha(data:Buffer|string) {return createHash('sha256').update(data).digest('hex');}
function childEnv():Record<string,string> {
  return Object.fromEntries(Object.entries(process.env).filter((entry):entry is [string,string] => entry[1] !== undefined)
    .filter(([key]) => !key.startsWith('TM_E2E_') && !key.startsWith('TM_INTERNAL_') && !key.includes('SIGNING') && !key.includes('TOKEN')));
}
async function launch() {
  app = await electron.launch({executablePath:executable,args:[`--user-data-dir=${c.profile_path}`],
    env:childEnv(),chromiumSandbox:true,timeout:60_000});
  page = await app.firstWindow();
  await expect(page.getByTestId('app.build')).toBeVisible();
  await app.context().tracing.start({screenshots:true,snapshots:true,sources:false}); tracing = true;
}
async function close() {
  if (app) {
    if (tracing) {await app.context().tracing.stop({path:join(output!, 'trace-01.zip')});tracing=false;}
    await app.close(); app=null; page=null;
  }
}
function record(actual:Record<string,unknown>, passed:boolean) {
  const step = baseline!.steps[0]!;
  appendFileSync(events, JSON.stringify({run_id:c.run_id,case_id:c.case_id,step:step.step,
    action:step.action,expected:step.expected,actual,passed,timestamp:new Date().toISOString(),source:'ui'})+'\n', {mode:0o600});
  expect(passed,`${c.case_id}: ${step.expected}`).toBe(true);
}
async function configure() {
  await page!.getByTestId('configuration.open').click();
  await page!.getByTestId('configuration.api-url').fill(c.service_url);
  await page!.getByTestId('configuration.save').click();
  await expect(page!.getByTestId('auth.server')).toHaveValue(c.service_url);
}
async function adminHome() {
  await configure();
  await page!.getByTestId('auth.username').fill('test-admin');
  await page!.getByTestId('auth.password').fill('TEST-ONLY-admin-42!');
  await page!.getByTestId('auth.login').click();
  await expect(page!.getByTestId('password.current')).toBeVisible();
  const passwordLayout=await geometry();
  await page!.screenshot({path:join(output!,'password-dark.png')});
  await page!.getByTestId('password.current').fill('TEST-ONLY-admin-42!');
  await page!.getByTestId('password.new').fill('TEST-ONLY-Changed-42!');
  await page!.getByTestId('password.confirm').fill('TEST-ONLY-Changed-42!');
  await page!.getByTestId('password.submit').click();
  await expect(page!.getByTestId('session.verified')).toBeVisible();
  const homeLayout=await geometry();
  await page!.screenshot({path:join(output!,'home-dark.png')});
  await page!.getByTestId('admin.accounts').click();
  await expect(page!.getByTestId('admin.state.test-admin')).toBeVisible();
  return {passwordLayout,homeLayout};
}
async function geometry() {
  return page!.evaluate(() => {
    const visible = [...document.querySelectorAll('main button,main input,main label,main h1,main h2')]
      .filter(item => {const box=item.getBoundingClientRect();return box.width>0&&box.height>0;});
    const clipped = visible.filter(item => {const box=item.getBoundingClientRect();
      return box.left < -1 || box.right > innerWidth + 1;});
    return {viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
      visibleElements:visible.length,horizontalClipped:clipped.length};
  });
}
async function theme() {
  const colors=await page!.evaluate(() => {
    const style=getComputedStyle(document.documentElement);
    const text=style.getPropertyValue('--text').trim(),surface=style.getPropertyValue('--surface').trim();
    return {text,surface};
  });
  return {...colors,contrast:contrastRatio(colors.text,colors.surface)};
}
test.afterEach(async () => {
  try {if (page && !page.isClosed()) await page.screenshot({path:join(output!, 'final.png')});} catch {}
  try {await close();} catch {}
});

test('TC-TM001-UI-01', async () => {
  await launch();
  await app!.evaluate(({BrowserWindow}) => BrowserWindow.getAllWindows()[0]!.setSize(760,640));
  await page!.emulateMedia({colorScheme:'light'});
  const loginLight=await geometry(), light=await theme();
  await page!.screenshot({path:join(output!,'login-light.png')});
  await page!.emulateMedia({colorScheme:'dark'});
  const loginDark=await geometry(), dark=await theme();
  await page!.screenshot({path:join(output!,'login-dark.png')});
  await configure();
  await page!.getByTestId('auth.username').fill('test-admin');
  await page!.getByTestId('auth.password').fill('TEST-ONLY-Wrong-42!');
  await page!.getByTestId('auth.login').click();
  await expect(page!.getByTestId('auth.error')).toBeVisible();
  const errorColor=await page!.getByTestId('auth.error').evaluate(item=>getComputedStyle(item).color);
  const {passwordLayout,homeLayout}=await adminHome();
  const admin=await geometry();
  await page!.screenshot({path:join(output!,'admin-dark.png')});
  await page!.getByTestId('configuration.open').click();
  const modal=await geometry();
  await page!.screenshot({path:join(output!,'config-dark.png')});
  const successVisible=await page!.getByTestId('password.status').isVisible();
  const layouts=[loginLight,loginDark,passwordLayout,homeLayout,admin,modal];
  const passed=layouts.every(item=>item.visibleElements>0&&item.documentWidth<=item.viewport+1&&item.horizontalClipped===0)
    && light.contrast>=4.5&&dark.contrast>=4.5&&light.surface!==dark.surface
    && !!errorColor&&successVisible;
  record({layouts,light,dark,errorColor,successVisible},passed);
});

test('TC-TM001-UI-02', async () => {
  await launch();
  const opener=page!.getByTestId('configuration.open');
  await opener.focus(); await opener.click();
  const dialog=page!.getByRole('dialog',{name:'服务配置'});
  await expect(dialog).toBeVisible();
  const focusInside=[];
  for (let i=0;i<7;i++) {await page!.keyboard.press('Tab');focusInside.push(await dialog.evaluate(
    element=>element.contains(document.activeElement)));}
  const settings=join(c.profile_path,'settings.json');
  const before=existsSync(settings)?sha(readFileSync(settings)):null;
  await page!.getByTestId('configuration.api-url').fill(c.service_url);
  await page!.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  const cancelled=(existsSync(settings)?sha(readFileSync(settings)):null)===before;
  const focusReturned=await opener.evaluate(element=>document.activeElement===element);
  await page!.keyboard.press('Meta+,');
  await expect(dialog).toBeVisible();
  await page!.getByTestId('configuration.api-url').fill(c.service_url);
  await page!.getByTestId('configuration.api-url').press('Enter');
  await expect(dialog).toBeHidden();
  await expect(page!.getByTestId('auth.server')).toHaveValue(c.service_url);
  const saved=existsSync(settings)&&readFileSync(settings,'utf8').includes(c.service_url);
  await page!.screenshot({path:join(output!,'keyboard-config.png')});
  await adminHome();
  const postLoginOpener=page!.getByTestId('configuration.open');
  await postLoginOpener.focus();await postLoginOpener.click();
  await expect(dialog).toBeVisible();
  const postLoginFocus=[];
  for (let i=0;i<7;i++) {await page!.keyboard.press('Tab');postLoginFocus.push(await dialog.evaluate(
    element=>element.contains(document.activeElement)));}
  await page!.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  const postLoginReturned=await postLoginOpener.evaluate(element=>document.activeElement===element);
  await page!.screenshot({path:join(output!,'keyboard-post-login.png')});
  record({focusInside,cancelled,focusReturned,shortcutOpened:true,enterSaved:saved,
    postLoginFocus,postLoginReturned},
    focusInside.every(Boolean)&&cancelled&&focusReturned&&saved&&postLoginFocus.every(Boolean)&&postLoginReturned);
});

test('TC-TM001-UI-03', async () => {
  await launch();
  const info=join(c.app_path,'Contents/Info.plist');
  const declared=execFileSync('/usr/bin/plutil',['-extract','CFBundleIconFile','raw','-o','-',info],{encoding:'utf8'}).trim();
  const icon=join(c.app_path,'Contents/Resources',declared.endsWith('.icns')?declared:declared+'.icns');
  const sourceIcon=join(codeRoot,'apps/desktop/resources/TokenMeter.icns');
  const sourceSvg=readFileSync(join(codeRoot,'apps/desktop/resources/TokenMeter.svg'));
  const iconMatch=existsSync(icon)&&sha(readFileSync(icon))===sha(readFileSync(sourceIcon));
  const rendered=await page!.locator('.brand .app-icon').evaluate(element => (element as HTMLImageElement).src);
  const renderedSvg=rendered.startsWith('data:image/svg+xml,')?decodeURIComponent(rendered.split(',')[1]!):'';
  const normalize=(value:string)=>value.trim().replace(/>\s+</g,'><').replace(/"/g,"'");
  const svgMatch=normalize(renderedSvg)===normalize(sourceSvg.toString('utf8'));
  const iconVisible=await page!.locator('.brand .app-icon').isVisible();
  const designMarkers=sourceSvg.toString('utf8').includes('id="bars"')&&sourceSvg.toString('utf8').includes('A282 282');
  await page!.screenshot({path:join(output!,'window-icon.png')});
  record({installedIconSha256:iconMatch?sha(readFileSync(icon)):'mismatch',sourceSvgSha256:sha(sourceSvg),
    iconMatch,svgMatch,iconVisible,designMarkers},iconMatch&&svgMatch&&iconVisible&&designMarkers);
});
