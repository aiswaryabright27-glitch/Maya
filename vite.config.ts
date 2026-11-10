import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const developmentCsp = {
  name: 'maya-dev-csp',
  transformIndexHtml(html: string, context: { server?: unknown }) {
    if (!context.server) return html;
    return html.replace(
      "connect-src 'self' ws://127.0.0.1:5173; style-src 'self'; script-src 'self'",
      "connect-src 'self' ws://127.0.0.1:*; style-src 'self'; script-src 'self' 'unsafe-inline'",
    );
  },
};

export default defineConfig({ plugins: [react(), developmentCsp], root: 'frontend', server: { host: '127.0.0.1' }, build: { outDir: '../dist', emptyOutDir: true } });
