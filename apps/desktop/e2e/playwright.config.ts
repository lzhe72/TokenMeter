import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';

const output = process.env.TM_E2E_CASE_OUTPUT;
const raw = process.env.TM_E2E_JSON;
if (!output || !raw || !process.env.TM_E2E_CONTEXT) throw new Error('Missing owned local E2E paths');
const spec = process.env.TM_E2E_SPEC ?? 'tm001.spec.ts';
if (!['tm001.spec.ts', 'granular-login.spec.ts', 'granular-account.spec.ts',
      'granular-config.spec.ts', 'granular-update.spec.ts', 'granular-update-validation.spec.ts',
      'granular-auxiliary.spec.ts', 'granular-permissions.spec.ts'].includes(spec)) {
  throw new Error('Unrecognized owned E2E spec');
}

export default defineConfig({
  testDir: resolve(__dirname),
  testMatch: spec,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 480_000,
  expect: { timeout: 20_000 },
  outputDir: resolve(output, 'playwright-test-results'),
  reporter: [['json', { outputFile: resolve(raw) }]],
  metadata: { run_id: process.env.TM_E2E_RUN_ID, candidate_sha: process.env.TM_E2E_CANDIDATE_SHA },
});
