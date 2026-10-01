/** Auxiliary real-window visual checks. This does not issue product qualification. */
const { _electron, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

async function run() {
  const context = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  if (context.owner !== 'tokenmeter-hig-probe' || !path.isAbsolute(context.output) || !context.service_url.startsWith('http://127.0.0.1:')) throw Error('Invalid owned visual context');
  const application = await _electron.launch({executablePath: context.executable, args: [context.project, `--user-data-dir=${context.profile}`], chromiumSandbox: true, timeout: 30000});
  const checks = [];
  try {
    const page = await application.firstWindow();
    await expect(page.getByTestId('app.build')).toBeVisible();
    const shot = async name => {
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({path: path.join(context.output, name+'.png')});
      checks.push({name, horizontal_overflow: false});
    };
    await application.evaluate(({nativeTheme}) => {nativeTheme.themeSource='light';});
    await page.emulateMedia({colorScheme:'light'});
    await shot('01-login-light-default');
    await application.evaluate(({BrowserWindow}) => BrowserWindow.getAllWindows()[0].setSize(760,640));
    await shot('02-login-light-minimum');
    await application.evaluate(({nativeTheme}) => {nativeTheme.themeSource='dark';});
    await page.emulateMedia({colorScheme:'dark'});
    expect(await page.evaluate(() => matchMedia('(prefers-color-scheme:dark)').matches)).toBe(true);
    await shot('03-login-dark-minimum');
    await page.getByTestId('configuration.open').click();
    await expect(page.getByTestId('configuration.api-url')).toBeFocused();
    for(let n=0;n<8;n++) {await page.keyboard.press('Tab'); expect(await page.evaluate(() => !!document.activeElement.closest('dialog'))).toBe(true);}
    await shot('04-configuration-dark-minimum');
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByTestId('configuration.open')).toBeFocused();
    checks.push({name:'dialog-keyboard',focus_trapped:true,escape_closes:true,focus_restored:true});
    await page.keyboard.press('Meta+,');
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.getByTestId('configuration.api-url').fill(context.service_url);
    await page.getByTestId('configuration.update-url').fill(context.service_url+'/version.json');
    await page.getByTestId('configuration.update-url').press('Enter');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    checks.push({name:'configuration-keyboard',command_comma:true,enter_saves:true});
    await page.getByTestId('auth.username').fill('test-admin');
    await page.getByTestId('auth.password').fill('TEST-ONLY-Wrong-42!');
    await page.getByTestId('auth.password').press('Enter');
    await expect(page.getByTestId('auth.error')).toContainText('invalid_credentials');
    await shot('05-login-error-dark');
    await page.getByTestId('auth.password').fill('TEST-ONLY-admin-42!');
    await page.getByTestId('auth.password').press('Enter');
    await expect(page.getByTestId('password.new')).toBeVisible();
    await shot('06-forced-password-dark-minimum');
    await page.getByTestId('password.current').fill('TEST-ONLY-admin-42!');
    await page.getByTestId('password.new').fill('TEST-ONLY-HIG-Changed-42!');
    await page.getByTestId('password.confirm').fill('TEST-ONLY-HIG-Changed-42!');
    await page.getByTestId('password.confirm').press('Enter');
    await expect(page.getByTestId('password.status')).toBeVisible();
    await page.getByTestId('admin.accounts').click();
    await expect(page.getByTestId('admin.state.test-bob')).toBeVisible();
    await page.getByTestId('admin.audit').click();
    await expect(page.getByTestId('audit.action.password_changed')).toBeVisible();
    await expect(page.getByTestId('password.new')).toHaveCount(0);
    await page.getByTestId('password.toggle').click();
    await expect(page.getByTestId('password.new')).toBeVisible();
    await page.getByTestId('password.toggle').click();
    await expect(page.getByTestId('password.new')).toHaveCount(0);
    await page.getByTestId('admin.accounts').scrollIntoViewIfNeeded();
    await shot('07-admin-dark-minimum');
    await application.evaluate(({nativeTheme,BrowserWindow}) => {nativeTheme.themeSource='light';BrowserWindow.getAllWindows()[0].setSize(1080,800);});
    await page.emulateMedia({colorScheme:'light'});
    await page.evaluate(() => window.scrollTo(0,0));
    await shot('08-admin-light-default');
    await page.getByTestId('admin.reset.test-bob').click();
    await expect(page.getByTestId('admin.temporary-password')).toBeFocused();
    await shot('09-reset-password-sheet-light');
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('admin.reset.test-bob')).toBeFocused();
    await page.getByTestId('updates.check').click();
    await expect(page.getByTestId('updates.status')).toContainText('update_download_failed');
    await page.getByTestId('updates.status').scrollIntoViewIfNeeded();
    await shot('10-update-state-light');
    const typography = await page.evaluate(() => ({body:getComputedStyle(document.documentElement).fontSize,title:getComputedStyle(document.querySelector('h1')).fontSize,dark:matchMedia('(prefers-color-scheme:dark)').matches}));
    fs.writeFileSync(path.join(context.output,'visual-checks.json'),JSON.stringify({scope:'auxiliary_visual',product_e2e:false,checks,typography},null,2),{mode:0o600});
    console.log(JSON.stringify({scope:'auxiliary_visual',checks:checks.length,output:context.output}));
  } finally { await application.close(); }
}
run().catch(error => {console.error(error);process.exitCode=1;});
