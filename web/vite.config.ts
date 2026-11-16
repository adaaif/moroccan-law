import { execFileSync } from 'node:child_process';
import path from 'node:path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vite';

/** The build's short id, which every batch of measures carries (`build`, at most eight letters and digits: the
 *  analytics review, 15 Nov 2026): the commit the web was built from, «local» outside a git checkout. */
function buildId(): string {
  try {
    const commit = execFileSync('git', ['rev-parse', '--short=7', 'HEAD'], { cwd: import.meta.dirname, stdio: ['ignore', 'pipe', 'ignore'] })
      .toString().trim().slice(0, 8);
    return /^[A-Za-z0-9]{1,8}$/.test(commit) ? commit : 'local';
  } catch {
    return 'local';
  }
}

export default defineConfig(({ isSsrBuild }) => ({
  plugins: [react(), tailwindcss()],
  define: { __BUILD__: JSON.stringify(buildId()) },
  // Seven hash characters, not eight (rolldown's least for this many chunks): the first load's entry names every lazy
  // chunk (121 on 27 Oct 2026), random characters do not compress, and a chunk's new hash moved the first load by up to
  // 20 bytes at its budget's edge. 0.2 KB of room came back.
  // The prerender's renderer keeps its plain name (scripts/prerender.mjs imports dist-ssr/entry-server.js).
  // The minified bundles keep no notice of the packages in them, whose licences ask that it travel with their code:
  // the build writes each bundled package's name, version, licence and its licence's text to /licenses.txt.
  build: {
    license: isSsrBuild ? false : { fileName: 'licenses.txt' },
    rollupOptions: { output: { entryFileNames: isSsrBuild ? '[name].js' : 'assets/[name]-[hash:7].js',
                               chunkFileNames: 'assets/[name]-[hash:7].js' } },
  },
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  // The renderer carries its packages (react, the router, i18next…): the server runs it with node alone, no node_modules
  // (IX1 of the search-engines review: every law's address drawn by the app's own components, scripts/ssr-server.mjs).
  ssr: { noExternal: true },
  server: {
    // Django runserver (back/) on 8020: same origin for the page and /api. WEB_PORT and API_TARGET run a
    // second pair beside it (e.g. against Postgres) without touching the first.
    port: Number(process.env.WEB_PORT ?? 5190),
    strictPort: true,
    // As nginx does on the server: the API, the assistants' sign-in (/oauth, /.well-known) to Django, /mcp to law-mcp.
    proxy: {
      '/api': process.env.API_TARGET ?? 'http://localhost:8020',
      '/oauth': process.env.API_TARGET ?? 'http://localhost:8020',
      '/.well-known': process.env.API_TARGET ?? 'http://localhost:8020',
      '/mcp': process.env.MCP_TARGET ?? 'http://localhost:8042',
    },
  },
}));
