import { defineConfig } from 'electron-vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  main: { build: { rollupOptions: { output: { format: 'cjs', entryFileNames: 'index.cjs' } } } },
  preload: { build: { rollupOptions: { output: { format: 'cjs', entryFileNames: 'index.cjs', inlineDynamicImports: true } } } },
  renderer: { plugins: [react()], build: { sourcemap: false } }
});
