import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
  ],
  build: {
    rollupOptions: {
      output: {
        // Without this, Rollup's default chunking groups every node_modules
        // dependency into one bundle regardless of whether it's only ever
        // reached through a lazy route import — so recharts (only used by
        // AgentChat/StaffChat inside the lazy-loaded dashboards) was ending
        // up in the eager entry chunk that even the public login page had
        // to download. Splitting these out means the public/auth pages only
        // fetch 'vendor', and 'vendor-charts'/'vendor-icons' load lazily
        // alongside whichever dashboard chunk actually needs them.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('recharts') || id.includes('d3-')) return 'vendor-charts';
          if (id.includes('lucide-react')) return 'vendor-icons';
          return 'vendor';
        },
      },
    },
  },
})
