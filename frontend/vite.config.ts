import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Content-Security-Policy meta — injected ONLY into production builds.
// Dev mode needs inline scripts (React Refresh preamble) and HMR WebSockets,
// so applying CSP there would break the dev server.
//
// NOTE: `frame-ancestors` is deliberately omitted — it is ignored when
// delivered via a <meta> element (header-only directive).
function productionCspPlugin(apiOrigin: string): Plugin {
  return {
    name: 'inject-production-csp',
    transformIndexHtml(html, ctx) {
      if (ctx.server) return html; // dev server — skip

      // Backend API origin for fetch/SSE connections (same-origin falls back
      // to 'self' automatically, so an empty string is safe).
      const connectSrc = apiOrigin ? `'self' ${apiOrigin}` : "'self'";

      const CSP = [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' https://fonts.gstatic.com",
        `connect-src ${connectSrc}`,
        "base-uri 'self'",
        "form-action 'self'",
      ].join('; ');

      return html.replace(
        '</head>',
        `    <meta http-equiv="Content-Security-Policy" content="${CSP}" />\n  </head>`,
      );
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxyTarget = env.VITE_API_URL || 'http://localhost:8000';
  return {
    plugins: [react(), tailwindcss(), productionCspPlugin(env.VITE_API_URL || '')],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
        '/health': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      target: 'es2020',
      cssMinify: true,
      // No source maps in production (smaller payloads, faster parse)
      sourcemap: false,
      // Tolerate the (intentional) large vendor chunks
      chunkSizeWarningLimit: 700,
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (id.includes('node_modules/react-dom') || id.includes('node_modules/react/') || id.includes('node_modules/react-router')) return 'vendor-react';
            if (id.includes('node_modules/@tanstack/react-query')) return 'vendor-query';
            if (id.includes('node_modules/react-markdown') || id.includes('node_modules/remark-gfm')) return 'vendor-md';
            if (id.includes('node_modules/zustand')) return 'vendor-state';
            if (id.includes('node_modules/lucide-react')) return 'vendor-icons';
            if (id.includes('node_modules/@microsoft/fetch-event-source')) return 'vendor-sse';
          },
        },
      },
    },
  };
})
